# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Finalsite** (school website and
communications platform). Staging-only project with no intermediate layer.

## Model Structure

```text
models/
  staging/     # materialized: table, contract: enforced: true
  sources.yml
```

Uses `cloud_storage_uri_base` and `local_timezone` vars (both `null` here, set
by consuming projects).

## Cross-Project Usage

Referenced by `kipptaf` only.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
