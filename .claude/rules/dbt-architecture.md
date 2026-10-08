---
paths:
  - "**/src/dbt/**/models/**"
---

# dbt architecture

Loads on the first read under any dbt project's `models/`. The section between
the snippet markers is the published standard
(`docs/reference/dbt-conventions.md` includes it); cite rules by ID in reviews.
SQL style rules are in `.claude/rules/dbt-sql.md`.

<!-- --8<-- [start:architecture] -->

## Architecture

### Layers

Data flows from source to consumer through these layers. Each layer has 1 job.

| Layer         | Does                                                                                                           | Lives in (kipptaf)                      |
| ------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `stg_`        | 1 source table: rename, cast, filter soft-deletes, dedup source duplicates, unpivot a source that arrives wide | `<source>/staging/`                     |
| Source `int_` | Logic within 1 source system                                                                                   | `<source>/intermediate/`                |
| Domain `int_` | Cross-source business entities and identity resolution                                                         | Folders tagged `+meta: {layer: domain}` |
| Marts         | `dim_`, `fct_`, `bridge_`: the core every consumer reads                                                       | `marts/`                                |
| `rpt_`        | Thin shaping of marts for 1 tool, including that tool's pivots                                                 | `extracts/<tool>/`                      |

Source packages hold `stg_` and source `int_` only. District projects hold
package config, district-only source models, and thin `rpt_` wrappers over
kipptaf extracts. Cross-region business logic lives only in kipptaf.

### Allowed edges

| Model         | May read                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------ |
| `stg_`        | `source()`                                                                                 |
| Source `int_` | `stg_` and source `int_` in the same source folder; `source()` for district union wrappers |
| Domain `int_` | `stg_`, any source `int_`, domain `int_`, `snapshot_`                                      |
| Marts         | Domain `int_`, other marts                                                                 |
| `rpt_`        | Marts, domain `int_`                                                                       |
| Exposures     | `rpt_`, marts; Cube reads marts only                                                       |

