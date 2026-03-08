# Changelog

## Unreleased

- Fixed remote header preservation during sync and Codex-specific bearer auth translation behavior for remote MCP servers

## 0.1.0 - 2026-03-08

- Initial public release scaffold for `mcpone-cli`
- Added Python package, Makefile, docs, config sample, and test harness
- Added McpOne SQLite repository access and market catalog loading
- Added CLI commands for apps, clusters, servers, market, import, sync, and doctor
- Fixed sync/import decoding for legacy McpOne JSON fields stored as SQLite `TEXT` instead of `BLOB`
- Added regression coverage for sync targets, config key styles, transport serialization, and import/sync round trips
- Added built-in Gemini/Copilot sync sanitization so external sanitizer agents are no longer required for those targets
- Fixed GitHub remote market install selection so parameterized `STREAMABLE_HTTP` installs materialize OAuth bearer arguments correctly
- Added Codex sync translation from bearer `Authorization` headers to `bearer_token_env_var` for remote MCP servers
