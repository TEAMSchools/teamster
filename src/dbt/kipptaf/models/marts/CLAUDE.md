# CLAUDE.md — `marts/`

Dimensional marts (star schema) consumed by Cube and Tableau. Most-downstream
layer — no `ref()` from staging, intermediate, or reporting into marts.
Intra-mart refs are permitted (e.g. `bridge_survey_expectations → dim_surveys`,
`fct_staff_attrition → dim_staff_status`). When renaming a mart column, grep
`ref(...)` within `marts/` too — not just outside.

**Bridge models (`bridge_*`)** are factless facts that link two or more
dimensions via a many-to-many relationship and carry no measures. They live in
`marts/bridges/`. Naming follows `bridge_<entity>_<entity>` or
`bridge_<concept>` when the linked entities are obvious from context. Like dims
and facts, bridges inherit `contract: enforced: true` and `materialized: view`,
and require an explicit uniqueness test on their PK. Bridges follow the same
strict-chain rule as facts — no diamond paths to a shared ancestor dim.

## Column-naming rubric

Applied to every column in every mart model.

- **R1. Strip source-system prefixes/names** (`powerschool_`, `adp_`,
  `deanslist_`, `focus_`, `finalsite_`) unless disambiguating unified columns.
  Source-agnostic naming is load-bearing — the mart surface must not change when
  Focus replaces PowerSchool or Finalsite replaces PowerSchool enrollment.
- **R2. No KIPP-specific language** (`teammate`, `employee_number`, `microgoal`,
  `dcid`, `oid`, `lep`).
- **R3. Boolean fields use `is_` / `has_` prefix.** On fact tables, countable
  0/1 flags may use `INT64` rather than `BOOLEAN` so `SUM(is_x)` / `AVG(is_x)`
  read naturally without casting. Weighted non-binary measures drop `is_` (e.g.
  `present_weight`).
- **R4. Dates end `_date`; timestamps end `_timestamp`.**
- **R5. \[reserved / removed\]** — numbering retained for stability of
  references in prior PRs and issue history.
- **R6. Ed-Fi Unified Data Model** nomenclature is the default for IDs, entity
  names, standard attributes. Deviate toward plain English for awkward
  descriptors.
- **R7. Keep ubiquitous acronyms; spell out internal ones.** Ubiquitous,
  user-facing acronyms (`gpa`, `ada`, `fte`, etc.) stay verbatim; niche
  source-system acronyms (`dcid`, `oid`, `lep`) get spelled out or removed.
- **R8. Plumbing removed** from mart SELECTs — see definition below.
- **R9. Remove dimension attributes reachable via FK.** Includes natural keys
  that duplicate a surrogate FK, and date columns that duplicate a date-key FK.
- **R10. Entity qualification.** Qualify a descriptive column with the model's
  entity prefix only when removing it creates a real downstream-join ambiguity
  (e.g. `full_name` on every person dim — not `student_name`). Otherwise default
  to unqualified. Don't entity-qualify bare reserved-word columns to satisfy BI
  field-list readability — Cube `title:` aliases BI presentation. Evaluate R10 /
  reserved-word rename decisions against raw-SQL ergonomics only.

### Degenerate-dim rule

Text columns (e.g. `incident_type`, `consequence_type`) drop `_code` / `_name`
suffixes. **Exception**: when a code AND a human name coexist in the same table
(e.g. `term_code` + `term_name`, `status_code` + `status_name`), both suffixes
stay. Under R10, both halves also keep their entity prefix so the pair stays
consistent.

### Plumbing definition

Removed from all mart SELECTs:

- `_dbt_source_relation` (dbt internal, union-model metadata)
- Source-system internal row IDs used only for upstream joins (DeansList `lid`,
  PowerSchool `dcid`, Amplify record IDs, iReady submission IDs, etc.)
- Any column whose only historical use was as a join key in intermediate layers

Plumbing remains in `staging/` and `intermediate/` — only stripped from the mart
SELECT.

## Filing follow-up issues from marts work

