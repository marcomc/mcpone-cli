# Architecture

## System Overview

`mcpone-cli` is a layered CLI around the McpOne desktop database and app-bundled
resource manifests.

Primary flow:

1. load runtime settings
2. open the McpOne SQLite database
3. optionally load market manifests from the installed app bundle
4. translate McpOne rows into JSON or TOML config entries
5. expose the operations as Typer commands

## Layer Model

### `config.py`

Responsibilities:

- default path resolution
- optional runtime config loading
- user-configurable DB path and resource path

Non-responsibilities:

- no database logic
- no config-sync mapping rules

### `models.py`

Responsibilities:

- typed dataclasses for app, cluster, server, and market entities

Non-responsibilities:

- no persistence
- no conversion logic

### `store.py`

Responsibilities:

- SQLite connections
- row-to-dataclass mapping
- JSON blob encoding and decoding
- narrow database writes
- DB backup creation

This is the canonical persistence layer.

### `formats.py`

Responsibilities:

- load JSON and TOML config maps
- write JSON and TOML config maps
- infer target key style
- build export-ready server objects
- parse imported server keys

This is the canonical config-format layer.

### `market.py`

Responsibilities:

- load app-bundled market manifests
- pick a connection variant
- materialize placeholders into concrete server values

This is the canonical market-install layer.

### `cli.py`

Responsibilities:

- user-facing command registration
- argument validation at the CLI boundary
- composition of store, format, and market operations
- Rich output rendering

Non-responsibilities:

- business logic should not drift into `cli.py` if it is reusable elsewhere

## Runtime Dependencies

The project relies on:

- Python stdlib `sqlite3`, `json`, `tomllib`
- `tomli_w` for TOML output
- `typer` for CLI UX
- `rich` for human-readable tables and JSON output

## Data Sources

### Live McpOne database

Used for:

- app definitions
- cluster definitions
- installed/imported server definitions

### App-bundled resource manifests

Used for:

- market catalog browsing
- market connection template materialization

### Agent config files

Used for:

- import into the McpOne database
- sync from the active cluster back out to agent tools

## Main Data Flows

### Inspection flow

```text
CLI -> store -> sqlite -> dataclasses -> Rich table / JSON output
```

### Cluster write flow

```text
CLI -> store -> update cluster membership blob -> commit
```

### Market install flow

```text
CLI
  -> market manifest loader
  -> connection selection
  -> placeholder materialization
  -> store.add_server(...)
  -> store.enable_servers(...)
```

### Import flow

```text
CLI
  -> resolve app config file and key
  -> formats.load_config_map(...)
  -> parse server keys
  -> store.add_server(...) for missing records
```

### Sync flow

```text
CLI
  -> app.active_cluster_id
  -> cluster.enabled_server_ids
  -> store.get_servers_by_ids(...)
  -> formats.enabled_servers_to_config(...)
  -> formats.write_config_map(...)
```

## Design Decisions

### The database is canonical

App config path, root key, and active cluster are taken from the McpOne DB.
They are not duplicated in runtime config.

### JSON blobs are first-class

Several important Core Data columns are actually UTF-8 JSON blobs.
The CLI treats them as structured data, not opaque binary.

### Key naming is target-dependent

The same server record may export with different names depending on the target
tool:

- bracketed keys such as `Server[id=ABC123]`
- sanitized keys such as `Server_id_ABC123`

### Narrow writes are preferred

The CLI mutates only the fields it has verified and documented.
This minimizes accidental drift from desktop-app expectations.

### Fixture-first testing

The live DB is for smoke checks, not for normal automated tests.
Automated tests rely on a minimal verified schema fixture.

## Extension Architecture

### Good extension pattern

- new persistence rule -> `store.py`
- new config mapping rule -> `formats.py`
- new market rule -> `market.py`
- new user flow -> `cli.py`
- new invariant -> docs + tests

### Bad extension pattern

- embedding SQL directly in `cli.py`
- duplicating config-path logic outside the DB
- writing undocumented table fields “because they seem related”

## Current Limits

- no hidden-server management commands
- no DB restore command
- no diff engine between DB and config files
- no dry-run mode for write commands
- no machine-readable JSON output mode for all commands

See also:

- [`feature-support-matrix.md`](feature-support-matrix.md)
- [`write-safety.md`](write-safety.md)
- [`config-sync-spec.md`](config-sync-spec.md)
