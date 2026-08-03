# Cube Semantic-Layer API Reference and Field Catalog — Design

Issue: [#4438](https://github.com/TEAMSchools/teamster/issues/4438)

## Problem

The Cube semantic layer (`src/cube/`) is the governed query surface for KIPP
TEAM & Family metrics, but it has no consumer-facing documentation. Three
audiences need it and today have nothing:

- **External / API developers** hitting the REST or SQL API directly.
- **Internal dashboard / BI builders** (Superset, Tableau) choosing fields.
- **Claude MCP users** asking natural-language questions through the connector.

They differ only in entry point. All three need the same core facts: which views
exist, what fields each exposes (type, description, access tier), and how to
authenticate and shape a query. The existing guides
([`docs/guides/cube.md`](../../guides/cube.md),
[`docs/guides/claude-cube-connector.md`](../../guides/claude-cube-connector.md))
cover the internal dev workflow and connector setup — neither is a field
reference nor an API reference.

## Goals

- One documentation set, under the existing MkDocs Cube docs area, serving all
  three audiences from shared content with role-specific entry points.
- A **field catalog** that is **generated from the Cube model** so it never
  drifts and updates automatically when cubes or views are added.
- A **hand-written API guide** for the stable narrative (auth, query format,
  entry points) that rarely changes when a view is added.
- Executable by smaller models: deterministic generator, golden-file test,
  explicit per-file tasks, a clear CI pass/fail signal.

## Non-goals

- No new public hosting infrastructure. The docs publish through the existing
  `mkdocs gh-deploy` pipeline (GitHub Pages) on merge to `main`.
- No changes to the Cube model, access policies, or `cube.js` security.
- No OpenAPI/Swagger spec. Cube's `/meta` is the schema contract; we render a
  human catalog from the model rather than introducing a second spec format.
- No small-cell suppression or new demographic views (tracked separately in
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237)).

## Architecture

Two artifacts, split along the axis that matters — auto-generated vs. stable.

```text
src/cube/model/
  cubes/**/*.yml   ─┐
  views/**/*.yml   ─┤ parse + resolve
                    ▼
        scripts/generate_cube_reference.py
                    │  (optional: --verify-against-meta → /meta)
                    ▼
   docs/reference/cube-data-catalog.md   ← GENERATED, committed, CI-enforced
   docs/guides/cube-api.md               ← HAND-WRITTEN narrative
                    │
                    ▼
        mkdocs gh-deploy (existing) → GitHub Pages
```

### Component 1 — generated field catalog

`docs/reference/cube-data-catalog.md`. The data dictionary. Regenerated from
source; a banner at the top marks it generated and names the command. One
section per view so the page auto-grows with zero `mkdocs.yml` nav edits when a
view is added (MkDocs Material renders the heading tree as a sidebar TOC, giving
the traditional API-reference jump-link feel; `toc.integrate` surfaces sections
in the left nav).

Per-view layout:

```text
## <view name>
<view description>

### Access
<who can read it, row-level scoping field, whether PII is exposed>

### Measures
| Name | Type | Description |

### Dimensions   (grouped by folder)
#### <folder name>
| Name | Type | Description |
```

### Component 2 — hand-written API guide

`docs/guides/cube-api.md`. Stable prose. Sections:

- **Overview** and three "start here" entry points (external API dev · dashboard
  / BI builder · Claude MCP user), each routing to the shared core.
- **Authentication** — HS256 JWT whose payload carries the `email` claim; base
  URLs for REST, SQL, and MCP; how identity resolves to access (link to the
  access-model summary in `cube.md`).
- **Query format** — `measures`, `dimensions`, `filters`, `timeDimensions`,
  `order`, `limit`; the named filter operators (not SQL); the academic-year
  convention (start-year integer; `academic_year` 2025 = SY26).
- **Error handling** — 403 hidden-member, default-deny (zero rows), and the
  whole-query block behavior when a requested field is outside the caller's
  tier.
- **Worked example per audience** — a REST `curl`, a SQL-API `psycopg2` snippet,
  and a natural-language MCP prompt, each returning the same figure so the three
  paths are visibly equivalent.
- Links to the field catalog for all field-level detail (kept out of the guide
  to avoid duplication).

### Component 3 — the generator

`scripts/generate_cube_reference.py`, mirroring
[`scripts/generate_marts_reference.py`](../../../scripts/generate_marts_reference.py):
PEP-723 inline script metadata, `pyyaml` dependency, `--output` argument, no
network access on the default path.

Pipeline:

1. **Parse cubes** — glob `src/cube/model/cubes/**/*.yml`. Build an index keyed
   by cube `name`; for each, record every dimension and measure with `name`,
   `type`, `description`, `primary_key`, and `public`. **Resolve `extends:`
   chains** — a cube with `extends: <parent>` (e.g.
   `staff_manager extends staff`) inherits all of the parent's members, with its
   own definitions winning. Without this, members exposed through an aliased
   cube fail to resolve (confirmed by the design spike).
2. **Parse views** — glob `src/cube/model/views/**/*.yml`. For each view record
   `description`, the `cubes[]` includes (each with `join_path`, `prefix`,
   `includes[]`), `meta.folders`, and `access_policy`.
