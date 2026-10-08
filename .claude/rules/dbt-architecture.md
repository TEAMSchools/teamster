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
- Bad: `int_<source>__scores` and `int_<source>__scores_clean` in 1 source
  folder at the same grain.
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
When an entity has a key macro (`{{ student_key(...) }}`), hash its surrogate
key in a mart only through that macro, never with a direct
`generate_surrogate_key` call.

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

<!-- --8<-- [end:architecture] -->

## Claude-only notes

- Apply the A, S, and R rules only to models and lines you add or change. Never
  propose a sweep of untouched models. An existing A1, A2, or A8 edge is known
  backlog, not a finding.
- Until domain folders carry the `+meta: {layer: domain}` tag, treat a kipptaf
  `int_` that reads more than 1 source system as domain. Key macros live in
  `src/dbt/kipptaf/macros/`; an entity with none yet uses
  `generate_surrogate_key` (see PK shapes in `.claude/rules/dbt-marts.md`).

- Mart column naming, strict-chain traversal, and PK/FK shapes:
  `.claude/rules/dbt-marts.md` (loads under kipptaf `models/marts/`).
