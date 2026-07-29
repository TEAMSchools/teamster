# GPA Goal Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated goal scaffold for the GPA/gradebook dashboard —
goals defined per (org/region/school × grade band × GPA metric) in a Google
Sheet, joined upstream in an aggregation model that compares each grain's actual
rate to its target.

**Architecture:** Port the topline aggregate-goals pattern. A Google Sheet →
`stg_google_sheets__gpa_goals` → `int_google_sheets__gpa_goals` (adds the grain
`aggregation_hash`). A per-student measures spine
(`int_gpa__goal_student_metrics`) is rolled up per `org_level` and left-joined
to the goals in `int_gpa__goal_aggregations`, which computes rate /
`is_goal_met` / `progress_to_goal`. `rpt_tableau__gpa_goals` exposes it. Detail
stays in `rpt_tableau__student_course_grades`.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Google Sheets external source,
kipptaf project.

Spec: `docs/superpowers/specs/2026-07-28-gpa-goal-scaffold-design.md`. Issue
#4581.

## Global Constraints

- Follow `src/dbt/CLAUDE.md` + `src/dbt/kipptaf/CLAUDE.md`: BigQuery dialect;
  max 1 level function nesting; no `ORDER BY`/`QUALIFY`/`SELECT *` in `rpt_`;
  ST06 column ordering; sqlfluff/sqlfmt via trunk; every model + column gets a
  `description`.
- Grain hash + grade-band mechanics mirror
  `int_google_sheets__topline_aggregate_goals` and
  `int_topline__dashboard_aggregations` — read those two models before
  implementing; copy their shape, substitute the columns named here.
- Staging: contract enforced; filter the Sheet's phantom empty rows
  (`where academic_year is not null`); Google Sheets staging inherits the
  Sheet's header case — match it exactly.
- dbt unit tests use `format: sql` inline fixtures (the real upstreams need not
  be materialized to run them); dict scalars UNQUOTED; every `expect` row lists
  the same columns.
- Build/test source-package-free kipptaf models directly:
  `uv run dbt build --select <model> --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --favor-state`.
- `--target prod` runs, `stage_external_sources --target staging`, and
  `git push origin main` are user-only — hand off.
- Direction semantics: `direction` is the student comparison (`>=` default /
  `<=`); goal-direction is derived (`>=`/`>` ⇒ higher-is-better).

## Prerequisites (human / gated — not subagent tasks)

1. **Sheet header row (blocks Tasks 1+).** Ops adds row 1 to the goals Sheet
   (`1jEZHhe6ZGM0k2fFqDKlh3I45FRjTRa-uYT1rY0JmtlA`, tab gid `187401938`) with
   these exact lowercase headers, left to right: `academic_year`, `org_level`,
   `region`, `schoolid`, `grade_low`, `grade_high`, `metric`, `threshold`,
   `direction`, `goal`. (Optional trailing `notes`.) At least one data row helps
   staging autodetect types; zero data rows is acceptable once headers exist.
2. **`on_pace` upstream (blocks Task 6 only).** The per-student
   `is_on_pace_cumulative_3_0` flag and the priority-subset denominator flag are
   a separate follow-on off the merged #4528/#4529 work. Tasks 1–5 build the
   threshold-metric scaffold and leave `on_pace` inputs null; Task 6 wires it
   when the flags land.

---