3. **Resolve exposed members** — for each include, look up the member on the
   cube named by the last segment of `join_path`. Compute the exposed name via
   the prefix rule (documented in
   [`src/cube/CLAUDE.md`](../../../src/cube/CLAUDE.md)):
   `<last-join_path-segment>_<member>` when `prefix: true`, else the bare member
   name. Classify measure vs. dimension from the source cube. Pull `type` and
   `description`. A member with no description renders an explicit placeholder
   so gaps are visible (and lintable) rather than silent.
4. **Derive access summary** — from each view's `access_policy`: which groups
   can read it, the `row_level` scoping member(s), and whether the view exposes
   PII (heuristic: presence of the known sensitive members, cross-checked with
   the view's own documentation).
5. **Render Markdown** — folder order follows the view's `meta.folders`;
   measures listed first, then dimensions grouped by folder.

**Guarantee — views are the only surface documented.** The generator is
view-driven: it renders exactly the members a view's `includes:` exposes,
resolving each one's type and description from the cube index. The cube parse is
only a lookup table — it never emits a row on its own. Therefore any cube
dimension/measure that no view exposes, every private cube (`public: false`),
and every hidden helper measure (`_`-prefixed, `public: false`, never included
by a view) is absent from the catalog by construction. This matches Cube's
"cubes private, views public" model, and `--verify-against-meta` reinforces it
(`/meta` returns only public members, so any non-public render would flag as a
mismatch).

CLI:

```text
uv run scripts/generate_cube_reference.py [--output PATH] [--check] [--verify-against-meta]
```

- `--check` — regenerate to a temp buffer and diff against the committed file;
  non-zero exit if stale. This is what CI runs.
- `--verify-against-meta` — mint an HS256 JWT from `CUBE_API_SECRET`, GET
  `/meta`, and assert the YAML-resolved member set and types match Cube's
  compiled contract. Off by default (no network); run manually or on a schedule.
  Divergence is a hard error naming the mismatched members.

### Component 4 — automation (the "auto-update" guarantee)

A **separate** GitHub Actions workflow
(`.github/workflows/cube-docs-check.yaml`, not folded into `trunk-check.yaml`),
triggered on pull requests touching `src/cube/**` or the generator: run
`generate_cube_reference.py --check` and fail if the committed catalog is stale.
Adding a cube or view without regenerating cannot merge. This mirrors the
enforcement model the repo already trusts for generated artifacts. The regen
command is documented in [`docs/CLAUDE.md`](../../CLAUDE.md) alongside the
`automations.md` precedent.

### Component 5 — tests

A golden-file test under `tests/` feeds a small fixture cube + view through the
generator and asserts the rendered Markdown. This gives smaller models a clear
pass/fail signal when editing the generator and pins the resolution rules
(prefix naming, folder grouping, measure/dimension classification).

## Data flow summary

Model YAML → parse → cube member index + view definitions → resolve exposed
members (name, type, description, measure/dimension, folder, access) → render
Markdown → committed catalog page → `mkdocs gh-deploy` publishes. CI `--check`
prevents drift; optional `--verify-against-meta` keeps YAML resolution honest
against Cube's compiler.

## File inventory

| Path                                        | Status            | Purpose                                          |
| ------------------------------------------- | ----------------- | ------------------------------------------------ |
| `scripts/generate_cube_reference.py`        | new               | YAML → catalog generator + verifier              |
| `docs/reference/cube-data-catalog.md`       | new, generated    | Field catalog (data dictionary)                  |
| `docs/guides/cube-api.md`                   | new, hand-written | API reference / query guide                      |
| `docs/guides/cube.md`                       | edit              | Cross-link the two new pages from the hub        |
| `mkdocs.yml`                                | edit              | Add both pages to `nav:`; enable `toc.integrate` |
| `docs/CLAUDE.md`                            | edit              | Document the generator + freshness check         |
| `.github/workflows/*`                       | edit/new          | CI freshness check on `src/cube/**`              |
| `tests/.../test_generate_cube_reference.py` | new               | Golden-file test for the generator               |

## Decisions made

- **Generation source: YAML in-repo, verified against `/meta`.** No auth or
  network on the default path; drift caught at PR time; `/meta` verification is
  an on-demand correctness backstop.
- **Single catalog page** with heading-based sidebar nav, not one page per view
  — avoids `mkdocs.yml` nav churn as views are added.
- **One doc set, three entry points** — the audiences share a field catalog and
  query format; only the guide's opening routes differ.

## Risks and mitigations

- **Resolution logic diverges from Cube's compiler.** Mitigated by
  `--verify-against-meta` and the golden-file test.
- **Descriptions are the weak link.** The catalog is only as good as the
  `description:` fields on cubes. The placeholder-on-missing render makes gaps
  visible; filling them is follow-up model work, not a docs blocker. The design
  spike enumerated the current gap (9 exposed members from 6 source columns),
  tracked in [#4450](https://github.com/TEAMSchools/teamster/issues/4450).
- **Access-summary heuristic mislabels PII.** Mitigated by cross-checking the
  view's own documented access policy and keeping the summary descriptive
  (linking to `cube.md`'s authoritative access model) rather than authoritative.
