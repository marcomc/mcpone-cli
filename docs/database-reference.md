# Database Reference

## Purpose

This document is the canonical database guide for `mcpone-cli`.

It exists so future contributors do not need to rediscover:

- which McpOne tables matter
- how rows relate to each other
- which columns are plain text versus JSON blobs
- how app config targets are modeled
- how cluster membership is encoded
- which writes are safe for this CLI to perform

The notes below are grounded in the verified live schema of the installed
McpOne desktop application.

## Database Location

Default database path:

```text
~/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite
```

This is a Core Data SQLite store used by the desktop app.

## Verified Tables

The live database currently exposes at least:

- `ZADDEDAPP`
- `ZADDEDSERVER`
- `ZCLUSTER`
- `ZSERVER`
- `ZFILEACCESSBOOKMARK`
- `Z_METADATA`
- `Z_MODELCACHE`
- `Z_PRIMARYKEY`

The CLI currently reads or writes:

- `ZADDEDAPP`
- `ZCLUSTER`
- `ZADDEDSERVER`

The CLI currently only documents, but does not modify:

- `ZSERVER`
- `ZFILEACCESSBOOKMARK`

## Schema Snapshot

Verified schema summary:

```sql
CREATE TABLE ZADDEDAPP (
  Z_PK INTEGER PRIMARY KEY,
  Z_ENT INTEGER,
  Z_OPT INTEGER,
  ZHASFILEACCESS INTEGER,
  ZRENAMED INTEGER,
  ZCREATEDAT TIMESTAMP,
  ZACTIVECLUSTERID VARCHAR,
  ZAIAGENTID VARCHAR,
  ZAIAGENTJSONFILEPATH VARCHAR,
  ZAIAGENTJSONKEY VARCHAR,
  ZAIAGENTPROJECTPATH VARCHAR,
  ZEXPLANATION VARCHAR,
  ZID VARCHAR,
  ZNAME VARCHAR,
  ZUPDATEDAT VARCHAR,
  ZHIDDENADDEDSERVERIDSDATA BLOB
);

CREATE TABLE ZCLUSTER (
  Z_PK INTEGER PRIMARY KEY,
  Z_ENT INTEGER,
  Z_OPT INTEGER,
  ZAPP INTEGER,
  ZCREATEDAT TIMESTAMP,
  ZUPDATEDAT TIMESTAMP,
  ZID VARCHAR,
  ZNAME VARCHAR,
  ZENABLEDADDEDSERVERIDSDATA BLOB
);

CREATE TABLE ZADDEDSERVER (
  Z_PK INTEGER PRIMARY KEY,
  Z_ENT INTEGER,
  Z_OPT INTEGER,
  ZCREATEDAT TIMESTAMP,
  ZUPDATEDAT TIMESTAMP,
  ZCOMMAND VARCHAR,
  ZID VARCHAR,
  ZNAME VARCHAR,
  ZSERVERID VARCHAR,
  ZSOURCE VARCHAR,
  ZTYPE VARCHAR,
  ZURL VARCHAR,
  ZVERSION VARCHAR,
  ZARGS BLOB,
  ZARGUMENT BLOB,
  ZCUSTOMFIELDSBYAGENTDATA BLOB,
  ZENV BLOB,
  ZHEADERS BLOB,
  ZPARAMETERS BLOB
);

CREATE TABLE ZSERVER (
  Z_PK INTEGER PRIMARY KEY,
  Z_ENT INTEGER,
  Z_OPT INTEGER,
  ZEDITVERSION INTEGER,
  ZGITHUBSTAR INTEGER,
  ZORDER INTEGER,
  ZAUTHOR VARCHAR,
  ZCATEGORY VARCHAR,
  ZEXPLANATION VARCHAR,
  ZGITHUBURL VARCHAR,
  ZID VARCHAR,
  ZNAME VARCHAR,
  ZVERSION VARCHAR,
  ZCONNECTIONDATA BLOB,
  ZPACKAGEURL VARCHAR,
  ZAVAILABLEVERSIONSDATA BLOB
);

CREATE TABLE ZFILEACCESSBOOKMARK (
  Z_PK INTEGER PRIMARY KEY,
  Z_ENT INTEGER,
  Z_OPT INTEGER,
  ZAPPID VARCHAR,
  ZBOOKMARKDATA VARCHAR,
  ZCREATEDAT VARCHAR,
  ZFILEPATH VARCHAR,
  ZID VARCHAR,
  ZUPDATEDAT VARCHAR
);
```

