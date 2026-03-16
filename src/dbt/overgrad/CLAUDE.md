# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Overgrad** (college counseling and
application tracking platform). Produces staging and intermediate models.

## Model Structure

```text
models/
  staging/     # contract: enforced: true
  intermediate/
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. School projects disable
`stg_overgrad__followings` and `stg_overgrad__schools` (not available for all
schools).

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
