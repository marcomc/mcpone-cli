# Feature Support Matrix

## Purpose

This matrix maps McpOne desktop capabilities to current CLI support so
contributors can see what is already covered and what remains partial.

## Matrix

| McpOne Capability | Current CLI Support | Notes |
| --- | --- | --- |
| List apps | Full | `apps list`, `apps show` |
| Create custom app | Full | `apps add-custom` writes to DB |
| Switch active cluster | Full | `apps set-active-cluster` |
| List clusters | Full | `clusters list`, `clusters show` |
| Create cluster | Full | `clusters create` |
| Rename cluster | Full | `clusters rename` |
| Delete cluster | Full | `clusters delete` |
| List added servers | Full | `servers list`, `servers show` |
| Add server manually | Full | `servers add` |
| Update server | Full | `servers update` |
| Delete server | Full | `servers delete` |
| Enable/disable server in cluster | Full | `servers enable`, `servers disable` |
| Enable server across multiple clusters/apps at once | Full | `servers enable-many` |
| Inspect market catalog | Full | `market list`, `market show` via app resources |
| Install market tool | Full | `market install` for one selected connection |
| Import from target config file | Full | `import app`, `import file` |
| Sync active cluster to config | Full | `sync app`, `sync all` |
| Environment diagnostics | Full | `doctor`, `check-prereqs` |
| Hidden server management | None | DB field documented but no commands |
| Bookmark/file-access management | None | table documented but not used |
| Rich GUI workflows | None | intentionally out of scope for CLI |
| Dry-run DB writes | None | recommended future work |
| DB restore | None | recommended future work |
| DB/config diffing | None | recommended future work |
| JSON output for all commands | Partial | some commands emit JSON, not all |
| Full marketplace parity | Partial | app-bundled manifest path supported; deeper catalog internals not yet used |
| Every transport variant | Partial | primary connection materialization exists; not every edge case is covered |

## Contributor Guidance

When adding support, update this matrix in the same change so the repo stays
honest about actual coverage.