## Core Data Conventions

All important rows include Core Data metadata columns:

- `Z_PK`: row primary key used for local relations
- `Z_ENT`: Core Data entity identifier
- `Z_OPT`: optimistic locking/version field

Timestamp fields vary by table and are not perfectly uniform:

- some are stored as `TIMESTAMP`
- some are stored as `VARCHAR`
- app-created values observed in this project use Apple epoch time for numeric
  timestamp fields

The CLI currently preserves the existing row shape and only touches fields it
has verified.

## Table Guide

### `ZADDEDAPP`

`ZADDEDAPP` represents an application integration managed by McpOne.

Examples:

- Codex
- Claude
- Claude CLI
- Gemini CLI
- Copilot
- VSCode Copilot
- custom integrations

Important columns:

- `Z_PK`
  internal primary key used by `ZCLUSTER.ZAPP`
- `ZID`
  stable app identifier, typically UUID-like
- `ZNAME`
  user-visible app name
- `ZAIAGENTID`
  agent family identifier such as `codex`, `claude`, or `custom`
- `ZACTIVECLUSTERID`
  current active cluster ID for this app
- `ZAIAGENTJSONFILEPATH`
  target config file path for sync/import
- `ZAIAGENTJSONKEY`
  root config key such as `mcpServers`, `mcp_servers`, or `servers`
- `ZAIAGENTPROJECTPATH`
  optional project path for app-specific behavior
- `ZEXPLANATION`
  short description shown in the UI
- `ZHIDDENADDEDSERVERIDSDATA`
  JSON blob of hidden added server IDs
- `ZHASFILEACCESS`
  boolean-ish field used by the desktop app
- `ZRENAMED`
  boolean-ish field used by the desktop app

Operational meaning:

- this table is the canonical source for app-to-config-file mapping
- if an app lacks `ZAIAGENTJSONFILEPATH` or `ZAIAGENTJSONKEY`, sync/import
  cannot work for that app
- `ZACTIVECLUSTERID` determines which cluster is exported by `sync app`

### `ZCLUSTER`

`ZCLUSTER` represents a named server set attached to one app.

Important columns:

- `Z_PK`
  internal primary key
- `ZAPP`
  foreign key-like link to `ZADDEDAPP.Z_PK`
- `ZID`
  cluster ID used by `ZADDEDAPP.ZACTIVECLUSTERID`
- `ZNAME`
  user-visible cluster name
- `ZENABLEDADDEDSERVERIDSDATA`
  JSON array blob of enabled server IDs

Operational meaning:

- this table models cluster membership entirely by server ID list
- clusters do not duplicate full server definitions
- one app can have multiple clusters
- only one cluster is active per app

Verified blob example:

```json
["7J6VKW", "SUG610", "WTYCA2"]
```

### `ZADDEDSERVER`

`ZADDEDSERVER` stores concrete, usable MCP server definitions.

This is the main table that the CLI edits.

Important columns:

- `Z_PK`
  internal primary key
- `ZID`
  stable McpOne added server ID
- `ZNAME`
  display name
- `ZSOURCE`
  source classification such as `market` or `imported`
- `ZTYPE`
  connection type, usually `STDIO` or another transport label
- `ZCOMMAND`
  executable used for stdio servers
- `ZURL`
  optional remote endpoint for HTTP-based connections
- `ZVERSION`
  chosen version string
- `ZSERVERID`
  currently observed as empty in CLI-managed records
- `ZARGS`
  JSON blob of command arguments
- `ZARGUMENT`
  duplicate argument blob retained for compatibility with the app schema
- `ZENV`
  JSON blob of environment variables
- `ZHEADERS`
  JSON blob of request headers
- `ZPARAMETERS`
  JSON blob of connection parameter definitions
- `ZCUSTOMFIELDSBYAGENTDATA`
  JSON blob for agent-specific metadata

