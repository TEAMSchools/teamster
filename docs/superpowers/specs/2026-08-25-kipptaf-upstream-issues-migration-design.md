# Migrating `Known Upstream Issues` out of `src/dbt/kipptaf/CLAUDE.md`

## Problem

`src/dbt/kipptaf/CLAUDE.md` lines 242-389 hold a section titled
`## Known Upstream Issues`: 9,058 characters across 17 entries, 14 of which open
with a model or column name in backticks. It loads on every session that touches
kipptaf.

The repo's own rule, in `src/dbt/CLAUDE.md` under _YAML conventions_, assigns
that content elsewhere:

> Data and column semantics — code values, identifier formats, join keys, grain
> notes — belong in the model's `description:` (or `config.meta`), not
> CLAUDE.md. CLAUDE.md is for workflow conventions and tooling guidance only.

The section is a near-exact match for what that rule excludes. It is also the
only place in the repo where the rule is broken at scale — a currency audit of
all 65 CLAUDE.md files found no other structural violation.

## What makes this non-trivial

The entries are not column descriptions wearing a disguise. Most are **hybrids**
that mix three kinds of content:

1. A data fact about one model (grain, code values, a defect).
1. A directive or prohibition about what not to do with it.
1. Incident history and tracking-issue references.

Moving an entry wholesale would relocate prohibitions such as "do not add
defensive dedupes" into a file that is only read when someone opens that model —
which is not when the prohibition matters.

## Decisions

### Hybrids are split, not moved whole

The data fact goes to the model's `properties.yml`. The directive stays in
`src/dbt/kipptaf/CLAUDE.md` as a one-line entry naming the model.

Rejected: moving whole entries (puts prohibitions where they may not load) and
moving only the pure-fact entries (leaves the bulk of the section in place).

Cost accepted: two places to maintain per split entry.

### Facts about source-package models land in both projects

`stg_powerschool__students`, `stg_powerschool__cc`, and
`int_powerschool__student_enrollment_union` each exist twice — once in the
`powerschool` package, which builds in all four district projects, and once at
the kipptaf level. The raw defect and the kipptaf-level handling are different
facts about different models.

The package `properties.yml` gets the raw defect. The kipptaf `properties.yml`
gets the union view's behavior. A session working in a district or in the
package still learns about the defect.

### `config.meta` is not a destination

`config.meta` in this repo is a structured namespace — `dagster.group`,
`source_model`, `source_system`, `contains_pii`, `foreign_key`, across 2,769
uses. It carries no prose anywhere. Facts go in `description:` only.

### No new tests

Two entries look test-shaped and are not.

`stg_powerschool__students.enroll_status`: the entry says `-1` (pre-registered)
and `1` (inactive) must never be reported against. Those values **exist in the
data**. An `accepted_values` test asserting `(0, 2, 3)` would fail on real rows
immediately. The entry states a usage rule, not a data constraint.

`dim_terms.type`: the documented value list ends in "etc." — an open set. A test
over it would be brittle and would fail the next time Ops adds a type.

A `config.where`-scoped variant would pass, but would then assert something
trivially true while costing a BigQuery scan per CI run — which
`src/dbt/CLAUDE.md` explicitly warns against under _Test config defaults_.

### Issue references stay put

`src/dbt/CLAUDE.md` under _YAML conventions_:

> Don't put TODOs, history, migration plumbing, or tracking-issue refs (`#3142`,
> etc.) in descriptions — those go in inline SQL comments at the derivation
> site.

So `#3900`, `#3915`, and `#4407` travel with their directives and stay in
CLAUDE.md. No description gains an issue reference.

## Entry classification

Three entries move wholly, 11 split, 3 stay untouched.

