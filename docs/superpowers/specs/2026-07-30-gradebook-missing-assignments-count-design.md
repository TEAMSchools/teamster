# Missing-assignment count for `rpt_tableau__student_course_grades`

Refs [#4655](https://github.com/TEAMSchools/teamster/issues/4655)

## Problem

The rebuilt gradebook dashboards (Academic Health Home, School Grade Analysis)
want a per-student-per-course count of missing assignments, with a link out to
DeansList for the detail. `rpt_tableau__student_course_grades` carries grades,
GPA, and category percentages but no assignment-level signal at all — its
description states it is deliberately decoupled from the gradebook-audit
lineage.

This is a count only. DeansList remains the system of record for which
assignments are missing, and this change does not rebuild missing-assignment
reporting.

## Scope

One new intermediate model and one new contract column on the extract.

| Change                                              | File                                                                                            |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| New aggregate                                       | `models/powerschool/intermediate/int_powerschool__gradebook_missing_assignments.sql`            |
| Its properties, config, and uniqueness test         | `models/powerschool/intermediate/properties/int_powerschool__gradebook_missing_assignments.yml` |
| One left join, one projected column, one CTE column | `models/extracts/tableau/rpt_tableau__student_course_grades.sql`                                |
| One contract column                                 | `models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`                     |

All paths relative to `src/dbt/kipptaf/`.

## Data model

### Where the count comes from

The count is derived from the **PowerSchool** assignment lineage. Nothing on the
DeansList side is a source — `rpt_deanslist__missing_assignments` is an
_outbound_ extract that Dagster pushes to DeansList as
`deanslist_missing_assignments.json.gz`. Both surfaces are downstream of the
same PowerSchool rows, which is why they can be made to agree exactly.

```text
int_powerschool__section_grade_config   (filtered storecode_type = 'Q')
  → int_powerschool__gradebook_assignments   (sectionsdcid + duedate in termbin)
    → stg_powerschool__assignmentscore       (assignmentsectionid + studentsdcid)
```

### `grading_formula_weighting_type` is per-storecode, not per-section

This is the structural fact the design rests on, and it is easy to get wrong.
`int_powerschool__section_grade_config` holds one row per
`(section, storecode)`, and in NJ the weighting type partitions cleanly by
`storecode_type`:

| `storecode_type` | `storecode`s | `grading_formula_weighting_type` |
| ---------------- | ------------ | -------------------------------- |
| `Q`              | `Q1`-`Q4`    | `Total_Points`                   |
| `W`/`H`/`S`/`F`  | `W1`-`F4`    | `Category_Weighting`             |

So the two union branches of `rpt_tableau__gradebook_assignments` are not two
kinds of section. They are the quarter-grain and category-grain views of the
same assignments. Every HS section is in both — NCA 516 of 516, NLH 304 of 304,
KHS 315 of 315.

Filtering to `storecode_type = 'Q'` therefore:

- yields exactly one config row per `(section, quarter)`, so no `category_id`
  join is needed and no fan-out is possible;
- reads the same branch the DeansList feed reads, which is what makes the
  reconciliation exact;
- covers ES. 529 sections have `Q` storecodes but no category storecodes, and
  every one of them is ES (SPARK, LSP, Seek, KURA, THRIVE, Life) — ES does not
  use gradebook categories. A category-keyed count is blank for 79.2% of ES
  quarter rows.

Both branches were measured and produce the same count, so this choice costs
nothing in accuracy: on the strictest definition, Newark 156,912 and Camden
73,975 in both.

### The new intermediate

`int_powerschool__gradebook_missing_assignments`, landing in
`kipptaf_powerschool`.

**Grain**: one row per
`(_dbt_source_project, sections_dcid, quarter, studentsdcid)`. `quarter` is
`Q1`-`Q4` plus a `Y1` row carrying the section-year total. Roughly 205,000 rows
for two academic years of NJ.

**Keyed on `studentsdcid`, not `studentid`.** `stg_powerschool__assignmentscore`
is natively keyed on `studentsdcid`, so there is no identifier translation
anywhere in the model. This matches both existing models in this lineage:
`rpt_tableau__gradebook_assignments` joins `enr.students_dcid = s.studentsdcid`,
and `int_powerschool__gradebook_assignments_scores` carries `students_dcid` with
no `studentid`.

An earlier draft joined `stg_powerschool__students` to translate `studentsdcid`
to `studentid`. That was dropped. It is unnecessary —
`base_powerschool__course_enrollments` already carries `students_dcid` — and it
introduced a latent hazard: `stg_powerschool__students` is unique only on
`(_dbt_source_project, dcid)`, with 2,108 duplicate bare `dcid` values
network-wide because the key is region-scoped. The join was safe only because
every predicate carried `_dbt_source_project`. Removing it eliminates the
dependency rather than relying on it.

**Year scope**:
`term_start_date >= date({{ var("current_academic_year") - 1 }}, 7, 1)`,
mirroring the extract's own two-year window and self-maintaining across the July
rollover. If a future consumer wants full history back to 2016, that filter is
the single thing to relax.

**Materialization**: `materialized: table` set in the properties YAML, not
inline `{{ config() }}`. No automation-condition override — the default
`dbt_table_automation_condition()` is eager (rebuild on any upstream update),
which is what we want.

### The extract change

`course_enrollments` gains one column in its projection, `m.students_dcid`, and
a single left join is added after the `category_grades` join, mirroring its
shape:

```sql
left join
    {{ ref("int_powerschool__gradebook_missing_assignments") }} as ma
    on s.`quarter` = ma.`quarter`
    and s._dbt_source_project = ma._dbt_source_project
    and ce.students_dcid = ma.studentsdcid
    and ce.sections_dcid = ma.sections_dcid
    and ce._dbt_source_project = ma._dbt_source_project
```

Both join keys come from the same `ce` row, so they cannot disagree.
`students_dcid` stays inside the CTE and is **not** projected to the final
`SELECT`, so the contract change is exactly one column.

`ma.n_missing_assignments` is projected after the `c.category_*` block and
before the `coalesce(...)` / `if(...)` expressions, per ST06 column ordering.

## Decisions and rationale

### Count raw `ismissing = 1`

No `isexempt` or `iscountedinfinalgrade` exclusion.

The DeansList detail list a dean clicks through to is fed by our own
`ismissing = 1` extract. Any exclusion means the dashboard badge says 12 and the
list opens with 13 rows — a count that contradicts the list it links to, not a
cosmetic rounding difference.

Measured cost of the alternatives, against the count that lands in the extract:

| Definition                                       | Newark  | vs raw | Camden | vs raw |
| ------------------------------------------------ | ------- | ------ | ------ | ------ |
| `ismissing = 1` (chosen)                         | 139,893 | —      | 64,936 | —      |
| `and isexempt = 0`                               | 135,258 | -3.3%  | 63,177 | -2.7%  |
| `and isexempt = 0 and iscountedinfinalgrade = 1` | 134,777 | -3.7%  | 62,230 | -4.2%  |

The counter-argument is real and should be recorded: this repo already has a
more defensible measure in
`int_powerschool__gradebook_assignments_scores.is_expected_missing`
(`is_missing = 1` and not exempt and `iscountedinfinalgrade = 1`). It is the
right measure for gradebook _audit_ purposes. It is the wrong one here, because
the requirement is agreement with the system of record — and PowerSchool's
`ismissing` flag is also what teachers and families see in the portal.

### Do not source from the gradebook-audit lineage

`int_powerschool__gradebook_assignments_scores` looks like the DRY choice. It is
not usable here.

It applies an enrolment-window guard
(`duedate >= cc_dateenrolled and duedate < cc_dateleft`) plus
`not is_dropped_section`, which puts its count 11% below DeansList: Newark
145,026 against 163,679; Camden 69,301 against 77,670. Its guard is arguably
_more_ correct — PowerSchool auto-assigns every section assignment to a student
on enrolment, including work due before they arrived — but
`rpt_tableau__gradebook_assignments` has no such guard, so DeansList already
includes that work. It also carries no termbin or quarter dimension, and using
it would re-couple this extract to the audit lineage it was deliberately
decoupled from.

### Cover both academic years, NULL when out of scope

AY2026 has **zero** gradebook assignments today (both regions), even though
section and termbin config exists. Consequently prod
`rpt_tableau__gradebook_assignments` holds 296,320 AY2026 rows with zero
`ismissing = 1`, and `rpt_deanslist__missing_assignments` currently returns 0
rows.

Mirroring the sibling model's `cc_academic_year = current_academic_year` filter
would therefore ship a column that is 100% NULL on merge day, unvalidatable by
anyone for weeks, with the prior-year rows the dashboard already shows
permanently blank. Covering both years populates AY2025 immediately and lets
AY2026 fill in as teachers post work.

NULL rather than `coalesce(..., 0)`: the extract's convention is
NULL-out-of-scope for every as-of-today measure, and printing "0 missing
assignments" across all 92,417 AY2026 rows would be affirmatively false rather
than merely blank. Tableau can apply `ZN()` per view, scoped to the selected
year, which dbt cannot.

### Quarter rows plus a `Y1` section-year total

`Q1`-`Q4` rows carry that quarter's count. `Y1` rows — the extract's
one-row-per-student-course grain, and the shape the consumer asked for — carry
the year total, produced by a second `union all` branch that regroups without
`quarter`.

The alternative of populating only `Y1` was rejected: the count would vanish the
moment a user picks a quarter, and the quarter selector is exactly where this
dashboard already trips people up.

### Join on section, not course number

0.24% of `(student, course, year)` triples span more than one section (103
Newark, 32 Camden), and the extract's `rn_course_number_year = 1` keeps only the
latest. Section-keying therefore undercounts those rows against the DeansList
list by 200 assignments network-wide in Newark and 0 in Camden — 0.14% of the
Newark total.

That is the right trade. The extract row _is_ about one section: `teacher_name`,
`section_number`, and `external_expression` all describe it. Attributing another
section's missing work here would file it under the wrong teacher's name.

## Why a new model rather than a CTE

Three prior column-adds to this extract used inline CTEs, and
`prior_year_gpa_rollup` is already an aggregate-with-`GROUP BY` inside the
reporting view — so an inline CTE would have been the consistent choice. It was
rejected for one reason: **a CTE cannot carry a test.**

The count depends on three uniqueness invariants that are all currently
untested:

| Model                                    | Invariant                             | Existing coverage                    |
| ---------------------------------------- | ------------------------------------- | ------------------------------------ |
| `int_powerschool__section_grade_config`  | `(sections_dcid, storecode)` unique   | none                                 |
| `int_powerschool__gradebook_assignments` | `assignmentsectionid` unique          | none                                 |
| `stg_powerschool__assignmentscore`       | `(assignmentsectionid, studentsdcid)` | `unique` on `assignmentscoreid` only |

Each was verified to hold today, but nothing keeps it holding. The failure mode
is a silent multiplication of every count on two live dashboards. A
`dbt_utils.unique_combination_of_columns` test on the intermediate guards the
composition of all three at the grain the dashboards consume, in kipptaf where
CI actually runs it — and because the model is a table, that test re-runs on
data change. Per `src/dbt/CLAUDE.md`, view-materialized models are not
re-materialized by the data-change automation condition, so their tests rarely
re-run; a view-materialized intermediate would get neither the test cadence nor
the plan flattening.

Secondary benefits: it keeps the extract view's plan flat (inline would take it
from 26 to roughly 38 expanded base tables, and `src/dbt/CLAUDE.md` notes the
`query is too complex` failure fires on fan-out width well below the 16-view
limit), and the extract SQL is already 606 lines with 5 CTEs and 6 joins.

