# CLAUDE.md — `marts/`

Dimensional marts (star schema) consumed by Cube and Tableau. Most-downstream
layer — no `ref()` from staging, intermediate, or reporting into marts.
Intra-mart refs are permitted (e.g. `dim_survey_expectations → dim_surveys`,
`fct_staff_attrition → dim_staff_status`). When renaming a mart column, grep
`ref(...)` within `marts/` too — not just outside.

## Column-naming rubric

Applied to every column in every mart model. Numbering matches the spec
(`docs/superpowers/specs/2026-04-15-column-naming-audit.md`); R5 is omitted here
because R7 covers the same ground.

- **R1. Strip source-system prefixes/names** (`powerschool_`, `adp_`,
  `deanslist_`) unless disambiguating unified columns.
- **R2. No KIPP-specific language** (`teammate`, `employee_number`, `microgoal`,
  `dcid`, `oid`, `lep`).
- **R3. Boolean fields use `is_` / `has_` prefix.** On fact tables, countable
  0/1 flags may use `INT64` rather than `BOOLEAN` so `SUM(is_x)` / `AVG(is_x)`
  read naturally without casting. Weighted non-binary measures drop `is_` (e.g.
  `present_weight`).
- **R4. Dates end `_date`; timestamps end `_timestamp`.**
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
  to unqualified.

### BI presentation is Cube's job

Don't entity-qualify bare reserved-word columns to satisfy BI field-list
readability — Cube `title:` aliases BI presentation. Evaluate R10 /
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

## Strict-chain traversal

Facts and child dims FK to their direct parent(s) only; deeper dimensional
context is reached by traversing the FK chain, not by denormalizing it into the
row.

- **No diamond paths.** A fact should never have two FK routes to the same
  ultimate dim. If a fact needs attributes of a deep dim (e.g. `dim_regions`
  from a staff observation), traversal goes through the chain
  (`fct_staff_observations → dim_staff_work_assignments → dim_work_assignment_locations → dim_locations → dim_regions`),
  not via a direct `region_key` on the fact.
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
- **Date FK** (`_date_key`): raw DATE value matching `dim_dates.date_key`,
  **not** a hash. Never also expose the same date as a degenerate `_date` column
  next to its `_date_key` (R9).
- **Nullable FK**: wrap with the
  `if(col is not null, generate_surrogate_key, cast(null as string))` pattern
  (see `src/dbt/CLAUDE.md` → "Nullable surrogate keys") — otherwise
  relationships tests fail against the placeholder hash.

## BigQuery reserved identifiers

Columns named `name`, `type`, `text`, `order`, `role`, `rank`, `timestamp`, etc.
need backticks in SQL (`as \`type\``) and `quote: true` in the YAML column entry
— trunk fails sqlfluff RF04 otherwise.

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

Pure output-alias renames don't change hashes. Any of the five above require an
entry in the "Enumerated surrogate-key changes" table of the column-naming audit
spec.

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
every paste. The audit review caught this twice in one pass
(`fct_behavioral_consequences.start_date_key/end_date_key` pointed at
`stg_powerschool__sectionteacher`; `fct_behavioral_incidents.incident_status`
pointed at `stg_powerschool__courses`).

## Contract + uniqueness inherited

Marts inherit `contract: enforced: true` and `materialized: view` from
`dbt_project.yml`. Don't restate them per model. Every model still needs an
explicit uniqueness test on its PK (`unique` on a single column, or
`dbt_utils.unique_combination_of_columns` for composite).

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

Every mart must appear in `cube.yml`'s `cube_semantic_layer.depends_on`; other
exposures reference `rpt_*` / staging / intermediate models, not marts.

## Not in this layer

- Reporting views (`rpt_*`) — live under `extracts/`.
- Source-system cleanup — happens in `staging/` and `intermediate/`.
- Plumbing (see definition above) — never leaks to a mart SELECT (R8).

## Deferred structural follow-ups

Tracked under #3631 (star-schema second pass):

- #3672 — `fct_job_candidate_applications.shared_with_location_key` coverage
- #3686 — `dim_staffing_positions.location_key` coverage
- #3687 — `int_people__staff_roster_history` multi-assignment fan-out
- #3688 — `fct_grades_assignments` polymorphic score split
- #3689 — `dim_locations` address unification +
  `dim_work_assignment_locations.location_key` FK

Before proposing a new structural mart change, check these — the case may
already be tracked and deferred.

## SIS-migration insulation

Source-system agnostic naming is a load-bearing design choice. When Focus
replaces PowerSchool (Miami) and Finalsite replaces PowerSchool enrollment, the
mart surface should not change. Don't add source-system terminology
(`powerschool_*`, `focus_*`, `finalsite_*`) to new mart columns.
