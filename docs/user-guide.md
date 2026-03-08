# User Guide

## What This Tool Is

`mcpone-cli` is a macOS command-line interface for McpOne Desktop.
It focuses on the operational layer that McpOne persists locally:

- apps
- clusters
- added servers
- market catalog entries shipped with the app
- agent config import and sync

This means you can inspect and automate most of the state that the desktop app
stores without manually browsing SQLite or re-learning each config format.

## What It Can Do

- list and inspect McpOne apps
- create custom apps that point to JSON or TOML MCP config files
- list, inspect, create, update, and delete added servers
- create, rename, delete, and inspect clusters
- enable and disable servers inside a cluster
- switch the active cluster for an app
- read the bundled McpOne market catalog from the installed app bundle
- install market entries into McpOne and enable them for a cluster
- import MCP servers from agent config files into McpOne
- sync the active cluster for an app back to its target config file
- run a doctor check for the DB path, resource manifests, and app count

## What It Does Not Yet Do

The current CLI does not try to replicate every GUI-only behavior in the desktop
app. It does not yet provide:

- a full TUI or interactive browser
- secrets-safe prompting for market parameters
- deep editing of every Core Data field used by the app
- hidden server management per app
- bidirectional diff and conflict resolution between DB and agent config files

Those gaps are tracked in [`TODO.md`](../TODO.md).

## Requirements

- macOS
- Python 3.11+
- McpOne Desktop installed if you want to operate on the live database

Default McpOne DB path:

```text
~/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite
```

Default app resource path:

```text
/Applications/McpOne.app/Contents/Resources
```

## Install

Clone and install locally:

```bash
git clone <repo-url>
cd mcpone-cli
make install
```

Show help:

```bash
mcpone-cli --help
```

## Configuration

`mcpone-cli` optionally reads:

- `~/.config/mcpone-cli/config.toml`
- or a custom file passed via `--config`

See [`config.toml.example`](../config.toml.example).

Supported keys:

- `db_path`
- `resources_dir`
- `backup_on_write`

`backup_on_write = true` causes the CLI to create a timestamped SQLite backup
before write operations.

For programmatic use, add `--json` before the command group:

```bash
mcpone-cli --json apps list
mcpone-cli --json apps matrix Codex
```

## Read-Only Examples

List apps:

```bash
mcpone-cli apps list
```

Show one app:

```bash
mcpone-cli apps show Codex
```

Show the app-wide server/cluster matrix for one app:

```bash
mcpone-cli apps matrix Codex
```

Show only servers enabled in at least one cluster for the app:

```bash
mcpone-cli apps matrix Codex --enabled-only
```

List clusters for one app:

```bash
mcpone-cli clusters list --app Codex
```

List imported servers only:

```bash
mcpone-cli servers list --source imported
```

Inspect the market catalog:

```bash
mcpone-cli market list --category development
```

Check the local environment:

```bash
mcpone-cli doctor
```

## Write Examples

Add a custom app:

```bash
mcpone-cli apps add-custom "Claude CLI" ~/.claude.json --config-key mcpServers
```

Create a cluster:

```bash
mcpone-cli clusters create "Testing" --app Codex
```

Add a server manually:

```bash
mcpone-cli servers add \
  "My Server" \
  --command npx \
  --arg -y \
  --arg my-server-package \
  --env API_KEY=secret \
  --type STDIO
```

Enable a server in a cluster:

```bash
mcpone-cli servers enable Context7 --app Codex --cluster "Cluster A"
```

Disable a server:

```bash
mcpone-cli servers disable Context7 --app Codex --cluster "Cluster A"
```

Set an app's active cluster:

```bash
mcpone-cli apps set-active-cluster Codex Testing
```

## Administrative Workflows

### Add a new app

Create a custom app entry that points McpOne to a specific MCP config file:

```bash
mcpone-cli apps add-custom "Claude CLI" ~/.claude.json --config-key mcpServers
```

Use this when the app is not already present in the McpOne database.

### Add a new cluster for an app

Create an extra cluster for an existing app:

```bash
mcpone-cli clusters create "Staging" --app Codex
```

Switch the app to use that cluster:

```bash
mcpone-cli apps set-active-cluster Codex Staging
```

### Add a new MCP or local server

Example: add a local Python-based server:

```bash
mcpone-cli servers add \
  "Local Dev Server" \
  --command python3 \
  --arg -m \
  --arg my_local_server \
  --env DEBUG=true \
  --type STDIO \
  --source imported
```