Cost is not a factor either way: the aggregate scans 0.65 GiB, taking the
extract from 1.28 to roughly 1.94 GiB per query (+51%), about +$1/month against
observed usage of 60-170 queries per day. The inline variant was executed
against production and planned cleanly, so this is a maintainability choice, not
a performance rescue.

Extending an existing intermediate was considered and rejected:
`int_powerschool__category_grades` has the wrong grain and is a source-system
package model (a column add there triggers the two-PR district-then-kipptaf
sequence); `int_powerschool__gradebook_assignment_scores_rollup` is at
class-assignment grain with no student.

## Contract and tests

The extract inherits `contract: enforced: true` from `extracts/` and enumerates
columns explicitly, so both the SQL and the properties YAML change.

```yaml
- name: n_missing_assignments
  data_type: int64
```

`int64`, because `countif()` returns `INT64`. `numeric` and `float64` are
distinct BigQuery types and a mismatch passes `dbt parse` then fails contract
enforcement at build. Sibling counts (`gpa_n_failing_y1`,
`n_failing_y1_prior_quarter`) are all `int64`.

The description must carry the repetition warning: the value repeats identically
across the four `W`/`H`/`S`/`F` rows of a quarter, so a naive `SUM` over AY2025
reads 1,023,976 against a true 204,829 — a fivefold overcount. `MIN`, `MAX`,
`AVG`, or a single-category filter are correct. This matches the behaviour of
every other course-grain column in the extract.

