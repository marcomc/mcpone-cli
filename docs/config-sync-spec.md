# Config Sync Spec

## Purpose

This document defines the current import and export behavior between the McpOne
database and agent config files.

## Supported File Types

- JSON
- TOML

JSON is handled with the stdlib `json` module.
TOML is handled with `tomllib` for reading and `tomli_w` for writing.

## Canonical App Fields

Sync and import depend on:

- `ZADDEDAPP.ZAIAGENTJSONFILEPATH`
- `ZADDEDAPP.ZAIAGENTJSONKEY`
- `ZADDEDAPP.ZACTIVECLUSTERID`

If any of these are missing, sync cannot proceed for that app.

## Export Rules

Export flow:

1. resolve app
2. resolve active cluster
3. decode enabled server IDs
4. fetch `ZADDEDSERVER` rows for those IDs
5. convert servers into target config entries
6. write them under the target root key

## Import Rules

Import flow:

1. load config file
2. read the root key object
3. parse each server entry key
4. derive display name and optional embedded ID
5. create missing `ZADDEDSERVER` rows

Import does not currently delete existing DB rows.

## Root Keys

Verified current keys:

- `mcp_servers` for Codex TOML
- `mcpServers` for Claude/Gemini/Copilot-style JSON
- `servers` for VS Code MCP JSON

## Key Naming Styles

### Bracketed style

Example:

```text
Context7[id=7J6VKW]
```

Used for:

- Claude-style configs
- generic JSON targets without a known compatibility override

### Sanitized style

Example:

```text
Context7_id_7J6VKW
```

Used for:

- Codex TOML
- Gemini JSON written by `mcpone-cli`
- Copilot-style JSON
- VS Code-style JSON if configured similarly

## Client Compatibility Rules

`mcpone-cli` applies a small amount of client-specific export behavior when the
target app is known to reject bracketed MCP server names.

- Gemini CLI exports `mcpServers` entries with sanitized keys such as
  `Context7_id_7J6VKW`
- Copilot exports sanitized keys and injects `tools = ["*"]` into each server
  entry for Copilot CLI compatibility
- Codex TOML exports sanitized keys and translates remote bearer
  `Authorization` headers into `bearer_token_env_var` entries instead of
  serializing the bearer token as a header directly
- Claude-style JSON remains bracketed by default

## Value Mapping

Current export mapping uses these server fields:

- `command`
- `args`
- `env`
- `url`
- `headers`

It intentionally does not export every database field.

### Codex bearer auth translation

For Codex TOML targets, if a remote server has an `Authorization` header with a
`Bearer ...` value, `mcpone-cli` rewrites that auth into Codex's expected
`bearer_token_env_var` shape during sync.

Example DB-side server state:

```json
{
  "url": "https://api.githubcopilot.com/mcp",
  "headers": {
    "Authorization": "Bearer <token>"
  }
}
```

Codex output shape:

```toml
[mcp_servers.GitHub_id_ABC123]
url = "https://api.githubcopilot.com/mcp"
bearer_token_env_var = "CODEX_GITHUB_PERSONAL_ACCESS_TOKEN"
```

Notes:

- this translation is Codex-specific and does not change the McpOne DB record
- this applies to any Codex remote MCP server whose `Authorization` header uses
  a `Bearer ...` value, not only GitHub
- non-auth headers are still emitted normally
- the referenced environment variable must exist when Codex runs

## Known Non-Goals

- no conflict resolution between existing config entries and DB rows
- no three-way merge
- no deep preservation of formatting style beyond valid JSON/TOML output
- no support yet for every possible agent-specific custom field

## Contributor Rules

- if you change key naming logic, update [`formats.py`](../src/mcpone_cli/formats.py)
- if you broaden supported shapes, add fixture tests
- if you support a new tool family, document its root key and key style here
