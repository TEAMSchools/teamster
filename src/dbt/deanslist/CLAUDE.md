# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Source-system staging project for **Deanslist** (behavior management, homework
tracking, and student support platform). Produces staging and intermediate
models consumed by school-specific projects and `kipptaf`.

## Model Structure

```text
models/
  staging/     # contract-enforced, one model per Deanslist API endpoint
  intermediate/
```

All staging models have `contract: enforced: true`. The
`bigquery_external_connection_name` var is `null` here and set by consuming
projects.

## Cross-Project Usage

Referenced as a dbt package by `kippnewark`, `kippcamden`, and `kipptaf`.
Consuming school projects may disable specific models (e.g.,
`stg_deanslist__followups`) in their own `dbt_project.yml`.

## Model Conventions

See `src/dbt/CLAUDE.md` for per-layer requirements (contract enforcement,
uniqueness tests, SQL antipatterns) that apply to all dbt projects.
