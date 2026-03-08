# Write Safety

## Purpose

This document defines which commands mutate state, what they mutate, and which
safety assumptions contributors must preserve.

## Mutation Classes

### Database-only writes

- `apps add-custom`
- `apps set-active-cluster`
- `clusters create`
- `clusters rename`
- `clusters delete`
- `servers add`
- `servers update`
- `servers delete`
- `servers enable`
- `servers disable`
- `market install`
- `import app`
- `import file`

### Config-file-only writes

- `sync app`
- `sync all`

### Read-only commands

- `doctor`
- `apps list`
- `apps show`
- `clusters list`
- `clusters show`
- `servers list`
- `servers show`
- `market list`
- `market show`

## Safety Rules

- the McpOne DB is canonical for app and cluster metadata
- config sync must not invent app config targets outside the DB
- write only documented fields
- preserve unknown columns untouched
- prefer full replacement of documented JSON blobs over partial blob mutation
  inside opaque encodings
- back up the database before writes when configured

## Current Write Surface

The CLI currently writes only:

- `ZADDEDAPP`
- `ZCLUSTER`
- `ZADDEDSERVER`

It does not write:

- `ZSERVER`
- `ZFILEACCESSBOOKMARK`
- `Z_PRIMARYKEY`

## Risk Hotspots

### Cluster membership

Cluster membership is encoded as a JSON blob, not as relational rows.
If that blob is corrupted, the app may lose its enabled-server mapping.

### Sync overwrite behavior

`sync` writes the target MCP config section in place. It does not attempt
semantic merges beyond preserving other top-level file content via the existing
JSON/TOML rewrite strategy.

### Server deletion

Deleting a server also removes its ID from all clusters.
That behavior is intentional and should stay documented.

## Future Safety Improvements

- dry-run mode for write commands
- explicit restore command for DB backups
- config-file backup option before sync
- diff preview before sync or import
