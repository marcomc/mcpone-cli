# Release Workflow

## Purpose

This document defines the lightweight release and contribution workflow for the
project.

## Before Opening A PR Or Commit

Run:

```bash
make check-prereqs
make install-dev
make lint
make test
```

## When Behavior Changes

Update:

- [`CHANGELOG.md`](../CHANGELOG.md)
- user docs if user-facing
- developer docs if the invariants changed

## When New Functionality Is Added

Update:

- [`command-reference.md`](command-reference.md)
- [`feature-support-matrix.md`](feature-support-matrix.md)
- [`TODO.md`](../TODO.md) if anything remains partial

## Versioning

The project currently uses a simple package version in
[`pyproject.toml`](../pyproject.toml).

At minimum, a release should include:

- version bump
- changelog entry
- lint and test pass

## Pre-Commit Checklist

- code changes implemented
- docs updated
- no leftover scaffolding
- no unintended personal/local data in docs or config samples
- `make lint` passes
- `make test` passes