`base_` models count as domain `int_` until
[#2541](https://github.com/TEAMSchools/teamster/issues/2541) renames them.

### Rules

#### A1. Read only the layers your layer allows

A model reads only what the _Allowed edges_ table lists for its layer. An `rpt_`
never reads another `rpt_`.

- Why: when every layer reads from its own place, logic has 1 home and a
  reviewer knows where to look for it.
- Good: `rpt_tableau__<dashboard>` reads
  `fct_student_attendance_enrollment_daily`.
- Bad: `rpt_tableau__<dashboard>` reads `stg_powerschool__attendance`.
- Enforced by: `dbt-layer-check`, with a baseline of existing violations.

#### A2. An `rpt_` reads a mart when 1 covers the entity

Read a domain `int_` only while no mart covers the entity, and link an issue for
the missing mart in the PR.

- Why: marts are the 1 shared definition; an `rpt_` built on an `int_` rebuilds
  logic the mart already owns.
- Good: `rpt_gsheets__<roster>` reads `dim_staff`.
- Bad: `rpt_gsheets__<roster>` reads `int_people__staff_roster` when `dim_staff`
  has the columns.
- Enforced by: review.

#### A3. An intermediate either builds or reshapes

A build model keeps a grain and assembles columns (joins, decodes, cleanup); its
name has no suffix. A reshape model changes the grain; its name ends in
`_pivot`, `_unpivot`, `_rollup`, `_scaffold`, or `_union`. A crosswalk is a
build model whose entity is a mapping. Existing names stay.

- Why: the name tells a reader what happens to the grain before they open the
  file.
- Good: `int_people__staff_roster` (build),
  `int_kippadb__standardized_test_unpivot` (reshape).
- Bad: `int_<concern>__scores_unpivoted`.
- Enforced by: `dbt-layer-check` (new models).

#### A4. 1 model per grain

Each grain has 1 model within a source folder, and 1 across the domain folders.
A reshape model is the canonical model for its output grain. Before adding an
intermediate, check whether a model already has that grain; extend it instead of
adding a sibling.

- Why: 2 models at 1 grain drift apart, and the next author cannot tell which is
  right.
- Good: a new staff column goes into `int_people__staff_roster`, not a second
  model at 1 row per staff member.
- Bad: `int_powerschool__gradebook_assignments_scores` and
  `int_students__gradebook_assignments_scores` at the same grain.
- Enforced by: review; `dbt-layer-check` warns on a shared uniqueness grain.

#### A5. Dedup only in `stg_` or source `int_`

- Why: a dedup further down hides an upstream bug instead of fixing it.
- Good: `dbt_utils.deduplicate` in a staging model over a source that resends
  rows.
- Bad: `dbt_utils.deduplicate` on the PK at the end of a mart.
- Enforced by: review.

#### A6. Long in the core, wide at the edge

Intermediates and marts stay long: 1 row per fact at its natural grain. A pivot
to a wide layout for 1 tool lives inside that tool's `rpt_`. An `int_` pivot is
fine when its output grain is reused.

- Why: long data serves every consumer; a wide layout serves 1.
- Good: a fact with 1 row per student, test, and subject.
- Bad: `int_deanslist__students__custom_fields__pivot` read only by
  `rpt_tableau__community_service`.
- Enforced by: review.

#### A7. Identity in the domain `int_`; keys through their macro

Decide which source records are the same person or thing in the domain `int_`.
Hash an entity's surrogate key in a mart only through that entity's macro
(`{{ student_key(...) }}`), never with a direct `generate_surrogate_key` call.

- Why: 1 macro holds each key's inputs, so a key cannot drift between the marts
  that hash it.
- Good: `{{ student_key("s.student_number") }} as student_key`.
- Bad:
  `{{ dbt_utils.generate_surrogate_key(["s.student_number"]) }} as student_key`.
- Enforced by: `dbt-layer-check` (touched marts).

#### A8. Exposures read only `rpt_` and marts

A tool reads an `rpt_` or a mart. Cube reads marts only.

- Why: the consumer layer absorbs schema change; a tool on an `int_` breaks when
  the `int_` changes.
- Good: a Tableau exposure `depends_on: ref("rpt_tableau__<dashboard>")`.
- Bad: a Tableau exposure `depends_on: ref("int_topline__student_metrics")`.
- Enforced by: `dbt-layer-check`, with a baseline.

#### A9. No `select *` in the final select of an `rpt_` or mart

- Why: the column list is the consumer's contract; a star hides it.
- Good: `select student_key, academic_year, … from final`.
- Bad: `select * from final`.
- Enforced by: `dbt-layer-check` (touched models).

#### A10. Join unioned regional models on `_dbt_source_project`

When 2 models both union regional datasets, add
`a._dbt_source_project = b._dbt_source_project` to the join.

- Why: ids repeat across regions; without it, rows match across regions.
- Good:
  `on a.student_number = b.student_number and a._dbt_source_project = b._dbt_source_project`.
- Bad: `on a.student_number = b.student_number` between 2 cross-region unions.
- Enforced by: review.

#### A11. Domain folders are tagged

A kipptaf folder holding domain `int_` models carries `+meta: {layer: domain}`
in `dbt_project.yml`. Adding a domain is normal: add the folder and its tag in 1
PR.

- Why: the tag is how the check tells a domain `int_` from a source `int_`.
- Good: `students: +meta: {layer: domain}`.
- Bad: a new `enrollments/` folder of cross-source models with no tag.
- Enforced by: `dbt-layer-check`.

### Marts

Dimensional marts (star schema) are consumed by Cube, Tableau, and the `rpt_`
layer. Bridge models (`bridge_*`) are factless facts that link 2 or more
dimensions many-to-many.

#### Column-naming rubric

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

#### Degenerate-dim rule

Text columns (e.g. `incident_type`, `consequence_type`) drop `_code` / `_name`
suffixes. Exception: when a code AND a human name coexist in the same table
(e.g. `term_code` + `term_name`, `status_code` + `status_name`), both suffixes
stay. Under R10, both halves also keep their entity prefix so the pair stays
consistent.

#### Plumbing definition

Removed from all mart SELECTs:

- `_dbt_source_relation` (dbt internal, union-model metadata)
- Source-system internal row IDs used only for upstream joins (DeansList `lid`,
  PowerSchool `dcid`, Amplify record IDs, iReady submission IDs, etc.)
- Any column whose only historical use was as a join key in intermediate layers

Plumbing remains in `staging/` and `intermediate/` — only stripped from the mart
SELECT.

#### Strict-chain traversal

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

#### PK / FK / date column shapes

- **Primary key**: `<entity>_key`, hashed through the entity's key macro (A7),
  or `generate_surrogate_key([...])` for an entity with no macro yet.
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

<!-- --8<-- [end:architecture] -->

## Claude-only notes

- Nullable FK hashing: `.claude/rules/dbt-sql.md` → _Nullable surrogate keys_.
- Mart-specific operations (hash-change discipline, table materialization, FK
  constraints, pre-merge checklist): `src/dbt/kipptaf/models/marts/CLAUDE.md`.