When filing a GitHub issue from marts work (spec authoring, PR review follow-up,
CI warning triage), add it to project board
[#4](https://github.com/orgs/TEAMSchools/projects/4) and set `Tier`, `PR batch`,
and `Driver`. Commands and `GITHUB_TOKEN=` prefix: see root CLAUDE.md → MCP
Servers `gh project` bullets. `Status` auto-sets to Todo on add — skip.

**Ops-tracked grouping**: file ONE `ops-tracked` issue per underlying source
(one Google Sheet, one config file) — bullets per orphan bucket inside. Don't
split per-bucket when the action is one sheet-editing session.

## Pre-merge checklist (marts PRs)

Run before posting the final PR comment on any marts PR (spec, bugfix,
refactor):

- Scan touched models for diamond paths (see "Strict-chain traversal").
- Scan touched models for column-naming rubric violations (R1–R10 above).
- Pull marts-model warnings from the latest CI run
  (`mcp__dbt__get_job_run_error` with `warning_only=true`). For each, search
  open issues by model name + FK target. Bucket orphans (by region, source,
  test_type, etc.) in the issue body before filing.
- Scan the
  [project board](https://github.com/orgs/TEAMSchools/projects/4/views/1) for
  bonus issues incidentally resolved; close them in the PR.
- File newly surfaced errors per "Filing follow-up issues from marts work"
  above.

## Strict-chain traversal

Facts and child dims FK to their direct parent(s) only; deeper dimensional
context is reached by traversing the FK chain, not by denormalizing it into the
row.

- **No diamond paths.** A fact should never have two FK routes to the same
  ultimate dim. If a fact needs attributes of a deep dim (e.g. `dim_regions`
  from a staff observation), traversal goes through the chain
  (`fct_staff_observations → dim_locations → dim_regions`), not via a direct
  `region_key` on the fact.
- **Parent-fact inheritance.** A child fact that FKs to a parent fact inherits
  the parent's dimensional context and does not repeat it. Example:
  `fct_behavioral_consequences` carries `behavioral_incident_key` only; student
  / location / region come through the parent, not duplicated here.

Watch for common diamond triggers: a new `region_key` on a fact that already FKs
to a location or staff-work-assignment; role-playing date FKs pointed at the
same `dim_dates` row without a role qualifier (`created_date_key` vs
`solved_date_key`, not both `date_key`). If you find yourself adding an FK to
avoid a join, the chain is probably already there — use it instead.

## PK / FK / date column shapes

- **Primary key**: `<entity>_key`, always `generate_surrogate_key([...])`.
- **Foreign key**: `<target>_key` when unambiguous; `<role>_<target>_key` when
  multiple FKs to the same target coexist (e.g. `submitter_staff_key` +
  `assignee_staff_key` on `fct_support_tickets`). Never expose the raw natural
  key alongside its surrogate (R9).
- **FK constraint form**: declare foreign keys with the ref-aware
  `to: ref(...)` + `to_columns:` form (dbt 1.9+) at the **column** level for
  single-column FKs — not model-level `expression: ref(...)`, which is free text
  that doesn't capture the ref dependency.
- **Date FK** (`_date_key`): raw DATE value matching `dim_dates.date_key`,
  **not** a hash. Never also expose the same date as a degenerate `_date` column
  next to its `_date_key` (R9).
- **Nullable FK**: wrap with the
  `if(col is not null, generate_surrogate_key, cast(null as string))` pattern
  (see `src/dbt/CLAUDE.md` → "Nullable surrogate keys") — otherwise
  relationships tests fail against the placeholder hash.

## Hash-input joins: INNER over LEFT when scope guarantees membership

When a fact/bridge joins a parent (members, canonical, dim) purely to read
hash-input columns, and the `where` filter (`is_internal_assessment`, etc.)
guarantees the parent row exists, use INNER JOIN. LEFT JOIN silently produces
null hash inputs that surrogate-key into placeholder hashes — orphans surface
only at `relationships` test runtime, not at compile.

## BigQuery reserved identifiers

Columns named `name`, `type`, `text`, `order`, `role`, `rank`, `timestamp`, etc.
need backticks in SQL (`as \`type\``) and `quote: true` in the YAML column entry
— trunk fails sqlfluff RF04 otherwise.

Reserved words also fail as plain SELECT aliases (`count(*) as rows`,
`count(*) as keys`) — sqlfluff doesn't catch those, BQ throws at parse. Use
`n_rows`/`n_keys` or backtick.

## Hash-change discipline

Surrogate-key hash values change for five reasons only:

1. **Values unify** — consolidating two source columns into one canonical.
2. **Types change** — casting `int64` to `string` alters the hash input.
3. **Composition changes** — adding/removing a column from the
   `generate_surrogate_key()` input list.
4. **Null handling changes** — wrapping a previously-unwrapped nullable key in
   the `if(x is not null, ...)` pattern.
5. **Structural add** — introducing a new FK/degenerate surrogate where none
   existed before.

Pure output-alias renames don't change hashes.

Hash inputs must be derived identically across producer and consumer.
Intermediates may rename or transform columns (e.g. scaffold's
`academic_year_clean` aliased as `academic_year` is +1 vs
`int_assessments__assessments_members.academic_year`); the consumer must re-join
the source-of-truth model rather than trust the matching column name.

Before swapping the input list of any `generate_surrogate_key()` on a dim/fact,
grep every consumer that hashes the same composition and migrate producer + all
consumers in one atomic commit.

Adding a column to a hash input or join predicate also requires that column in
the upstream CTE that aliases the source. Compile fails with
`Name X not found inside ALIAS` otherwise.

## `_dbt_source_project` joins and hashes

When a marts fix touches joins or surrogate-key composition involving
`_dbt_source_project` (or `_dbt_source_relation`), promote the
`extract_code_location()` call up to the union model itself rather than applying
it at each consumer
([#3142](https://github.com/TEAMSchools/teamster/issues/3142)). Downstream
consumers should join and hash on the materialized `code_location` column, not
re-derive it from `_dbt_source_relation` per-call. This counts as an additive
upstream edit under "Spec authoring context" and does not require a separate
refactor PR.

## Removing a mart-level `qualify row_number() = 1`

Verify the upstream intermediate is unique on the qualify's partition key before
removing — the qualify often masks an upstream PK collision (hashed ID
duplicates), not a date-range overlap. "Same join shape as another mart" is not
sufficient evidence.

Net mart row-count delta is typically `+N` where N is the residual fan-out — not
`-N`. Adding an upstream `where` filter alongside doesn't drop PKs; it changes
which rows the surviving PK joins to.

## Verify source precision before R9 drops

Staging cast chains (`cast(x as datetime)` → `cast(as date)`) and field names
ending in `_date` are not reliable signals of value precision. Before dropping a
column as redundant with its date/timestamp sibling, sample real values via
BigQuery MCP:

```sql
select
  countif(extract(time from col) = '00:00:00') as n_midnight,
  count(*) as n_rows,
from `<schema>.stg_<model>`
```

All midnight → drop is safe. Distributed times → column carries real
time-of-day; keep. SmartRecruiters state-transition fields are the canonical
trap — field names end in `_date` but values are full ISO timestamps.

## Descriptions are source-agnostic

Source-system internal field names (`cc_dateleft`, `WorkAssignment.jobTitle`,
`powerschool_student_number`, etc.) belong in `config.meta.source_column`, not
in the user-visible `description:`.

## Stale metadata from copy-paste

A copy-pasted column block usually keeps the old `description:` and
`config.meta.source_*` pointing at the wrong source table. Update both after
every paste.

## Contract + uniqueness inherited

Marts inherit `contract: enforced: true` and `materialized: view` from
`dbt_project.yml`. Don't restate them per model. Every model still needs an
explicit uniqueness test on its PK (`unique` on a single column, or
`dbt_utils.unique_combination_of_columns` for composite).

Exception: the assessment-scores star (`fct_assessment_scores_enrollment_scoped`
plus its FK-closure dims) and the three assessment intermediates are
`materialized: table` for Cube query performance
([#4464](https://github.com/TEAMSchools/teamster/issues/4464)) — don't revert to
view without re-profiling Cube's BigQuery spend.

Drop model-level `dbt_utils.unique_combination_of_columns` when its column set
equals the surrogate-key hash inputs — `unique` on the PK detects the same
violations.

## FK constraints declared on every mart

`generate_marts_reference.py` derives FK edges **only** from literal
`foreign_key` constraints — never inferred from `relationships` data tests. So
every mart (view-materialized and `config.materialized: table` alike) must
declare its outgoing FKs as column- or model-level `foreign_key` constraints, or
they vanish from the generated reference diagram. A `relationships` data test is
still good to keep for orphan detection, but it does not feed the diagram.

A `config.materialized: table` mart renders `constraints:` into CREATE TABLE DDL
(inert on the default view marts). On a table mart, add `warn_unenforced: false`
(not just `warn_unsupported: false`) on EVERY constraint — primary_key AND
foreign_key both render into DDL and warn otherwise.

## Converting a view mart to a table

- BigQuery FK DDL requires every referenced relation to be a TABLE with a PK
  constraint. Convert the full FK closure (walk `to: ref(...)` edges) in one PR
  — a table mart FK'ing a still-view mart fails the build.
- Under `--defer` (local dev AND dbt Cloud CI), dbt resolves FK constraint refs
  to the DEFERRED relation unconditionally — even for models rebuilt in the same
  run (dbt-core `compilation.py`). CI fails against still-view `zz_stg` copies
  no matter what the PR schema builds. Before pushing, pre-seed staging as
  tables: `dbt run --select <closure> --target staging` (shared `zz_stg` — needs
  direct user authorization). BQ table clones preserve PK constraints, so
  `Clone - Staging` keeps CI healthy afterward.

## Constraints are informational (views)

PK/FK `constraints:` blocks on marts are not enforced (views). dbt emits a parse
warning per constraint unless `warn_unsupported: false` is set on the block.
Constraint metadata still lands in `manifest.json` for downstream tooling (Cube)
— set `warn_unsupported: false` on every constraint.

## Exposures are the consumer contract

Every external consumer (Tableau, Google Sheets, Cube, AppSheet, etc.) that
reads a mart must have a dbt exposure under `src/dbt/kipptaf/models/exposures/`.
Without one, column renames and removals silently break downstream — dbt has no
other signal.

Before removing a column from any `dim_*` / `fct_*`, grep `src/cube/model/` for
`sql: <col>` and bare `<col>` — Cube YAML reads by name and dbt has no exposure
to surface the dep.

Every mart must appear in `cube.yml`'s `cube_semantic_layer.depends_on`; other
exposures reference `rpt_*` / staging / intermediate models, not marts.

## SCD2 status dims bound to enrollments

Status dims sourced from external systems (edplan, titan, s_nj_stu_x) that
represent enrollment-context status:

- Grain `(student_number, _dbt_source_project, effective_date_start)`; expose
  `_dbt_source_project` as a dim column.
- Inner-join external records to enrollment **per stint** (not aggregated
  min/max). Multi-stint students get separate dim rows per stint. Date-range
  predicates in ON, not WHERE.
- Carry `student_enrollment_key` as direct FK to `dim_student_enrollments` via
  `surrogate_key(student_number, _dbt_source_project, academic_year, entrydate)`
  — consumers equi-join instead of date-range BETWEEN.
- Half-open exit:
  `enrollment_end = coalesce(date_sub(exitdate, interval 1 day), '9999-12-31')`
  to avoid boundary-share overlaps.
- `student_enrollment_key` is **non-unique** here — within-stint status changes
  emit multiple spans per stint (IEP ~26% of stints, up to 10; meal ~3%; ELL 1).
  A consumer equi-join on it fans out by the span count; collapse to one row per
  stint (a rollup model with an explicit per-attribute rule) before joining a
  fact or the enrollment dim.

## "Is current X" flags on dim_dates

Date-grain temporal classifiers (`is_current_academic_year`,
`is_current_fiscal_year`, etc.) live on `dim_dates`, derived from
`{{ var("current_X") }}` baked in at build time. Don't auto-derive from
`CURRENT_DATE` at query time — rollover is manual via dbt var bump.

## Verify FK population, not just compilation

`relationships` tests don't fail on 100%-NULL FKs. After adding or restructuring
an FK join, sample populated count in prod (or PR-branch schema):

```sql
select countif(<fk>_key is null) as n_null, count(*) as n_total
from `<schema>.<fact>`
```

Treat ≥99% NULL as a broken join, not a sparse FK.

To join a mart by its surrogate key from ad-hoc BQ (verify FK population when
the column was dropped, or compare PR vs prod), reproduce
`generate_surrogate_key`:
`to_hex(md5(concat(coalesce(cast(<f1> as string), '_dbt_utils_surrogate_key_null_'), '-', coalesce(cast(<f2> as string), '_dbt_utils_surrogate_key_null_'))))`.
Validate the hash by checking the join row count reconciles before trusting it.

## Not in this layer

- Reporting views (`rpt_*`) — live under `extracts/`.
- Source-system cleanup — happens in `staging/` and `intermediate/`.
- Plumbing (see definition above) — never leaks to a mart SELECT (R8).

## Spec authoring context

Cube and Tableau consume these marts directly — 11 cubes read `kipptaf_marts.*`
tables (see `src/cube/CLAUDE.md` and `cube.yml`'s
`cube_semantic_layer.depends_on`). Treat column renames, removals, restructures,
and surrogate-key hash churn as breaking changes: grep `src/cube/model/` for the
column (see "Exposures are the consumer contract" above) and ship the Cube
update in the same change — don't assume hash churn is free.

Mart-focused PRs may edit upstream files (`staging/`, `intermediate/`, source
packages) but those edits must be **additive only**. Wider upstream refactors
require a compelling reason called out in the spec; otherwise split into a
separate PR.

Before proposing a new structural mart change, check the open items on the
[Data Team project board](https://github.com/orgs/TEAMSchools/projects/4) — the
case may already be tracked and deferred.

Adding a column to a model breaks downstream contract-enforced `select *`
consumers. Grep `select \*` consumers and update their contract YAMLs in the
same PR — only `dbt build` catches it, not `parse`.
