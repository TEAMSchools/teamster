---
title: Docusaurus Migration Design
date: 2026-03-23
status: approved
---

# Docusaurus Migration Design

## Context

MkDocs is in governance collapse. The original author returned after eight years
of absence and is driving MkDocs 2.0 in a direction that eliminates plugin
support, breaks all themes (including Material for MkDocs), changes config
format from YAML to TOML with no migration path, and operates under a closed
contribution model. The last stable release (1.6.1) was August 2024.

The Material for MkDocs team is launching Zensical as a drop-in replacement, but
Zensical launched in February 2026 and has unproven adoption. Docusaurus is
Meta-backed, widely adopted, actively maintained, and handles the current
feature set natively. Given the site is only ~12 pages, migration cost is low
and the stability payoff is high.

## Decision

Migrate from MkDocs + Material for MkDocs to **Docusaurus v3**, deployed to
GitHub Pages via the modern `actions/deploy-pages` workflow.

## Project Structure

The `docs/` directory becomes the Docusaurus project root. Content moves to
`docs/content/` (configured via `path: 'content'` in the docs plugin), keeping
all docs-related files — toolchain, config, and content — under one directory
without a `docs/docs/` redundancy.

```
docs/
  content/                   # markdown content (was: root docs/)
    reference/
    guides/
    troubleshooting/
    getting-started.md
    CONTRIBUTING.md
    CODE_OF_CONDUCT.md
    SECURITY.md
    SUPPORT.md
    superpowers/             # excluded from nav (specs + plans)
  src/
    pages/
      index.js               # React homepage (replaces README.md + hooks.py)
  static/
    img/                     # images (was: docs/images/)
  CLAUDE.md
  docusaurus.config.js
  sidebars.js
  package.json
```

Files removed:

- `mkdocs.yml` (project root)
- `docs/hooks.py`
- `docs/README.md` (content moves to `src/pages/index.js`)

## Content Migration

Syntax changes are minimal — only 4 content files require edits, plus
`reference/claude-code-security-hooks.md` which moves as-is (not in nav,
accessible by URL, same as today).

### Admonitions

MkDocs `!!!`/`???` syntax becomes Docusaurus `:::` syntax:

| Before                | After                                            |
| --------------------- | ------------------------------------------------ |
| `!!! note`            | `:::note`                                        |
| `!!! warning "title"` | `:::warning[title]`                              |
| `??? note "title"`    | `<details><summary>title</summary>...</details>` |

Affected files: `reference/architecture.md`, `guides/dagster.md`,
`troubleshooting/dbt.md`, `troubleshooting/dagster.md`.

### Emoji

One instance of a Material/FontAwesome shortcode:

- `troubleshooting/dagster.md`: `:fontawesome-solid-thumbs-up:` → 👍

### Images

All image references update from `images/` to `/img/` (Docusaurus serves
`static/` at the site root).

### Homepage

`docs/README.md` content (project intro, badge row, reference tables,
guides/troubleshooting tables) moves to `docs/src/pages/index.js` as a React
component or MDX page. The `hooks.py` trick for hiding nav/TOC is unnecessary —
`src/pages/` renders outside the docs layout entirely.

### No changes needed

- Fenced code blocks (Prism.js handles syntax highlighting natively)
- GFM checkboxes `- [ ]` / `- [x]` (supported via `remark-gfm`, included by
  default)
- All links, headings, tables, and inline formatting
- `{{ }}` Jinja syntax in dbt docs (all instances are inside fenced code blocks
  or inline code — not interpreted by MDX)

### MDX curly brace audit

Docusaurus renders content as MDX; `{` outside code blocks is treated as a JSX
expression. Every `{`/`}` occurrence in the current content has been checked and
all instances are inside fenced code blocks or inline code:

- `reference/dbt-conventions.md` — Jinja `{{ }}` in SQL/YAML code blocks
- `reference/adding-an-integration.md` — Python dict literals in code blocks
- `guides/google-sheets.md` — `{ STAGING_MODEL_NAME }`, `{SHEET_URL}`,
  `{NAMED_RANGE}`, `{SOURCE_NAME}` placeholder tokens in fenced code blocks

No bare curly braces exist in prose. No action required, but this should be
re-verified if new content is added before or during migration.

## Extension Mapping

All current MkDocs extensions map to native Docusaurus capabilities:

| MkDocs extension                  | Docusaurus                                           |
| --------------------------------- | ---------------------------------------------------- |
| `admonition` + `pymdownx.details` | Native admonitions (`:::note`, `:::warning`, etc.)   |
| `pymdownx.superfences`            | Prism.js, built-in                                   |
| `pymdownx.tasklist`               | `remark-gfm`, included by default                    |
| `pymdownx.emoji`                  | Replace one shortcode with Unicode; no plugin needed |
| `pymdownx.keys`                   | `<kbd>` HTML; not used in any content file           |
| `attr_list`                       | Not used in content; not needed                      |

No third-party remark/rehype plugins are required for the current feature set.

**Search**: Add `@docusaurus/plugin-search-local` for offline full-text search,
equivalent to MkDocs Material's built-in search. Avoids requiring an Algolia
account.

## Generated Content

`scripts/gen-automations-doc.py` generates `docs/reference/automations.md`
today. After migration, update the output path to
`docs/content/reference/automations.md`. No other changes to the script are
needed.

## CI/Deployment

Replace `.github/workflows/mkdocs-gh-deploy.yaml` with a new workflow using the
modern GitHub Pages deployment model (artifact-based, no `gh-pages` branch, no
`contents: write` permission).

```yaml
name: Docusaurus Deploy

on:
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - docs/**
      - "!docs/superpowers/**"

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
          cache: npm
          cache-dependency-path: docs/package-lock.json
      - run: npm ci
        working-directory: docs
      - run: npm run build
        working-directory: docs
      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs/build

  deploy:
    needs: build
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Trigger paths mirror the current workflow: any change under `docs/` except
`docs/superpowers/**`.

## Dependency Changes

- Remove `mkdocs-material` from `pyproject.toml`
  `[project.optional-dependencies] docs` group (remove the group entirely if
  nothing else uses it)
- Add `docs/package.json` with `@docusaurus/core`, `@docusaurus/preset-classic`,
  and `@docusaurus/plugin-search-local` as dependencies
- Add `docs/node_modules/` and `docs/.docusaurus/` to `.gitignore`

## Navigation

The current MkDocs `nav:` structure maps to a Docusaurus `sidebars.js` with one
intentional change: `Automations` moves from a top-level nav item (a Docusaurus
sidebar antipattern) into the Reference group, where it logically belongs.

```
Reference
  Architecture
  Adding an Integration
  IO Managers
  Fiscal Year & Partitioning
  dbt Conventions
  Automation Conditions
  Automations (generated)
Guides
  Getting Started
  Dagster
  Google Sheets & Forms
Troubleshooting
  Dagster
  dbt
  VS Code
```

`superpowers/` remains excluded from the sidebar (not listed in `sidebars.js`),
accessible by URL as today.

## Out of Scope

- Content rewrites or restructuring
- Adding new documentation
- Enabling Docusaurus versioning, blog, or MDX-heavy components
- Migrating `superpowers/` specs and plans to a different location
