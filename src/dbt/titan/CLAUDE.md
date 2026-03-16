# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Titan K12** (school meals / nutrition
management platform). Staging-only project.

## Model Structure

```text
models/
  staging/     # contract: enforced: true
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. The model
`stg_titan__income_form_data` is disabled in NJ school projects.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
