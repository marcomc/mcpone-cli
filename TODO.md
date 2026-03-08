# TODO

## Next

- Add DB backup and restore commands with safe pre-write snapshots
- Add richer editing support for server headers, custom fields, and custom parameter metadata
- Add JSON output mode for every command for scripting workflows
- Add shell completion install helpers for `zsh`, `bash`, and `fish`

## Later

- Add launchd watcher mode to auto-sync after McpOne DB changes
- Add export/import bundles for moving app/cluster/server definitions between Macs
- Add `diff` commands to compare McpOne state against agent config files

## Propositions

- Add an interactive TUI for browsing apps, clusters, and market tools
- Add GitHub Actions smoke tests with fixture databases for public releases
- Add optional secrets redaction when printing configs or doctor reports
- [ ] Add target-client config reload hooks after sync
  Support triggering non-restart reload behavior in compatible MCP clients after `sync app` or `sync all`, so file rewrites can be applied without manual in-app refresh steps when the target client exposes a safe reload mechanism.
  Actions:
  - Identify which supported clients expose a documented reload command, IPC hook, or file-watch-based refresh path
  - Define a per-client capability matrix for `reload`, `reload-status`, and unsupported cases
  - Add an opt-in CLI flow that triggers reload only after a successful sync
  - Document safety constraints so the CLI never simulates unsupported GUI interactions as a hidden side effect
