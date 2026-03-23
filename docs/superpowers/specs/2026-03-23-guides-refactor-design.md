# Design: Guides Refactor

**Date:** 2026-03-23 **Status:** Approved

## Problem

`docs/getting-started.md` has two issues:

1. **Monolith**: it contains a full Local Development section (install, Dagster,
   dbt prep, linting, testing) that belongs as a standalone guide alongside
   Codespaces, Dagster, and Google Sheets.
2. **Missing sidenav**: it carries `hide: navigation` in its frontmatter — a
   copy of the homepage behavior — which hides the sidenav on a page that is
   part of the Guides section nav.

A secondary issue: the filename `getting-started.md` lives at the root of
`docs/` but is placed under the Guides section in `mkdocs.yml`. The location and
the nav placement are mismatched.

## Goals

- `getting-started.md` becomes `docs/guides/index.md` — the section landing page
  for Guides, with the sidenav visible.
- The landing page contains only: Account Setup prose (GitHub, Google Workspace,
  dbt Cloud) and a routing table linking to all guides.
- Local Development content moves to its own guide at
  `docs/guides/local-development.md`.
- All navigation, cross-references, and documentation structure maps are updated
  consistently.

## Non-Goals

- No changes to guide content beyond what is required by the move.
- No changes to other sections (Reference, Troubleshooting, Automations).

## File Changes

| Action | Path                               | Notes                                                                                                                                                                                 |
| ------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create | `docs/guides/index.md`             | Account Setup + routing table                                                                                                                                                         |
| Create | `docs/guides/local-development.md` | Extracted from `getting-started.md`                                                                                                                                                   |
| Delete | `docs/getting-started.md`          | Replaced by `guides/index.md`                                                                                                                                                         |
| Update | `mkdocs.yml`                       | Enable `navigation.indexes` feature; remove `Getting Started: getting-started.md`; add `Local Development: guides/local-development.md`; add `guides/index.md` as section index entry |
| Update | `docs/README.md`                   | "Get started" section links to `getting-started.md` — update to `guides/`                                                                                                             |
| Update | `docs/troubleshooting/vscode.md`   | "See also" link points to `../getting-started.md` — update to `../guides/`                                                                                                            |
| Update | `docs/CLAUDE.md`                   | Update structure map: add `guides/index.md`, `guides/local-development.md`, and the previously missing `guides/codespaces.md`                                                         |

## `docs/guides/index.md` Structure

```markdown
# Guides

## Account Setup

### GitHub

...

### Google Workspace

...

### dbt Cloud

...

## Guides

| Guide                                     | Description |
| ----------------------------------------- | ----------- |
| [Codespaces](codespaces.md)               | ...         |
| [Local Development](local-development.md) | ...         |
| [Dagster](dagster.md)                     | ...         |
| [Google Sheets & Forms](google-sheets.md) | ...         |
```

No `hide:` frontmatter — the sidenav displays normally.

## `docs/guides/local-development.md` Structure

Extracted verbatim from the Local Development section of `getting-started.md`:

- Prerequisites (uv)
- Setup (install, run Dagster, validate definitions)
- dbt (prepare and package)
- Linting and formatting (Trunk, linter table)
- Testing (pytest examples)

## MkDocs Nav

Before:

```yaml
- Guides:
    - Getting Started: getting-started.md
    - Codespaces: guides/codespaces.md
    - Dagster: guides/dagster.md
    - Google Sheets & Forms: guides/google-sheets.md
```

After:

```yaml
- Guides:
    - guides/index.md
    - Codespaces: guides/codespaces.md
    - Local Development: guides/local-development.md
    - Dagster: guides/dagster.md
    - Google Sheets & Forms: guides/google-sheets.md
```

`guides/index.md` without a title key is the Material for MkDocs convention for
section index pages — the section header in the sidenav becomes a clickable link
to the index. This requires `navigation.indexes` to be enabled in `mkdocs.yml`
under `theme.features`.
