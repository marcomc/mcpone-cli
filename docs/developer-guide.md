# Developer Guide

## Purpose

This document is for contributors who need to extend `mcpone-cli` without
repeating the original McpOne reverse-engineering work.

The important point is simple:

- the CLI is grounded in McpOne first-party artifacts
- the DB model and config sync conventions are already documented here
- future work should build on these references, not rediscover them

## Canonical Sources

The project was derived from the following first-party sources:

- the installed McpOne app bundle at
  `/Applications/McpOne.app`
- the bundled resource manifests under
  `/Applications/McpOne.app/Contents/Resources/*.json`
- the bundled TOML implementation note at
  `/Applications/McpOne.app/Contents/Resources/TOML_IMPLEMENTATION.md`
- the live McpOne SQLite database at
  `~/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite`
- the official App Store listing for MCP One

When changing behavior, prefer checking these artifacts first.

## Project Layout

- [`src/mcpone_cli/config.py`](../src/mcpone_cli/config.py)
  runtime settings and config file loading
- [`src/mcpone_cli/models.py`](../src/mcpone_cli/models.py)
  internal dataclasses
- [`src/mcpone_cli/store.py`](../src/mcpone_cli/store.py)
  SQLite repository for `ZADDEDAPP`, `ZCLUSTER`, and `ZADDEDSERVER`
- [`src/mcpone_cli/market.py`](../src/mcpone_cli/market.py)
  market catalog loading and connection materialization
- [`src/mcpone_cli/formats.py`](../src/mcpone_cli/formats.py)
  JSON/TOML config parsing and writing
- [`src/mcpone_cli/cli.py`](../src/mcpone_cli/cli.py)
  Typer command registration and orchestration
- [`tests/conftest.py`](../tests/conftest.py)
  fixture database and resource manifests
- [`tests/test_e2e.py`](../tests/test_e2e.py)
  end-to-end CLI tests

## Mental Model

There are four major concepts:

1. `AddedApp`
   A client integration such as Codex, Claude, Gemini CLI, or a custom app.
   It points to a config file path, a root key, and an active cluster ID.

2. `Cluster`
   A named grouping of enabled server IDs for an app.
   McpOne stores enabled servers as a JSON array blob in
   `ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA`.

3. `AddedServer`
   A concrete MCP server definition with command, args, env, headers, version,
   source, type, and optional URL.

4. `MarketTool`
   A catalog entry shipped in McpOne resources.
   It may contain multiple connection templates such as `STDIO` or
   `STREAMABLE_HTTP`.

## Supported Behaviors

The CLI currently implements:

- app inspection
- custom app creation
- cluster creation, rename, deletion, inspection
- active cluster switching
- server listing, inspection, add, update, delete
- cluster server enable and disable
- market catalog list and show
- market tool install into McpOne
- config import into McpOne
- config sync from McpOne to agent files
- environment diagnostics

If you add a new feature, update:

- [`README.md`](../README.md)
- [`docs/user-guide.md`](user-guide.md)
- [`docs/command-reference.md`](command-reference.md)
- [`CHANGELOG.md`](../CHANGELOG.md)

## Database Model

See the full reference in [database-reference.md](database-reference.md).

The key verified tables are:

- `ZADDEDAPP`
- `ZCLUSTER`
- `ZADDEDSERVER`

Important field behavior already verified:

- `ZADDEDAPP.ZAIAGENTJSONFILEPATH` stores the target config path
- `ZADDEDAPP.ZAIAGENTJSONKEY` stores the config root key
- `ZADDEDAPP.ZACTIVECLUSTERID` stores the active cluster ID
- `ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA` stores JSON bytes for enabled server IDs
- `ZADDEDSERVER.ZARGS`, `ZENV`, `ZHEADERS`, `ZPARAMETERS`,
  `ZCUSTOMFIELDSBYAGENTDATA` are JSON blobs

## Format Rules

See the full reference in [architecture.md](architecture.md).

Current format decisions:

- TOML files are read and written with `tomllib` plus `tomli_w`
- JSON files are read and written with the stdlib `json` module
- Codex-style files use `mcp_servers`
- most other current agent files use `mcpServers`
- key naming is either bracketed or sanitized depending on the target app

## Local Development Workflow

Create the environment:

```bash
make install-dev
```

Run lint:

```bash
make lint
```

Run tests:

```bash
make test
```

Run the CLI against the live environment:

```bash
mcpone-cli doctor
mcpone-cli apps list
```

## Testing Strategy

The tests intentionally avoid mutating the live McpOne DB.

Instead they use:

- a temporary SQLite fixture database with the verified schema subset
- temporary resource JSON files for a small market catalog
- `typer.testing.CliRunner` for end-to-end command execution

When adding features:

- prefer a fixture-first test
- use the live DB only for manual smoke checks
- keep end-to-end tests focused on user-visible behavior

## Contribution Rules

- keep write operations explicit
- preserve current first-party-compatible field names and config semantics
- do not silently broaden support claims beyond what has been verified
- update docs when behavior or assumptions change
- run lint after every modification

## Recommended Next Contributions

- implement safe DB restore support
- add JSON output mode for automation consumers
- add richer handling for hidden servers and custom fields
- add diff and dry-run commands for sync
- add coverage for more market connection variants
