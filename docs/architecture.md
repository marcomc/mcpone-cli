# Architecture

## Overview

`mcpone-cli` has a simple architecture:

1. load runtime settings
2. talk to the McpOne SQLite store
3. optionally load the bundled market catalog
4. convert between McpOne records and JSON/TOML agent config files
5. present commands via Typer

## Layer Breakdown

### `config.py`

Responsibilities:

- resolve default paths
- load optional config from TOML
- expose one `Settings` object

### `store.py`

Responsibilities:

- connect to the SQLite database
- convert rows into typed dataclasses
- create, update, and delete records
- manage cluster membership arrays
- create DB backups before writes when enabled

This file is the authoritative McpOne persistence layer.

### `market.py`

Responsibilities:

- load the McpOne resource catalog from app-bundled JSON files
- expose market entries as `MarketTool` and `MarketConnection`
- choose a connection template
- replace `<PLACEHOLDER>` values with concrete arguments

### `formats.py`

Responsibilities:

- load MCP server maps from JSON or TOML files
- write updated server maps back to disk
- infer whether a target app uses bracketed or sanitized keys
- translate a stored server into config-file form

### `cli.py`

Responsibilities:

- parse user arguments
- orchestrate store, format, and market operations
- render tables and JSON output

## Data Flow

### Read-only inspection

1. CLI command calls store method
2. store reads SQLite rows
3. rows become dataclasses
4. CLI renders Rich tables or JSON

### Market install

1. CLI loads market manifest files from the app bundle
2. selected market connection template is materialized with user parameters
3. store adds a new `ZADDEDSERVER` row
4. store enables that server ID for the target cluster

### Import from agent config

1. CLI resolves app config path and root key
2. format loader reads JSON or TOML
3. server keys are parsed to extract names and optional IDs
4. missing servers are inserted into `ZADDEDSERVER`

### Sync to agent config

1. CLI resolves the app's active cluster
2. enabled server IDs are loaded from the cluster
3. store resolves those IDs to servers
4. format layer maps those servers into JSON or TOML entries
5. file is written back to disk

## Key Compatibility Decisions

### Config key naming

Two styles are currently supported:

- bracketed: `Server Name[id=ABC123]`
- sanitized: `Server_Name_id_ABC123`

The tool infers style from the target app config path and key.

### JSON blobs inside SQLite

Several McpOne Core Data columns store JSON bytes rather than separate tables.

Examples:

- `ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA`
- `ZADDEDSERVER.ZARGS`
- `ZADDEDSERVER.ZENV`
- `ZADDEDSERVER.ZHEADERS`
- `ZADDEDSERVER.ZPARAMETERS`
- `ZADDEDSERVER.ZCUSTOMFIELDSBYAGENTDATA`

The store layer treats those as first-class JSON structures.

### Entity IDs

SQLite rows include Core Data entity metadata such as `Z_ENT`.
The tool reads existing values when possible and falls back to stable defaults in
fixture databases.

## Why Python

Python was chosen because it is the most convenient fit for this repo:

- excellent SQLite support in the stdlib
- simple JSON and TOML handling
- fast packaging for a public CLI
- straightforward test fixtures
- easy maintenance for contributors who are not Swift developers

## Extension Points

Likely future additions:

- `diff` layer between DB and config files
- structured JSON output mode
- hidden server support
- extra Core Data tables if new McpOne features need them
- shell completion and packaging automation