Operational meaning:

- cluster membership references `ZID`, not `Z_PK`
- `ZCOMMAND` plus `ZARGS` define stdio launch behavior
- `ZURL` plus headers and parameters define network-oriented servers
- `ZSOURCE` is useful for separating market-installed and imported/custom items

### `ZSERVER`

`ZSERVER` appears to represent the bundled or catalog-style server marketplace.

The current CLI does not query this table directly because the installed app
also ships richer first-party JSON manifests in the application bundle, which
are easier to consume and version independently.

Important columns:

- `ZID`
  server catalog identifier
- `ZNAME`
  catalog display name
- `ZAUTHOR`
  author string
- `ZCATEGORY`
  catalog category
- `ZEXPLANATION`
  descriptive text
- `ZGITHUBURL`
  project URL
- `ZPACKAGEURL`
  package source URL
- `ZVERSION`
  current version
- `ZCONNECTIONDATA`
  connection template blob
- `ZAVAILABLEVERSIONSDATA`
  available version list blob
- `ZGITHUBSTAR`
  star count cache
- `ZEDITVERSION`
  app-side edit version / schema version marker
- `ZORDER`
  ordering field for the UI

Operational meaning:

- treat this as catalog data, not as active installed server state
- prefer app-bundled JSON resources over direct writes here unless future work
  proves the table is the safer source

### `ZFILEACCESSBOOKMARK`

`ZFILEACCESSBOOKMARK` appears to store file access bookmarks for app integrations.

Important columns:

- `ZAPPID`
  app identifier string
- `ZFILEPATH`
  file path associated with the bookmark
- `ZBOOKMARKDATA`
  bookmark payload
- `ZID`
  bookmark ID

Operational meaning:

- this is relevant if future work needs to manage sandboxed file access
- the current CLI does not write this table

## Relationships

The most important relationships are:

```text
ZADDEDAPP.Z_PK           -> ZCLUSTER.ZAPP
ZADDEDAPP.ZACTIVECLUSTERID -> ZCLUSTER.ZID
ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA[*] -> ZADDEDSERVER.ZID
```

There is no join table between clusters and servers.
Membership is encoded directly in the JSON array blob on `ZCLUSTER`.

## Blob Encoding Rules

The following columns are treated as UTF-8 JSON blobs by the CLI:

- `ZADDEDAPP.ZHIDDENADDEDSERVERIDSDATA`
- `ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA`
- `ZADDEDSERVER.ZARGS`
- `ZADDEDSERVER.ZARGUMENT`
- `ZADDEDSERVER.ZENV`
- `ZADDEDSERVER.ZHEADERS`
- `ZADDEDSERVER.ZPARAMETERS`
- `ZADDEDSERVER.ZCUSTOMFIELDSBYAGENTDATA`

Typical decoded shapes:

- hidden/enabled IDs: `list[str]`
- args: `list[str]`
- env: `dict[str, str]`
- headers: `dict[str, str]`
- parameters: `dict[str, object]`
- custom fields: `dict[str, object]`

Failure handling in the CLI:

- invalid or empty blob data falls back to an empty structure
- the CLI does not crash on malformed blobs
- the CLI only rewrites blobs it explicitly manages

## Field Semantics Used by the CLI

### App selection

The CLI resolves an app by:

- `ZNAME`
- or `ZID`

### Cluster selection

The CLI resolves a cluster by:

- `ZNAME`
- or `ZID`

### Server selection

The CLI resolves a server by:

- `ZNAME`
- or `ZID`

### Config sync mapping

These fields are essential:

- `ZADDEDAPP.ZAIAGENTJSONFILEPATH`
- `ZADDEDAPP.ZAIAGENTJSONKEY`
- `ZADDEDAPP.ZACTIVECLUSTERID`
- `ZCLUSTER.ZENABLEDADDEDSERVERIDSDATA`

The sync process is:

1. find app
2. read active cluster ID from `ZADDEDAPP`
3. load that cluster
4. decode enabled server ID array
5. fetch matching `ZADDEDSERVER` rows
6. convert to JSON or TOML
7. write the target config file

## Safe Write Patterns

The CLI currently performs only these write classes:

