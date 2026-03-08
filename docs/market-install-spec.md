# Market Install Spec

## Purpose

This document defines how `market install` turns an app-bundled McpOne market
entry into a concrete `ZADDEDSERVER` row.

## Source Of Truth

The current CLI reads market metadata from the JSON manifests shipped in:

```text
/Applications/McpOne.app/Contents/Resources/*.json
```

It does not currently use `ZSERVER` as the primary market source.

## Market Entry Model

Each market tool may have:

- display metadata such as name, category, author, version
- one or more connection variants

Each connection may include:

- `type`
- `command`
- `args`
- `url`
- `headers`
- `parameters`

## Connection Selection

Selection order:

1. explicit `--connection` if provided
2. first `STDIO` connection
3. first `STREAMABLE_HTTP` connection
4. first available connection

## Placeholder Materialization

Placeholders look like:

```text
<VERSION>
<CONTEXT7_API_KEY>
<PROJECT_DIR>
```

Rules:

- `<VERSION>` defaults to the manifest version unless overridden
- required parameters must be provided or have defaults
- boolean parameters may emit flags/prefixes only when truthy
- inline placeholders inside strings are substituted directly

## Installed Server Mapping

The materialized connection becomes a `ZADDEDSERVER` row with:

- `ZSOURCE = market`
- `ZTYPE = connection.type`
- `ZCOMMAND = connection.command`
- `ZURL = materialized url`
- `ZARGS = materialized args`
- `ZHEADERS = materialized headers`
- `ZPARAMETERS = manifest parameter definitions`

After creation, the server ID is enabled in the target cluster.

## Known Limits

- no interactive prompting for missing parameters
- no validation against external services
- no advanced secret handling beyond plain passed values
- no deeper normalization of every market manifest quirk

## Contributor Rules

- keep market installs grounded in actual McpOne resource manifests
- if connection selection changes, document the precedence here
- add tests for every new placeholder or parameter behavior