## Task 1: Google Sheets source + `stg_google_sheets__gpa_goals`

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (add the
  `src_google_sheets__gpa_goals` external table with `columns:` at source level)
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gpa_goals.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gpa_goals.yml`

**Interfaces — Produces:** columns `academic_year` int64, `org_level` string,
`region` string, `schoolid` int64, `grade_low` int64, `grade_high` int64,
`metric` string, `threshold` numeric, `direction` string, `goal` numeric.

**Depends on Prerequisite 1** (header row exists).

- [ ] **Step 1: Add the source.** In `sources-external.yml`, under the
      `google_sheets` source, add `src_google_sheets__gpa_goals` following an
      existing entry (e.g. `src_google_sheets__topline__aggregate_goals`): the
      `external.options` sheet URI/format and a source-level `columns:` block
      declaring all 10 columns with `data_type` (mirror
      `stg_google_sheets__finance__enrollment_targets`'s source for the pattern,
      including the STRING-typed numeric-looking columns to dodge autodetect).

- [ ] **Step 2: Write the staging model.** `select` the 10 columns from the
      source, cast to the contract types, and `where academic_year is not null`
      (drops phantom empty rows). No renames beyond case-normalization.

- [ ] **Step 3: Properties + contract.** Create the yml:
      `contract: enforced:     true`, a `description` per column,
      `severity: error` on tests, `accepted_values` on `org_level`
      (`org`/`region`/`school`), `direction` (`>=`/`<=`), `metric`
      (`y1_gpa_weighted`/`y1_gpa_unweighted`/
      `cumulative_gpa_unweighted`/`on_pace`), and
      `dbt_utils.unique_combination_of_columns` on (`academic_year`,
      `org_level`, `region`, `schoolid`, `grade_low`, `grade_high`, `metric`).

- [ ] **Step 4: Stage + build.** Hand the user:
      `dbt run-operation stage_external_sources --args "select: google_sheets.src_google_sheets__gpa_goals" --vars '{ext_full_refresh: true}' --target dev --project-dir src/dbt/kipptaf`
      (personal dev copy — not classifier-blocked), then
      `uv run dbt build --select stg_google_sheets__gpa_goals --target dev`.
      Expected: builds; tests pass on the header-only (or seeded) sheet.

- [ ] **Step 5: Commit.**
      `git add src/dbt/kipptaf/models/google/sheets/sources-external.yml src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gpa_goals.sql src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gpa_goals.yml`

## Task 2: `int_google_sheets__gpa_goals`

**Files:**

- Create:
  `src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__gpa_goals.sql`
- Create: `.../intermediate/properties/int_google_sheets__gpa_goals.yml`

**Interfaces — Consumes:** `stg_google_sheets__gpa_goals` (Task 1).
**Produces:** the 10 staging columns plus `grade_band` string,
`aggregation_hash` string, `goal_proportion` numeric (= `goal / 100`),
`higher_is_better` boolean.

- [ ] **Step 1: Write the failing unit test.** In the yml, a `unit_tests:` entry
      `unit_gpa_goals_hash_and_direction` mocking `stg_google_sheets__gpa_goals`
      via `format: sql`, covering an org row (`grade_low` 9 / `grade_high` 12),
      a school+grade row (`schoolid` 73253, 10/10, `direction` `>=`), and a `<=`
      row. Assert `aggregation_hash`, `grade_band`, `goal_proportion`,
      `higher_is_better`:

```text
org 9-12          -> aggregation_hash 'org_9-12',        grade_band '9-12'
school 73253 10-10 -> aggregation_hash '73253_10-10',    grade_band '10'
region Newark 11-11 direction '<='  -> higher_is_better false
goal 49           -> goal_proportion 0.49
```

- [ ] **Step 2: Run it — expect FAIL** (model absent):
      `uv run dbt test --select unit_gpa_goals_hash_and_direction --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --favor-state`

- [ ] **Step 3: Implement.** Mirror
      `int_google_sheets__topline_aggregate_goals` +
      `stg_google_sheets__topline_aggregate_goals`'s `grade_band` /
      `aggregation_hash` derivation, keyed by `org_level` (`'org'` | `region` |
      `cast(schoolid as string)`) with the grade-band suffix. Add
      `goal / 100.0 as goal_proportion` and
      `direction in ('>=', '>') as higher_is_better`. Grade band string:
      `if(grade_low = grade_high, cast(grade_high as string), grade_low || '-' || grade_high)`.

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Properties.** `description`s; uniqueness on (`academic_year`,
      `metric`, `aggregation_hash`).

- [ ] **Step 6: Commit.**

## Task 3: `int_gpa__goal_student_metrics` (per-student spine)

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_gpa__goal_student_metrics.sql`
- Create: `.../gpa/intermediate/properties/int_gpa__goal_student_metrics.yml`
- Add the `models/gpa/` config block to `src/dbt/kipptaf/dbt_project.yml` if the
  path is new (schema `gpa`, view default).

