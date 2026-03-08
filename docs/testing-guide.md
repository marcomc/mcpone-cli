# Testing Guide

## Purpose

This document explains how to test `mcpone-cli` safely and consistently.

## Test Layers

### Lint

```bash
make lint
```

Covers:

- Ruff static checks
- Ruff formatting checks
- Markdown linting

### Automated tests

```bash
make test
```

Covers:

- fixture database behavior
- fixture market install flow
- import flow
- sync flow
- end-to-end CLI behavior

### Live smoke checks

Run only against your local McpOne environment:

```bash
mcpone-cli doctor
mcpone-cli apps list
mcpone-cli clusters list --app Codex
```

## Why Fixture-First

The real McpOne database is personal application state.
Automated tests should not mutate it.

The project therefore uses:

- a temporary SQLite fixture database
- temporary market manifests
- `CliRunner` for process-like command tests

## Current Fixture Coverage

Implemented in:

- [`tests/conftest.py`](../tests/conftest.py)
- [`tests/test_e2e.py`](../tests/test_e2e.py)

The fixture schema is intentionally small and only includes verified columns
used by the current CLI.

## When Adding Tests

- prefer user-visible CLI tests
- add fixture schema fields only when they are needed
- avoid coupling tests to unverified desktop-app behavior
- keep one test per main workflow when possible

## Recommended Manual Checks

After significant DB or sync changes:

```bash
make check-prereqs
make install-dev
make lint
make test
mcpone-cli doctor
mcpone-cli apps list
```

If the change touches sync:

```bash
mcpone-cli sync app Codex
```

If the change touches market install:

```bash
mcpone-cli market list --category development
```

## Things Not To Do In Tests

- do not mutate the live McpOne SQLite file in automated tests
- do not assume external APIs are available
- do not rely on exact market catalog contents unless using fixture manifests