**No test change on the extract.** The existing composite uniqueness test is
unaffected (proven below). No `not_null` — the column is legitimately NULL on
28% of AY2025 rows and all of AY2026. No range test — `countif()` cannot return
a negative, so it could never fail.

**One test on the intermediate**, per the convention that intermediate models
carry a uniqueness test:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - _dbt_source_project
          - studentsdcid
          - sections_dcid
          - quarter
```

## Validation

Measured against production on 2026-07-30 at `academic_year = 2025`. AY2026
returns zero rows everywhere and looks like a broken join.

**Grain.** Baseline extract: 713,212 rows, 713,176 distinct on the
uniqueness-test key (the 36-row gap is the pre-existing prior-year
`storedgrades` double-write, `TODO(#3915)`, warn-level). After the left join:
713,212 rows and 713,176 distinct PKs — unchanged on both measures, with zero
DCID lookup failures. Verified for the `studentid`-keyed and
`studentsdcid`-keyed variants and for a category-keyed variant; all three
preserved the grain and the first two matched row-for-row at 512,729 rows
populated.

**Reconciliation.** Against a DeansList-equivalent set (the
`Total_Points`/`storecode_type = 'Q'` branch, `ismissing = 1`, year filter
shifted to AY2025), restricted to the extract's population and deduplicated to
one row per `(student, section, quarter, assignment)`:

| Region | Students | Agreeing | Disagreeing | Sum of absolute differences |
| ------ | -------- | -------- | ----------- | --------------------------- |
| Newark | 6,442    | 6,442    | 0           | 0                           |
| Camden | 2,141    | 2,141    | 0           | 0                           |

Totals 139,893 (Newark) and 64,936 (Camden) on both sides.

Two differences exist between the raw feeds and are expected, not defects.
DeansList double-counts by roughly 2% (3,199 Newark, 3,318 Camden rows) because
it drives from `base_powerschool__course_enrollments`, one row per enrolment
stint; the aggregate's `GROUP BY` removes this incidentally. And DeansList has a
wider population — 246,638 NJ rows against 204,829 landing in the extract,
decomposing entirely into filters the extract already applies to every other
column (student not in the extract 10,088/7,879; dropped section 12,001/5,400;
excluded course number 242/0; non-primary section 200/0; other 496/0), plus
Miami, which the extract hard-excludes per #4340.

The practical consequence to communicate: a dean summing the DeansList feed
network-wide gets a larger number than the dashboard, because the dashboard
scopes to currently or recently enrolled NJ students on their primary section.
For any individual student on any individual course-term, the two agree exactly.

**Build checks.**

```bash
uv run dbt build \
  --select int_powerschool__gradebook_missing_assignments+ \
  --project-dir src/dbt/kipptaf \
  --target dev --defer --state target/prod
```

Then `trunk check --force` the changed SQL, YAML, and this document from inside
the worktree, using the absolute binary path — markdownlint and sqlfluff fire at
pre-push and CI, not at the pre-commit `fmt` hook.

## Out of scope

Each of these was considered and deliberately excluded.

- **Uniqueness tests on the three upstream package models.** The right fix for
  the root gap, but they live in `src/dbt/powerschool/` and are consumed by
  three districts, and dbt Cloud CI gives a no-op run for district-only changes
  — it would not be validated in this PR. Follow-up issue.
- **The missing dbt exposure for this extract.** Convention requires one, and
  none exists for `rpt_tableau__student_course_grades` or
  `rpt_tableau__gradebook_assignments` today. Deferred because the only Tableau
  consumer is an unpublished datasource in a personal project whose LSID changes
  on republish, so an exposure written now would be wrong the moment it became
  true. Ship it when the workbooks reach Production, without `cron_schedule`
  unless Dagster owns the refresh.
- **The DeansList feed's stint double-count.** A genuine upstream bug this
  investigation surfaced. Separate issue, and per `src/dbt/CLAUDE.md` not
  something to defensively dedupe around.
- **`ismissing = 1 and isexempt = 1`** on 6,152 Newark and 2,492 Camden score
  rows, a source contradiction. Inside the count by design; data-quality item.
- **Miami and Paterson.** Miami is hard-excluded from the extract per #4340;
  Paterson has no `int_powerschool__section_grade_config` relation in the
  three-way union and no HS. No change needed for either.

## Open questions

- `max(n_missing_assignments)` is 145 for a single course-quarter. Plausible,
  but worth a sanity check with Academics before publishing.
- 58 Camden sections carry a NULL `grading_formula_weighting_type` on
  `F3`/`F4`/`S2`/`S3`/`S4` (290 rows), so they fall out of _both_ union branches
  of `rpt_tableau__gradebook_assignments`. The `Q`-branch design here is
  unaffected, but it may indicate a mis-set grade formula in Camden worth a
  separate look.
