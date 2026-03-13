# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Pearson** state assessments — specifically
PARCC and NJGPA (New Jersey) standardized tests. Staging-only project.

## Model Structure

```text
models/
  staging/     # contract: enforced: true
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
