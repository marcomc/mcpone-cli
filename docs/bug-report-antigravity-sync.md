# Bug Report: `sync app` breaks on text-typed server fields and can emit an empty `mcp.json` for custom MCP clients

## Summary

While registering a new custom MCP client (`Antigravity`) with `mcpone-cli`, I hit two distinct issues:

1. `mcpone-cli sync app Antigravity` initially crashed because `decode_blob()` assumes `ZARGS` / `ZENV` / `ZPARAMETERS` are `bytes`, but at least one existing `ZADDEDSERVER` row in the McpOne DB stored them as `TEXT`.
2. After normalizing that malformed row and retrying, `mcpone-cli sync app Antigravity` reported success but wrote an empty config file:

```json
{
  "servers": {}
}
```

This happened even though the Antigravity cluster had enabled server IDs in McpOne.

## Environment

- macOS
- McpOne DB path:
  `/Users/mmassari/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite`
- `mcpone-cli` source checkout:
  `/Users/mmassari/Development/mcpone-cli`

## Reproduction

### Part 1: crash while syncing a custom app

1. Add a custom app:

```bash
mcpone-cli apps add-custom Antigravity \
  "$HOME/Library/Application Support/Antigravity/User/mcp.json" \
  --config-key servers \
  --ai-agent-id custom \
  --explanation "Antigravity MCP client"
```

2. Attempt to sync:

```bash
mcpone-cli sync app Antigravity
```

3. Observe a traceback ending in:

```text
AttributeError: 'str' object has no attribute 'decode'
```

### Part 2: sync succeeds but emits an empty config

1. Normalize the malformed server row so the CLI can continue:

```sql
-- offending row on this machine:
SELECT ZID, ZNAME, typeof(ZARGS), typeof(ZENV), typeof(ZPARAMETERS)
FROM ZADDEDSERVER
WHERE ZID='AM7K2Q';
```

Observed values before fix:

```text
AM7K2Q | automac-mcp | text | text | text
```

2. Enable servers for the custom app:

```bash
mcpone-cli servers enable 7J6VKW SUG610 PX649D WTYCA2 ZNACLC VCAO8D \
  --app Antigravity \
  --cluster "Cluster A"
```

3. Re-run sync:

```bash
mcpone-cli sync app Antigravity
```

4. Observe a success message:

```text
Synced Antigravity -> /Users/mmassari/Library/Application Support/Antigravity/User/mcp.json
```

5. But the output file contains:

```json
{
  "servers": {}
}
```

6. At the same time, the McpOne cluster has enabled server IDs:

```text
['7J6VKW', 'SUG610', 'PX649D', 'WTYCA2', 'ZNACLC', 'VCAO8D']
```

## Expected Behavior

- `sync app` should not crash when McpOne contains legacy / non-blob JSON fields stored as `TEXT`.
- `sync app Antigravity` should write a populated `servers` object into `mcp.json`.

## Actual Behavior

- `sync app` crashes on legacy `TEXT` rows because `decode_blob()` blindly calls `.decode("utf-8")`.
- After repairing the malformed row, `sync app` can still report success while producing an empty config map for a custom MCP client.

## Likely Root Cause 1

`decode_blob()` only accepts `bytes | None` and unconditionally calls `.decode()`:

File:
`src/mcpone_cli/store.py`

Relevant code:

```python
def decode_blob(blob: bytes | None, fallback: object) -> object:
    if not blob:
        return fallback
    try:
        return json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return fallback
```

This fails if SQLite returns `TEXT` instead of `BLOB`.

### Suggested fix

Handle both `bytes` and `str`:

```python
def decode_blob(blob: bytes | str | None, fallback: object) -> object:
    if not blob:
        return fallback
    try:
        if isinstance(blob, bytes):
            text = blob.decode("utf-8")
        else:
            text = blob
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return fallback
```

## Likely Root Cause 2

There is a second sync-path issue for custom apps like Antigravity where:

- the app is valid,
- the cluster is populated,
- `sync app` reports success,
- but `write_config_map()` ends up writing an empty object for the configured key.

Relevant path:

- `src/mcpone_cli/cli.py`
- `src/mcpone_cli/formats.py`

Code path:

```python
cluster = runtime.store.get_cluster(target.name, cluster_id)
servers = runtime.store.get_servers_by_ids(cluster.enabled_server_ids)
output = enabled_servers_to_config(target, servers)
write_config_map(Path(target.config_path).expanduser(), target.config_key, output)
```

This needs deeper debugging. Based on the observed state, one of these is going wrong:

- `get_servers_by_ids()` is unexpectedly returning `[]` despite valid enabled IDs.
- `enabled_servers_to_config()` is returning `{}` for a valid custom app.
- The custom app / cluster lookup path is inconsistent for newly-created `add-custom` apps.

## Additional Observation

`infer_key_style()` currently treats any path ending in `/mcp.json` as `sanitized`:

```python
if config_path.endswith("mcp-config.json") or config_path.endswith("/mcp.json"):
    return "sanitized"
```

That is correct for some clients, but not all VS Code-like MCP clients. Even if this is not the cause of the empty output bug, it is too broad and may generate the wrong key shape for clients that expect bracketed names like:

```json
"Context7[id=7J6VKW]": { ... }
```

instead of:

```json
"Context7_id_7J6VKW": { ... }
```

## Impact

- `mcpone-cli` is brittle against real-world McpOne DB rows that are JSON stored as `TEXT`.
- Adding new custom clients is unreliable because sync can silently produce an unusable empty `mcp.json`.
- Custom MCP clients that are not hardcoded into the tool are harder to onboard, which is one of the CLI’s main advantages.

## Workaround Used Locally

1. Manually converted the malformed `automac-mcp` row from `TEXT` to `BLOB`.
2. Manually populated:

`/Users/mmassari/Library/Application Support/Antigravity/User/mcp.json`

with the enabled server set after `sync app` wrote `{ "servers": {} }`.