| #   | Entry                                    | Fact to `properties.yml`                                                          | Residue in CLAUDE.md                                                         |
| --- | ---------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 1   | `int_people__location_crosswalk`         | alias grain; carries no `_dbt_source_relation`                                    | which consumers use it vs `stg_google_sheets__people__locations`             |
| 2   | `campus_crosswalk`                       | grain is `Location_Name`; sole owner of location-to-campus; NULL campus by design | do not reintroduce a `Campus_Name` scalar on the locations sheet             |
| 3   | `stg_powerschool__students` phantom rows | package: the 4 placeholder rows. kipptaf: the `where dcid >= 1` filter            | apply the same filter when reading a per-region staging table directly       |
| 4   | `enroll_status` code values              | meaning of `-1`, `0`, `1`, `2`, `3` (both project levels)                         | never resolve identity or attribute facts against `-1` or `1`                |
| 5   | `student_enrollment_union` graduates     | NULL entry/exit dates; one row per academic year; hash needs `academic_year`      | retain them; `dim_student_enrollments` stays alumni-inclusive                |
| 7   | `enroll_status` is student-level         | copied identically to every stint row                                             | count point-in-time enrollment by dates, not status                          |
| 10  | `dim_terms.type`                         | KIPP-managed code values; quarter attendance is `type='RT'`                       | none — moves wholly                                                          |
| 11  | `course_enrollments` double-writes       | duplicate `cc` rows per `(student, section, dateleft)`                            | filter `is_dropped_section`; no defensive dedupes; PK test to warn + `#3915` |
| 12  | Grow `_dagster_partition_key`            | it is the `archived` flag, `'f'` / `'t'`                                          | do not re-add the filter to the two exempt models                            |
| 13  | `locations` column naming                | `location_region` long-form vs `city` short canonical                             | none — moves wholly                                                          |
| 14  | `dim_staff`                              | all-time grain; `entity` derives from `business_unit_name`                        | do NOT filter `status_name != 'Terminated'`; spine on `is_current`           |
| 15  | `stg_renlearn__star`                     | what it consolidates; materialized as a table                                     | leave `int_renlearn__star_rollup` disabled; edit STAR here                   |
| 16  | `adp_workforce_now__workers`             | ghost rows stay open at `9999-12-31` with `is_current_record`                     | blast radius, the rematerialize fix, `#4407`                                 |
| 17  | `stg_people__employee_numbers`           | first-appearance order is not hire order                                          | none — moves wholly                                                          |
| 6   | Miami is the exception                   | none                                                                              | stays whole — decision record plus prohibition                               |
| 8   | Point-in-time headcount                  | none                                                                              | stays whole — cross-model analytic policy                                    |
| 9   | School calendars diverge at year-end     | none                                                                              | stays whole — cross-model analytic policy                                    |

## Files touched

16 `properties.yml` files, plus `src/dbt/kipptaf/CLAUDE.md`.

Three models exist at both project levels and take the split treatment from
_Facts about source-package models land in both projects_:
`stg_powerschool__students`, `stg_powerschool__cc`, and
`int_powerschool__student_enrollment_union`.

```text
src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__students.yml
src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml
src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_enrollment_union.yml
src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__students.yml
src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__cc.yml
src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_enrollment_union.yml
src/dbt/kipptaf/models/people/intermediate/properties/int_people__location_crosswalk.yml
src/dbt/kipptaf/models/people/staging/properties/stg_people__employee_numbers.yml
src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml
src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__campus_crosswalk.yml
src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml
src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff.yml
src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__measurements.yml
src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml
src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml
src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml
```

## Execution

Commits are grouped by model family so each is independently reviewable and
revertable:

1. powerschool staging — entries 3, 4, 7, 11 (both project levels)
1. powerschool intermediate — entry 5 (both project levels)
1. people and staff — entries 1, 2, 13, 14, 17
1. terms — entry 10
1. grow — entry 12
1. renlearn — entry 15
1. adp — entry 16
1. `src/dbt/kipptaf/CLAUDE.md` — the residue, written last

CLAUDE.md is edited last on purpose: the residue is written against what
actually landed, not against what was planned.

## Verification

Per commit: `dbt parse --no-partial-parse --target prod` from the affected
project directory. It proves the YAML is valid and that no node changed enable
state. Partial parse caches enable/disable state and under-reports, so the flag
is required.

A `description:` edit does **not** mark a model `state:modified`
(`src/dbt/CLAUDE.md`, _`dbt_utils.union_relations` is compile-time_). dbt Cloud
CI will therefore be a trivial no-op run. That is expected and is **not**
validation — the PR must not be described as CI-validated on that basis.

Final check before the PR: `trunk check --force` over the changed files.
`yamllint` fires at pre-push and CI, not at the pre-commit format hook.

## Risks

**YAML parsing.** Unquoted multi-line `description:` scalars cannot start with a
backtick or contain a colon followed by a space. Several facts do both — for
example the `business_unit_name` mapping in entry 14. Reword to lead with a word
and use an em dash instead of a colon rather than fighting the parser.

**Description drift into semantics that belong in tests.** The rule against
never-failing tests still applies. Adding prose is not a licence to add
`not_null` on a column that cannot be null.

**Column-order churn.** Columns carrying per-column `data_tests:` sort to the
top of the `columns:` list. Adding a description does not add a test, so this
migration should not reorder anything. If a reorder appears in a diff, it is a
mistake.

**Scope creep.** Only the 17 entries in this section are in scope. Other
sections of `src/dbt/kipptaf/CLAUDE.md` are not part of this work.

## Out of scope

- Adding, removing, or re-scoping any dbt test.
- Editing model SQL.
- The three cross-model policy entries (6, 8, 9).
- Any other CLAUDE.md file.
