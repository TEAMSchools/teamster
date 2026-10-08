---
paths:
  - "**/src/dbt/kipptaf/models/marts/**"
---

# dbt marts

Loads on the first read under kipptaf `models/marts/`. The section between the
snippet markers is published on `docs/reference/dbt-conventions.md`, right after
the architecture rules. Mart operations (hash-change discipline,
materialization, FK constraints, pre-merge checklist):
`src/dbt/kipptaf/models/marts/CLAUDE.md`. Nullable FK hashing:
`.claude/rules/dbt-sql.md` → _Nullable surrogate keys_.

<!-- --8<-- [start:marts] -->

## Marts

Dimensional marts (star schema) are consumed by Cube, Tableau, and the `rpt_`
layer. Bridge models (`bridge_*`) are factless facts that link 2 or more
dimensions many-to-many.

### Column-naming rubric

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
suffixes. Exception: when a code AND a human name coexist in the same table
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

### Strict-chain traversal

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

### PK / FK / date column shapes

- **Primary key**: `<entity>_key`, hashed through the entity's key macro (A7),
  or `generate_surrogate_key([...])` for an entity with no macro yet.
- **Foreign key**: `<target>_key` when unambiguous; `<role>_<target>_key` when
  multiple FKs to the same target coexist (e.g. `submitter_staff_key` +
  `assignee_staff_key` on `fct_support_tickets`). Never expose the raw natural
  key alongside its surrogate (R9).
- **FK constraint form**: declare foreign keys with the ref-aware
  `to: ref(...)` + `to_columns:` form (dbt 1.9+) at the **column** level for
  single-column FKs — not model-level `expression: ref(...)`, which is free text
  that doesn't capture the ref dependency. View marts only: a table mart carries
  no outgoing FK constraints and records the edge under
  `config.meta.foreign_key` instead.
- **Date FK** (`_date_key`): raw DATE value matching `dim_dates.date_key`,
  **not** a hash. Never also expose the same date as a degenerate `_date` column
  next to its `_date_key` (R9).

<!-- --8<-- [end:marts] -->