**Interfaces — Consumes:** `int_extracts__student_enrollments` (grain: student ×
`academic_year`; carries `region`, `school_name`, `grade_level`,
`enroll_status`, `student_number`, `cumulative_y1_gpa_projected_unweighted`,
`cumulative_y1_gpa_unweighted`) and `int_powerschool__gpa_term` (carries
`studentid`, `schoolid`, `academic_year`, `is_current`, `gpa_y1`,
`gpa_y1_unweighted`). **Produces:** one row per (`academic_year`, `region`,
`schoolid`, `grade_level`, `student_number`) with `y1_gpa_weighted`,
`y1_gpa_unweighted`, `cumulative_gpa_unweighted` (= projected unweighted),
`is_on_pace` boolean (null until Task 6), `is_on_pace_denominator` boolean (null
until Task 6).

- [ ] **Step 1: Write the failing unit test.**
      `unit_gpa_goal_student_metrics_grain` mocking both upstreams via
      `format: sql` for two students at one school in one grade, asserting the
      join yields one row per student with `y1_gpa_weighted` from `gpa_term` and
      `cumulative_gpa_unweighted` from the enrollments extract.

- [ ] **Step 2: Run it — expect FAIL.**

- [ ] **Step 3: Implement.** Join enrollments to `gpa_term` on
      (`student_number`↔`students`/`studentid`, `academic_year`, school)
      filtered to the year-level term (`gpa_term.is_current` or the `Y1` term —
      confirm which single term row to pick at build; there must be exactly one
      per student-year to preserve grain). Project the measures; set
      `is_on_pace` and `is_on_pace_denominator` to `cast(null as boolean)` with
      an inline comment `-- TODO(#4581): populate from on-pace follow-on`.
      Restrict to HS (`school_level = 'HS'`) and `enroll_status = 0`.

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Properties + uniqueness** on (`academic_year`, `schoolid`,
      `student_number`); build against real data
      (`uv run dbt build --select int_gpa__goal_student_metrics --target dev --defer --state <abs prod manifest> --favor-state`)
      and confirm one row per student-year.

- [ ] **Step 6: Commit.**

## Task 4: `int_gpa__goal_aggregations` (rollup + goal join + evaluation)

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_gpa__goal_aggregations.sql`
- Create: `.../properties/int_gpa__goal_aggregations.yml`

**Interfaces — Consumes:** `int_gpa__goal_student_metrics` (Task 3) and
`int_google_sheets__gpa_goals` (Task 2). **Produces:** one row per
(`academic_year`, `metric`, `aggregation_hash`) with `org_level`, `region`,
`schoolid`, `grade_band`, `goal_proportion`, `metric_rate` numeric,
`is_goal_met` boolean, `progress_to_goal` numeric.

- [ ] **Step 1: Write the failing unit test.** `unit_gpa_goal_aggregations`
      mocking both inputs via `format: sql`: a school+grade threshold goal
      (`metric` `y1_gpa_weighted`, `threshold` 3.0, `direction` `>=`, `goal` 58)
      over 4 students (2 at/above 3.0) → `metric_rate` 0.5, `is_goal_met` false
      (0.5 < 0.58), `progress_to_goal` ~0.862; plus an org all-grades row; plus
      a `<=` row asserting the derived direction flips `is_goal_met`.

- [ ] **Step 2: Run it — expect FAIL.**

- [ ] **Step 3: Implement.** Mirror `int_topline__dashboard_aggregations`: a
      `UNION ALL` of three blocks (`org_level` = school / region / org). Each
      groups the spine to its grain and left-joins
      `int_google_sheets__gpa_goals` on
      `grade_level between grade_low and grade_high`, `academic_year`, the
      org-level key, and `org_level`. Numerator per grouped goal row:

```text
metric_rate =
  case metric
    when 'on_pace'
      then safe_divide(countif(is_on_pace and is_on_pace_denominator),
                       countif(is_on_pace_denominator))
    else safe_divide(
      countif(
        (direction = '>=' and measure_value >= threshold)
        or (direction = '<=' and measure_value <= threshold)),
      count(student_number))
  end
