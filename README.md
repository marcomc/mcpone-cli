# mcpone-cli

`mcpone-cli` is a public macOS command-line interface for McpOne.
It manages the same core objects as the desktop app:

- apps
- clusters
- added/imported servers
- bundled market catalog entries
- sync to agent config files such as Codex, Claude, Gemini, Copilot, and VS Code

The implementation is grounded in first-party McpOne artifacts:

- the installed app bundle at `/Applications/McpOne.app`
- the live Core Data SQLite store used by McpOne
- first-party resource manifests shipped inside the app
- the App Store listing for the desktop app

## Features

- Inspect McpOne apps, clusters, and servers directly from the desktop database
- Add, update, and remove imported servers
- Enable or disable servers per cluster
- Create and manage clusters for an app
- Create custom app bindings to JSON or TOML MCP config files
- Read the bundled McpOne market catalog and install market entries into the DB
- Import servers from existing agent config files into McpOne
- Sync enabled cluster servers back out to agent config files
- Run a doctor report to verify DB path, app resources, and config targets

## Documentation Map

- Users: [`docs/user-guide.md`](docs/user-guide.md)
- Contributors: [`docs/developer-guide.md`](docs/developer-guide.md)
- Full command list: [`docs/command-reference.md`](docs/command-reference.md)
- Architecture and sync design: [`docs/architecture.md`](docs/architecture.md)
- McpOne database reference: [`docs/database-reference.md`](docs/database-reference.md)
- Feature support matrix: [`docs/feature-support-matrix.md`](docs/feature-support-matrix.md)
- Write safety: [`docs/write-safety.md`](docs/write-safety.md)
- Config sync spec: [`docs/config-sync-spec.md`](docs/config-sync-spec.md)
- Market install spec: [`docs/market-install-spec.md`](docs/market-install-spec.md)
- Testing guide: [`docs/testing-guide.md`](docs/testing-guide.md)
- Release workflow: [`docs/release-workflow.md`](docs/release-workflow.md)

## Requirements

- macOS
- Python 3.11+
- the official McpOne Desktop application must be installed to use this tool

`mcpone-cli` depends on first-party assets from the official desktop app:

- the live McpOne SQLite database
- the bundled market catalog in `/Applications/McpOne.app/Contents/Resources`

Without the official McpOne Desktop application installed, the CLI cannot read
or manage the real McpOne environment.

Default live DB path:

```text
~/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite
```

## Install

Check prerequisites first:

```bash
make check-deps
```

Then install:

```bash
git clone <repo-url>
cd mcpone-cli
make install
```

This follows the same pattern as your other local CLI projects:

- creates `.venv`
- installs the package into that virtualenv
- links the executable to `~/.local/bin/mcpone-cli`

For contributors, use:

```bash
make install-dev
```

`make check-deps` verifies:

- `python3` exists and is at least 3.11
- `/Applications/McpOne.app` exists
- `~/.local/bin` exists or can be created
- whether `~/.local/bin` is on `PATH`
- whether the McpOne SQLite database already exists

Run the CLI:

```bash
mcpone-cli --help
```

## Quick Start

List apps:

```bash
mcpone-cli apps list
```

Inspect a cluster:

```bash
mcpone-cli clusters show "Cluster A" --app Codex
```

List market tools:

```bash
mcpone-cli market list --category development
```

Install a market server into McpOne and enable it:

```bash
mcpone-cli market install Context7 --cluster "Cluster A" --app Codex
```

Sync the active cluster for Codex back to `~/.codex/config.toml`:

```bash
mcpone-cli sync app Codex
```

## Configuration

`mcpone-cli` reads optional runtime configuration from:

- `~/.config/mcpone-cli/config.toml`
- or the path given with `--config`

See [`config.toml.example`](config.toml.example) for supported keys.

## Design Basis

The project intentionally documents the McpOne-specific work that would
otherwise need to be rediscovered:

- which McpOne tables matter
- how cluster membership is stored
- how app config targets are mapped
- how bundled market entries are materialized
- which JSON and TOML formats have been verified locally

That material is captured in the docs above so future maintainers can extend the
tool without re-analyzing the desktop app from scratch.

## Quality Gates

Lint:

```bash
make lint
```

Test:

```bash
make test
```
