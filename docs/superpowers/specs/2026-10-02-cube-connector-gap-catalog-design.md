# Cube Connector Gap Catalog — Design

Refs [#5673](https://github.com/TEAMSchools/teamster/issues/5673). Approved in
conversation 2026-10-01.

## Problem

The Claude Cube Connector project (Asana: Data Marts + Semantic Layer) must
finish by the end of SY26-27, but only most of assessments and most of
attendance are done, and the Asana project's measure-level scope reads "TBD" for
nearly every dashboard. Nobody can see the true size of the remaining work, so
the timeline cannot be planned.

## Deliverable

A priority-agnostic gap catalog in `docs/superpowers/plans/`:

- `2026-10-02-cube-gap-catalog.md` — index: per-dashboard coverage counts and
  the Asana reconciliation.
- `2026-10-02-cube-gap-catalog-<domain>.md` — per-domain detail, grouped by the
  Asana project's domain sections (attendance, students, assessments, behavior,
  grades, postsecondary, staff, observations, surveys, talent, support,
  student-recruitment, stipends-cert).

No sequencing and no milestones. Sequencing is deferred to a later pass.

## Scope: the core set

The launch page (`docs/launch/links.yml`) defines the core set: every entry with
`system: tableau` and `status: verified` — 30 dashboards. Entries at
`needs-review` and non-Tableau systems are out of scope.

Revision 2026-10-02: the recount during extraction found 31 verified Tableau
entries, not 30. The catalog covers all 31.

## Extraction

For each dashboard: download the production workbook from tableau.kipp.org via
the tableau MCP and parse the workbook XML (per the `tableau-workbook-xml`
skill). Inventory, per published dashboard:

- the sheets it displays (hidden scratch sheets excluded),
- every measure on those sheets: field name, aggregation, and the calculation
  formula when it is a calculated field (pure formatting calcs excluded),
- every dimension used to slice, filter, or color those measures.

Execution is fanned out one subagent per dashboard in parallel batches. Each
subagent returns a structured inventory; claims are spot-checked against the raw
XML rather than accepted as self-reports.

## Classification

Each measure gets exactly one status:

| Status          | Meaning                                                      |
| --------------- | ------------------------------------------------------------ |
| `cube-covered`  | A Cube measure exists in `src/cube/model/`                   |
| `mart-ready`    | A `fct_`/`dim_` column carries it, but no Cube measure       |
| `mart-missing`  | No mart model carries it; names the `rpt_` model holding the |
|                 | logic today                                                  |
| `workbook-only` | Tableau-side calc with no warehouse counterpart worth        |
|                 | porting; flagged, not dropped                                |

Dimensions get the same treatment against Cube views and mart dims.

Every gap row also records regional coverage: which of Newark, Camden, Miami,
Paterson (or all) the metric applies to, derived from the workbook's filters and
datasource scoping and from the `rpt_` model logic. Region-limited flavors
(NJ-only certification, Miami-only FAST/STAR, Newark-only home instruction) must
be visible as a prioritization data point.

## Asana reconciliation

Per dashboard, the catalog reports (read-only — no Asana writes):

- the matching Asana task (workbook LSIDs are already recorded there),
- diffs between the task's `rpt_` and blocker lists and what the workbook
  actually uses,
- measure-level tasks that exist versus the extracted inventory,
- core-set dashboards with no Asana task at all.

## Constraints

- No PII: the catalog carries field names, model names, and counts only — never
  query rows.
- The tableau MCP may point at the Foundation sandbox (10ax) rather than
  production tableau.kipp.org. The first execution step verifies which site it
  serves; if production is unreachable, stop and ask rather than cataloging
  sandbox workbooks.

## Verification

Before the catalog is written up: spot-check a sample of `cube-covered` claims
against `cube meta` and `mart-ready` claims against mart YAML/SQL. Lint all
markdown with trunk before pushing.
