# Bug Report: remote `GitHub` market install does not produce a usable authenticated config

## Summary

Installing the `GitHub` market tool with the `STREAMABLE_HTTP` connection through `mcpone-cli` does not yield a working authenticated remote MCP configuration.

There appear to be two separate problems:

1. The initial market install creates a remote server record with only:
   - `url = https://api.githubcopilot.com/mcp`
   - no usable auth materialization from the provided token
2. Even after manually updating the McpOne server record to include an `Authorization: Bearer ...` header, `mcpone-cli sync app Codex` does not emit that header into the generated Codex config file.

Because of that, the resulting remote GitHub MCP config is unusable in Codex and fails with:

```text
No access token was provided in this request
```

## Environment

- macOS
- McpOne DB path:
  `/Users/mmassari/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite`
- `mcpone-cli` source checkout:
  `/Users/mmassari/Development/mcpone-cli`
- Codex config target:
  `/Users/mmassari/.codex/config.toml`

## Reproduction

### Part 1: install remote GitHub market server with an existing PAT

Starting point:

- local GitHub McpOne server exists as `PX649D`
- it works through Docker with `GITHUB_PERSONAL_ACCESS_TOKEN`

Install the remote GitHub market connection into Codex:

```bash
mcpone-cli market install GitHub \
  --app Codex \
  --cluster "Cluster A" \
  --connection STREAMABLE_HTTP \
  --param "OAUTH_BEARER=<existing_github_pat>"
```

On this machine, that created a second GitHub server:

```text
UJT5OQ | GitHub | STREAMABLE_HTTP | https://api.githubcopilot.com/mcp
```

Then disable the old local GitHub server and sync Codex:

```bash
mcpone-cli servers disable PX649D --app Codex --cluster "Cluster A"
mcpone-cli sync app Codex
```

Resulting Codex config excerpt:

```toml
[mcp_servers.GitHub_id_UJT5OQ]
url = "https://api.githubcopilot.com/mcp"
```

No auth header or token material is emitted.

### Part 2: manually add auth header to the McpOne remote server record

Update the remote server in McpOne:

```bash
mcpone-cli servers update UJT5OQ \
  --header "Authorization=Bearer <existing_github_pat>"
```

Verify the McpOne server record:

```bash
mcpone-cli servers show UJT5OQ
```

Observed:

```text
Type: STREAMABLE_HTTP
URL: https://api.githubcopilot.com/mcp
Headers: {"Authorization": "Bearer <existing_github_pat>"}
```

Then sync Codex again:

```bash
mcpone-cli sync app Codex
```

Observed Codex config excerpt:

```toml
[mcp_servers.GitHub_id_UJT5OQ]
url = "https://api.githubcopilot.com/mcp"
```

The header is still missing from the emitted config, despite being present in the McpOne DB row.

### Part 3: live Codex verification

Run a Codex CLI task that requires the GitHub MCP server:

```bash
codex exec --skip-git-repo-check \
  "Use the GitHub MCP server to call get_me and print only the GitHub login."
```

Observed failure:

```text
mcp: GitHub_id_UJT5OQ failed: The GitHub_id_UJT5OQ MCP server is not logged in.
Run `codex mcp login GitHub_id_UJT5OQ`.
```

And the underlying transport error was:

```text
No access token was provided in this request
```

## Expected Behavior

One of the following should happen:

1. `market install GitHub --connection STREAMABLE_HTTP --param OAUTH_BEARER=...` should emit a fully usable authenticated remote config for supported clients, or
2. the tool should refuse this installation mode for clients/config formats where it cannot materialize the required auth correctly.

At minimum, if a remote `STREAMABLE_HTTP` server row contains headers in McpOne, `sync app` should preserve those headers in the client config.

## Actual Behavior

- The remote GitHub market install produces an apparently valid McpOne server row.
- The generated client config omits the auth header.
- Codex cannot authenticate to the remote GitHub MCP endpoint.

## Likely Root Cause

There are probably two separate issues:

### 1. Market install / materialization gap

The remote GitHub market definition accepts `OAUTH_BEARER`, but the installed server row does not automatically materialize it into a persisted header that survives sync in the expected client config.

### 2. Sync serialization bug for remote headers

`server_to_config_dict()` in:

`src/mcpone_cli/formats.py`

does serialize `server.headers` in general:

```python
if server.headers:
    data["headers"] = server.headers
```

But for this GitHub remote server, the emitted Codex config still lacked `headers`, even though:

```bash
mcpone-cli servers show UJT5OQ
```

confirmed the header was present in the DB row.

That suggests one of:

- the sync path is not actually reading the updated headers for this server instance
- the wrong server instance is being emitted
- the app/cluster/server resolution path is stale after install/update
- or the config writer is dropping headers for this case unexpectedly

## Important Caveat

There may also be a client-side compatibility issue with Codex or the GitHub remote MCP endpoint itself.

I manually patched Codex config to include:

```toml
[mcp_servers.GitHub_id_UJT5OQ.headers]
Authorization = "Bearer <existing_github_pat>"
```

and Codex still reported:

```text
No access token was provided in this request
```

So this bug report is specifically about the `mcpone-cli` side:

- remote GitHub install is not producing a usable synced config
- sync does not preserve the header that exists in the McpOne server record

Even if Codex also has a separate auth-handling issue, the McpOne sync behavior still appears wrong.

## Impact

- Remote `GitHub` MCP setup through `mcpone-cli` is not reliable.
- Users can believe the server is installed correctly while generated configs are missing required auth.
- It is easy to end up with a broken client config and no clear indication that auth material was dropped.

## Local Workaround Used

I reverted Codex back to the known-good local GitHub server:

- re-enabled `PX649D`
- deleted the test remote server `UJT5OQ`
- re-synced Codex

`Context7` and `Firecrawl` remote installs worked, so this issue appears specific to the GitHub remote market path.
