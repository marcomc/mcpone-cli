# Database Reference

## Scope

This document records the McpOne database behavior already verified for
`mcpone-cli`. Contributors should start here before inspecting the live DB.

## Default Database Path

```text
~/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite
```

## Verified Tables

The live DB currently exposes at least:

- `ZADDEDAPP`
- `ZADDEDSERVER`
- `ZCLUSTER`
- `ZSERVER`
- `ZFILEACCESSBOOKMARK`
- `Z_METADATA`
- `Z_MODELCACHE`
- `Z_PRIMARYKEY`

The CLI currently operates on:

- `ZADDEDAPP`
- `ZCLUSTER`
- `ZADDEDSERVER`

## `ZADDEDAPP`

Represents an app integration such as Codex, Claude, or a custom client.

Verified important columns:

- `Z_PK`
- `ZNAME`
- `ZID`
- `ZAIAGENTID`
- `ZACTIVECLUSTERID`
- `ZAIAGENTJSONFILEPATH`
- `ZAIAGENTJSONKEY`
- `ZAIAGENTPROJECTPATH`
- `ZEXPLANATION`
- `ZHIDDENADDEDSERVERIDSDATA`

Observed behavior:

- `ZNAME` is the user-visible app name
- `ZID` is the app UUID-like identifier
- `ZAIAGENTID` identifies the target agent family such as `codex` or `claude`
- `ZAIAGENTJSONFILEPATH` points to the managed config file
- `ZAIAGENTJSONKEY` points to the root object key such as `mcpServers` or
  `mcp_servers`
- `ZACTIVECLUSTERID` stores the current active cluster ID

## `ZCLUSTER`

Represents a named cluster belonging to one app.

Verified important columns:

- `Z_PK`
- `ZAPP`
- `ZID`
- `ZNAME`
- `ZENABLEDADDEDSERVERIDSDATA`

Observed behavior:

- `ZAPP` references `ZADDEDAPP.Z_PK`
- `ZID` is the cluster identifier
- `ZNAME` is the user-visible cluster name
- `ZENABLEDADDEDSERVERIDSDATA` is a UTF-8 JSON array of server IDs

Verified example behavior:

```json
["7J6VKW", "SUG610", "WTYCA2"]
```

This is the most important storage detail for cluster membership.

## `ZADDEDSERVER`

Represents an installed or imported MCP server definition.

Verified important columns:

- `Z_PK`
- `ZID`
- `ZNAME`
- `ZSOURCE`
- `ZTYPE`
- `ZCOMMAND`
- `ZURL`
- `ZVERSION`
- `ZARGS`
- `ZARGUMENT`
- `ZENV`
- `ZHEADERS`
- `ZPARAMETERS`
- `ZCUSTOMFIELDSBYAGENTDATA`

Observed behavior:

- `ZID` is the McpOne server ID
- `ZNAME` is the server display name
- `ZSOURCE` distinguishes values like `market` and `imported`
- `ZTYPE` is a connection type such as `STDIO`
- `ZCOMMAND` stores the executable command for stdio servers
- `ZURL` is used for HTTP-based connections
- `ZARGS`, `ZENV`, `ZHEADERS`, `ZPARAMETERS`, and custom fields are JSON blobs

## Blob Encoding Rules

The CLI treats the following columns as UTF-8 JSON:

- `ZENABLEDADDEDSERVERIDSDATA`
- `ZARGS`
- `ZARGUMENT`
- `ZENV`
- `ZHEADERS`
- `ZPARAMETERS`
- `ZCUSTOMFIELDSBYAGENTDATA`
- `ZHIDDENADDEDSERVERIDSDATA`

When decoding fails, the CLI falls back to empty structures rather than crashing.

## Entity Metadata

Core Data tables also include:

- `Z_ENT`
- `Z_OPT`
- timestamp fields such as `ZCREATEDAT` and `ZUPDATEDAT`

The CLI preserves the general Core Data row shape but only relies on a limited,
verified subset.

## Live Examples Observed During Implementation

Verified app bindings in the local McpOne DB included:

- Codex -> `~/.codex/config.toml` with key `mcp_servers`
- Claude CLI -> `~/.claude.json` with key `mcpServers`
- Gemini CLI -> `~/.gemini/settings.json` with key `mcpServers`
- Copilot -> `~/.copilot/mcp-config.json` with key `mcpServers`
- VSCode Copilot -> `.../Code/User/mcp.json` with key `servers`

This is why the CLI supports both TOML and JSON config targets.

## Safe Contribution Guidance

Before adding support for more fields or tables:

1. inspect the live DB schema
2. confirm the field is actively used by McpOne
3. document it here
4. add fixture coverage in tests

Do not assume every Core Data column is stable or needed by the CLI.