```

where `measure_value` is selected by `metric` from the spine's three measure
columns (derive it as a named column in a CTE per the max-1-nesting rule — a
`case metric when 'y1_gpa_weighted' then y1_gpa_weighted ... end`). Then:

```text
is_goal_met      = if(higher_is_better, metric_rate >= goal_proportion,
                                        metric_rate <= goal_proportion)
progress_to_goal = least(1.0, if(higher_is_better,
                                 safe_divide(metric_rate, goal_proportion),
                                 safe_divide(goal_proportion, metric_rate)))
```

Null `goal_proportion` ⇒ null `is_goal_met` / `progress_to_goal`.

- [ ] **Step 4: Run it — expect PASS.**

- [ ] **Step 5: Properties + uniqueness** on (`academic_year`, `metric`,
      `aggregation_hash`).

- [ ] **Step 6: Commit.**

## Task 5: `rpt_tableau__gpa_goals` + exposure

**Files:**

- Create: `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goals.sql`
- Create: `.../extracts/tableau/properties/rpt_tableau__gpa_goals.yml`
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`

**Interfaces — Consumes:** `int_gpa__goal_aggregations` (Task 4). **Produces:**
a contracted view enumerating all aggregation columns.

- [ ] **Step 1:** Thin view — explicit column list from
      `int_gpa__goal_aggregations` (no `SELECT *` in `rpt_`).
- [ ] **Step 2:** Properties: `contract: enforced: true`, `description`s,
      uniqueness on (`academic_year`, `metric`, `aggregation_hash`).
- [ ] **Step 3:** Add the GPA-goals dashboard exposure to `tableau.yml`
      (`owner.name: Data Team`, `depends_on: [ref('rpt_tableau__gpa_goals')]`,
      `config.meta.dagster.kinds: [tableau]`).
- [ ] **Step 4:** Build `rpt_tableau__gpa_goals` + run its tests against dev.
- [ ] **Step 5:** `trunk check --force` all changed `.sql`/`.yml`; commit.

## Task 6 (GATED on Prerequisite 2): wire `on_pace`

**Files:** Modify `int_gpa__goal_student_metrics.sql` (+ its unit test).

- [ ] **Step 1:** Replace the null `is_on_pace` / `is_on_pace_denominator` with
      the real per-student flags from the on-pace follow-on (numerator =
      `is_on_pace_cumulative_3_0`; denominator = the priority-subset flag).
- [ ] **Step 2:** Extend `unit_gpa_goal_student_metrics_grain` and
      `unit_gpa_goal_aggregations` to cover the `on_pace` subset-denominator
      path (a student in the denominator but not on pace; a student excluded
      from the denominator).
- [ ] **Step 3:** Build + test; commit.

## End-to-end validation (after Tasks 1–5, sheet seeded)

Once Ops seeds real goal rows, build the chain
(`dbt build --select int_google_sheets__gpa_goals+ --target dev --defer --state <abs prod manifest> --favor-state`)
and spot-check that a known school+grade goal row produces the expected
`metric_rate` / `is_goal_met` against the detail extract. Report aggregates
only.