Example: add a remote HTTP server:

```bash
mcpone-cli servers add \
  "Remote Docs Server" \
  --url https://example.com/mcp \
  --header AUTHORIZATION="Bearer token" \
  --type STREAMABLE_HTTP
```

### Attach a server to one cluster

```bash
mcpone-cli servers enable "Local Dev Server" --app Codex --cluster "Cluster A"
```

### Attach one server to multiple app clusters at once

Use `servers enable-many` with repeated `--target` values.

Target format:

- `APP::CLUSTER`
- or `APP/CLUSTER`

Example:

```bash
mcpone-cli servers enable-many \
  "Local Dev Server" \
  --target "Codex::Cluster A" \
  --target "Codex::Testing" \
  --target "Claude CLI::Cluster A"
```

You can also attach multiple servers at once:

```bash
mcpone-cli servers enable-many \
  Context7 \
  Firecrawl \
  --target "Codex::Cluster A" \
  --target "Gemini CLI::Cluster A"
```

## Market Workflow

The desktop app ships market manifests in JSON files inside the application
bundle. `mcpone-cli` reads those files directly.

Typical flow:

1. discover a tool with `market list`
2. inspect it with `market show`
3. install it with `market install`
4. sync the app config with `sync app`

Example:

```bash
mcpone-cli market show Context7
mcpone-cli market install \
  Context7 \
  --app Codex \
  --cluster "Cluster A" \
  --param CONTEXT7_API_KEY=your-key
.venv/bin/mcpone-cli sync app Codex
```

Notes:

- market installs currently materialize one connection choice per install
- if a market tool has multiple connection types, use `--connection`
- required placeholder parameters must be passed with `--param KEY=VALUE`

## Import Workflow

Import reads an existing agent config file and creates missing McpOne servers.

Import from the app's configured file:

```bash
mcpone-cli import app Codex
```

Import from an explicit file and key:

```bash
mcpone-cli import file \
  "Claude CLI" \
  --path ~/.claude.json \
  --key mcpServers
```

## Sync Workflow

Sync takes the app's active cluster, resolves its enabled server IDs against the
McpOne DB, converts them into the target config format, and writes them to the
configured file.

Sync one app:

```bash
mcpone-cli sync app Codex
```

Sync every configured app:

```bash
mcpone-cli sync all
```

## Config Format Behavior

The CLI currently supports the same config styles that were verified locally in
McpOne-managed agent files:

- Codex TOML: `mcp_servers`
- Claude JSON: `mcpServers`
- Gemini JSON: `mcpServers`
- Copilot JSON: `mcpServers`
- VS Code JSON: `servers`

Key naming styles:

- Codex and Copilot-style configs use sanitized keys such as `Context7_id_ABC123`
- Gemini is also exported with sanitized keys such as `Context7_id_ABC123`
- Claude-style configs use bracketed keys such as `Context7[id=ABC123]`
- Copilot sync also injects `tools: ["*"]` into each server entry for CLI compatibility
- Codex sync translates remote bearer `Authorization` headers into
  `bearer_token_env_var` entries for Codex-compatible remote auth
- this applies to any Codex remote MCP server using bearer auth, not only GitHub

For Codex remote bearer-auth servers, the referenced environment variable must
exist when you run `codex`.

## Safety Notes

- write commands may back up the DB if `backup_on_write` is enabled
- sync overwrites only the configured MCP server section, not the whole DB
- config files are written in place, so use version control or manual backups
  for high-risk changes

## Troubleshooting

`doctor` says the DB does not exist:

- confirm McpOne is installed
- confirm the configured `db_path`
- open McpOne once so its app container exists

`market list` is empty:

- confirm `/Applications/McpOne.app` exists
- confirm the configured `resources_dir`

`sync app` fails with “App has no config target”:

- the app record in McpOne does not have a config file path or config key
- fix the app record or create a custom app with `apps add-custom`

`import app` imports zero servers:

- verify the target file exists
- verify the configured root key such as `mcpServers` or `mcp_servers`
- verify the config file contains MCP server entries in object form

## Further Reading

- Command reference: [command-reference.md](command-reference.md)
- Architecture: [architecture.md](architecture.md)
- Database reference: [database-reference.md](database-reference.md)
- Developer guide: [developer-guide.md](developer-guide.md)