- create `ZADDEDAPP`
- create `ZCLUSTER`
- update `ZADDEDAPP.ZACTIVECLUSTERID`
- rename or delete `ZCLUSTER`
- create/update/delete `ZADDEDSERVER`
- replace `ZENABLEDADDEDSERVERIDSDATA`

Safe principles:

- create a DB backup before writes when configured
- prefer updating a narrow set of known-good columns
- preserve unknown columns untouched
- never rewrite catalog tables like `ZSERVER` unless explicitly designed and
  tested later

## Timestamp Handling

Numeric Core Data timestamp fields are currently written using Apple epoch time:

```text
unix_time - 978307200
```

The CLI uses this for fields such as:

- `ZCREATEDAT`
- `ZUPDATEDAT` where the column stores numeric timestamps

Some app fields, especially on `ZADDEDAPP`, may store update timestamps as
string values. The CLI preserves the existing pattern it has already implemented
rather than forcing one universal representation.

## Primary Key Strategy

For inserts, the CLI currently derives:

- `Z_PK` as `MAX(Z_PK) + 1`
- `Z_ENT` from the existing table if possible
- fallback entity IDs only in fixture databases

This is intentionally simple and matches the verified needs of the current CLI.

If future work adds more tables, verify whether `Z_PRIMARYKEY` must also be
updated for correctness in those flows.

## Example SQL Queries

### List apps with their config targets

```sql
SELECT
  ZNAME,
  ZID,
  ZAIAGENTID,
  ZAIAGENTJSONFILEPATH,
  ZAIAGENTJSONKEY,
  ZACTIVECLUSTERID
FROM ZADDEDAPP
ORDER BY ZNAME;
```

### List clusters for one app

```sql
SELECT
  c.ZNAME,
  c.ZID,
  c.ZAPP,
  c.ZENABLEDADDEDSERVERIDSDATA
FROM ZCLUSTER c
JOIN ZADDEDAPP a ON a.Z_PK = c.ZAPP
WHERE a.ZNAME = 'Codex'
ORDER BY c.ZNAME;
```

### List active servers for an app

This requires decoding the enabled ID blob in application code, not plain SQL
alone, because membership is stored as JSON text inside a blob.

### Inspect added server launch data

```sql
SELECT
  ZNAME,
  ZID,
  ZSOURCE,
  ZTYPE,
  ZCOMMAND,
  ZURL,
  ZARGS,
  ZENV,
  ZHEADERS,
  ZPARAMETERS
FROM ZADDEDSERVER
ORDER BY ZNAME;
```

## Python Access Pattern

The store layer in `mcpone-cli` follows this pattern:

1. connect with `sqlite3`
2. set `row_factory = sqlite3.Row`
3. map rows into dataclasses
4. decode JSON blobs into Python structures
5. write back only the narrow fields the CLI owns

That implementation lives in:

- [`src/mcpone_cli/store.py`](../src/mcpone_cli/store.py)

## What Developers Should Not Assume

- do not assume every Core Data table matters to MCP operations
- do not assume every blob is opaque binary; several are JSON bytes
- do not assume `ZSERVER` is the only market source; the app bundle also ships
  authoritative resource JSON files
- do not assume config paths belong in external config; the DB is canonical
- do not assume `ZSERVERID` on `ZADDEDSERVER` is the primary identity field;
  `ZID` is the field used by current cluster membership

## Future Investigation Areas

Areas worth deeper study if the project grows:

- whether `ZPRIMARYKEY` needs coordinated updates for more advanced inserts
- whether `ZFILEACCESSBOOKMARK` is required for any write path on sandboxed apps
- whether `ZSERVER.ZCONNECTIONDATA` can safely replace the app-bundled JSON
  market manifests
- whether hidden server IDs in `ZHIDDENADDEDSERVERIDSDATA` should be surfaced by
  the CLI
- whether `ZARGUMENT` and `ZARGS` have distinct semantic meaning in newer app
  versions

## Contribution Checklist

Before changing database behavior:

1. inspect the live schema
2. confirm the target field is actively used by McpOne
3. document the change here
4. add fixture coverage in tests
5. run `make lint`
6. run `make test`

That process should keep the CLI conservative, transparent, and maintainable.
