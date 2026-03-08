# Developer Guide

## Purpose

This guide is for developers who need to maintain or extend `mcpone-cli`
without re-analyzing McpOne Desktop from scratch.

Read this first, then use the linked deeper references:

- architecture:
  [`architecture.md`](architecture.md)
- database model:
  [`database-reference.md`](database-reference.md)
- command surface:
  [`command-reference.md`](command-reference.md)
- CLI support coverage:
  [`feature-support-matrix.md`](feature-support-matrix.md)
- write safety:
  [`write-safety.md`](write-safety.md)
- sync behavior:
  [`config-sync-spec.md`](config-sync-spec.md)
- market behavior:
  [`market-install-spec.md`](market-install-spec.md)
- testing workflow:
  [`testing-guide.md`](testing-guide.md)

## Canonical Sources

The project is grounded in first-party McpOne artifacts:

- `/Applications/McpOne.app`
- `/Applications/McpOne.app/Contents/Resources/*.json`
- `/Applications/McpOne.app/Contents/Resources/TOML_IMPLEMENTATION.md`
- the live McpOne SQLite database
- the official App Store listing for MCP One

If a behavior is unclear, prefer checking those sources over making a guess.

## Project Layout

- [`src/mcpone_cli/config.py`](../src/mcpone_cli/config.py)
  runtime settings and config file loading
- [`src/mcpone_cli/models.py`](../src/mcpone_cli/models.py)
  internal dataclasses
- [`src/mcpone_cli/store.py`](../src/mcpone_cli/store.py)
  SQLite repository and write logic
- [`src/mcpone_cli/formats.py`](../src/mcpone_cli/formats.py)
  JSON and TOML mapping rules
- [`src/mcpone_cli/market.py`](../src/mcpone_cli/market.py)
  market manifest loading and materialization
- [`src/mcpone_cli/cli.py`](../src/mcpone_cli/cli.py)
  Typer command wiring and user-facing flows
- [`tests/conftest.py`](../tests/conftest.py)
  fixture DB and fixture market catalog
- [`tests/test_e2e.py`](../tests/test_e2e.py)
  end-to-end CLI behavior tests

## Mental Model

The CLI is built around four concepts:

1. `AddedApp`
   Represents an integration target such as Codex or Claude CLI.
2. `Cluster`
   Represents a named set of enabled added server IDs for one app.
3. `AddedServer`
   Represents a concrete installed/imported MCP server definition.
4. `MarketTool`
   Represents an app-bundled marketplace entry with connection templates.

## Maintainer Workflow

Standard loop:

```bash
make check-prereqs
make install-dev
make lint
make test
```

Smoke check against the live environment:

```bash
mcpone-cli doctor
mcpone-cli apps list
```

## Documentation Duties

When behavior changes, update the relevant docs in the same change:

- user-facing command behavior:
  [`README.md`](../README.md),
  [`user-guide.md`](user-guide.md),
  [`command-reference.md`](command-reference.md)
- developer-facing design or invariants:
  [`architecture.md`](architecture.md),
  [`database-reference.md`](database-reference.md),
  [`write-safety.md`](write-safety.md),
  [`config-sync-spec.md`](config-sync-spec.md),
  [`market-install-spec.md`](market-install-spec.md)
- release-visible changes:
  [`CHANGELOG.md`](../CHANGELOG.md)
- future work or missing behavior:
  [`TODO.md`](../TODO.md)

## How To Extend The CLI

### Add a new command group

1. add the command implementation in [`cli.py`](../src/mcpone_cli/cli.py)
2. keep orchestration in `cli.py`, but data logic in lower layers
3. add fixture-backed tests
4. document the new commands in
   [`command-reference.md`](command-reference.md)

### Add a new database field or table

1. verify the live schema and actual desktop-app usage
2. document the table or field in
   [`database-reference.md`](database-reference.md)
3. extend [`store.py`](../src/mcpone_cli/store.py)
4. add fixture coverage
5. update write-safety notes if the field is mutable

### Add a new agent config format

1. document the target config structure in
   [`config-sync-spec.md`](config-sync-spec.md)
2. extend [`formats.py`](../src/mcpone_cli/formats.py)
3. add import and sync tests
4. update the feature matrix

### Add a new market behavior

1. confirm how the McpOne resource manifest expresses it
2. document the rule in
   [`market-install-spec.md`](market-install-spec.md)
3. extend [`market.py`](../src/mcpone_cli/market.py)
4. add coverage for placeholders and edge cases

## Development Rules

- keep the database as the canonical source for app config paths and active
  clusters
- keep write operations explicit and narrow
- do not silently broaden support claims
- do not add undocumented fallback behavior
- run lint after every modification
- prefer fixture DB tests over mutating the live McpOne database

## Common Failure Modes

- wrong Make target name:
  use `make help` and prefer `check-prereqs`
- `mcpone-cli` missing after install:
  verify `~/.local/bin` is on `PATH`
- sync/import failures:
  inspect `ZAIAGENTJSONFILEPATH` and `ZAIAGENTJSONKEY` in the app row
- broken fixture tests:
  confirm the fixture schema still matches the verified live tables
- malformed blob decoding:
  inspect the affected row directly in SQLite and document the new shape if real

## Suggested Reading Order For New Contributors

1. [`README.md`](../README.md)
2. [`feature-support-matrix.md`](feature-support-matrix.md)
3. [`architecture.md`](architecture.md)
4. [`database-reference.md`](database-reference.md)
5. [`config-sync-spec.md`](config-sync-spec.md)
6. [`testing-guide.md`](testing-guide.md)
