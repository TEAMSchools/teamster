# Cumulative GPA Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `rpt_tableau__gpa_cumulative_year` with the current-state GPA
enrichment, GPA band labels, and a default-year flag, so a single student-year
table can drive the Cumulative GPA Monitor dashboard.

**Architecture:** One model changes. The year-grain extract gains a left join to
`int_powerschool__gpa_cumulative` gated on the model's existing `is_projected`
flag, so current-state values attach only to the current academic year's rows
and never overwrite 22 years of history. Band labels are derived in the extract.
A single-row CTE over `int_powerschool__gpa_term` supplies the latest year that
has posted Y1 grades. Goals come from `rpt_tableau__gpa_goals`, unchanged.

**Tech Stack:** dbt (BigQuery), sqlfluff/trunk, Tableau.

Spec: `docs/superpowers/specs/2026-07-29-cumulative-gpa-monitor-design.md`
Issue: [#4619](https://github.com/TEAMSchools/teamster/issues/4619)

## Global Constraints

- Every task runs `dbt` via `uv run` — never bare `dbt`.
- Project dir for every dbt call:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor/src/dbt/kipptaf`
- Dev builds need
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  The `--state` path must be absolute from a worktree.
- `rpt_tableau__gpa_cumulative_year` is contract-enforced by the `extracts/`
  directory default. Every new column needs a `properties.yml` entry with
  `data_type`, or the build fails.
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, trailing commas in
  `SELECT`, single-quoted strings, 88-char lines.
- ST06 column ordering in the final `SELECT`: plain refs grouped by source table
  in join order (`gcy`, then `e`, then `gcc`) with a blank line between groups,
  then logicals, then case statements.
- No `QUALIFY`, no `ORDER BY`, no subqueries against tables or CTEs, max one
  level of function nesting.
- Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree before any push. The `trunk` binary exists only in
  the main repo.
- Region scope stays `('Newark', 'Camden')`. Paterson and Miami have zero HS
  students in any year on record.

## Prerequisites

Neither blocks Tasks 1 through 4 — the extract work is independent. Both must
land before the dashboard's goal tiles are trustworthy.

- **[#4621](https://github.com/TEAMSchools/teamster/pull/4621) is merged**
  (2026-07-29) and live in production. It moved the goal-rate denominator to
  measured students and added `n_students_in_grain`, `n_students_measured`, and
  `n_students_met` to `rpt_tableau__gpa_goals`. Goal tiles can therefore treat a
  null rate as not-yet-measurable rather than as 0 percent attainment, and read
  `n_students_measured` to tell the two apart.
- **Ops populates three goal rows** in the GPA goals sheet, per the spec's _Goal
  integration_ table: Foundation 9th-grade at region grain for Newark and
  Camden, and the college-match goal at org grain for grade 11. The sheet
  currently holds one unrelated row, so the goal tiles have nothing to render
  until this happens.

## Five deviations from the spec, and why

**1. Band labels derive from `gcy`, not `gcc` — this is a correction.** The spec
says both band labels come from `gcc.cumulative_y1_gpa_projected_unweighted` /
`gcc.cumulative_y1_gpa_unweighted`. But `gcc` is left-joined only on
`is_projected`, so it is NULL on every prior-year row. Deriving the primary band
from it would leave 22 years of history with a null band and silently empty the
trend, splay, and equity surfaces — the reason the year-grain table exists at
all.

Corrected sourcing:

- `gpa_band_label` derives from `gcy.cumulative_y1_gpa_unweighted`, which is
  populated for every year. On prior years that is the year-end value; on the
  current year it is the projection (the model's own docstring states the
  current-year row IS the projected row). This single column serves trend,
  splay, equity, and the projected side of the distribution comparison.
- `gpa_band_as_of_today_label` derives from `gcc.cumulative_y1_gpa_unweighted`
  and is current-year-only by design — it is the "as of the last gradebook sync"
  series.

Task 2 Step 1 verifies the docstring's claim against prod before relying on it.

**2. `cumulative_y1_gpa_projected_unweighted` is NOT added.** The spec lists it,
but on the current-year row the existing `gcy.cumulative_y1_gpa_unweighted`
already holds exactly that value. Adding a second column with identical contents
invites drift. Instead Task 1 rewrites that column's description to state the
current-year semantics explicitly.

**3. The two integer band columns are NOT added.** The spec lists
`cumulative_y1_gpa_unweighted_band` and
`cumulative_y1_gpa_projected_unweighted_band`, but no surface in the spec's
dashboard-composition table consumes them — the labels serve every band need.
Omitted per YAGNI.

**4. The one-latest-year check is a singular test, not `expression_is_true`.**
The spec asks for `expression_is_true` asserting `is_latest_graded_year` is true
for exactly one year. That macro compiles to `where not (<expression>)` and
evaluates per row, so it cannot express a cross-row cardinality claim. Task 3
implements it as a singular test instead.

**5. `is_on_cusp_3_0` derives from `gcy`, not the spec's projected column.** The
spec defines the cusp on `cumulative_y1_gpa_projected_unweighted`, which is
`gcc`-sourced and therefore current-year-only. Task 3 sources it from
`gcy.cumulative_y1_gpa_unweighted` instead, for the same reason as deviation 1 —
so the cusp population exists across history and can be trended rather than
being visible for a single year. The shipped predicate is also half-open,
`>= 2.75 and < 3.00`, which closes the gap the spec's `between 2.75 and 2.999`
leaves open at values such as 2.9995.

## No unit test for this model, deliberately

`int_gpa__goal_aggregations` carries a unit test because its aggregation logic
is intricate. This model is a projection plus two joins: the `e` mock alone
would need 33 columns across 3 rows to satisfy the select list, and a mock
cannot catch the real-data surprises that matter here (whether `is_projected`
truly partitions the years, whether the docstring's projected-equals-current
claim holds). Each task therefore validates with a real dev build plus a named
prod query, and invariants are pinned as dbt data tests. This is a decision, not
an omission.

## File structure

| File                                                                                      | Responsibility                             |
| ----------------------------------------------------------------------------------------- | ------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`            | the extended extract                       |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml` | contract columns, descriptions, data tests |
| `src/dbt/kipptaf/tests/test_rpt_tableau__gpa_cumulative_year__one_latest_graded_year.sql` | singular test: exactly one year flagged    |
| `src/dbt/kipptaf/models/exposures/tableau.yml`                                            | new dashboard exposure                     |

---

### Task 1: Attach current-state enrichment to the current-year row only

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml`

**Interfaces:**

- Consumes: `int_powerschool__gpa_cumulative` (keyed `studentid`, `schoolid`,
  `_dbt_source_project`; no academic year — current state only).
- Produces: columns `cumulative_y1_gpa_unweighted_as_of_today` (float64),
  `gpa_needed_for_cumulative_3_0` (float64), `is_cumulative_3_0_attainable`
  (boolean), `potential_gpa_credits_current_year` (float64). Tasks 2 and 5 read
  these.

- [ ] **Step 1: Add the four contract column entries to the properties yml**

Insert immediately after the `school_leader_tableau_username` entry, at the end
of the `columns:` list:

```yaml
- name: cumulative_y1_gpa_unweighted_as_of_today
  data_type: float64
  description:
    Cumulative unweighted Y1 GPA as of the last gradebook sync, on current-year
    rows only. Distinct from `cumulative_y1_gpa_unweighted` on the same row,
    which is the year-end or projected value.
- name: gpa_needed_for_cumulative_3_0
  data_type: float64
  description:
    Weighted Y1 GPA needed across this year's GPA credits to finish with a 3.00
    projected unweighted cumulative. Current-year rows only. A negative value
    means the outcome is already guaranteed.
- name: is_cumulative_3_0_attainable
  data_type: boolean
  description:
    True when `gpa_needed_for_cumulative_3_0` is at or below the credit-weighted
    maximum achievable this year. Current-year rows only.
- name: potential_gpa_credits_current_year
  data_type: float64
  description:
    GPA credit hours in progress this year, used as the credits-in-progress
    figure on the cusp roster. Current-year rows only.
```

- [ ] **Step 2: Run the build to confirm it fails on the contract**

```bash
uv run dbt build --select rpt_tableau__gpa_cumulative_year \
  --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL. The contract declares four columns the SQL does not produce, so
`assert_columns_equivalent` reports them as missing from the model.

- [ ] **Step 3: Add the join and the four columns to the SQL**

Add the new plain-ref group after the `e` group, before the `from` clause
(preserving the blank line between groups for ST06):

```sql
    gcc.cumulative_y1_gpa_unweighted as cumulative_y1_gpa_unweighted_as_of_today,
    gcc.gpa_needed_for_cumulative_3_0,
    gcc.is_cumulative_3_0_attainable,
    gcc.potential_gpa_credits_current_year,
```

Add the join immediately after the existing `inner join ... as e` block and
before the `where` clause:

```sql
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gcc
    on gcy.studentid = gcc.studentid
    and gcy.schoolid = gcc.schoolid
    and gcy._dbt_source_project = gcc._dbt_source_project
    /* int_powerschool__gpa_cumulative is current-state, with no academic year.
       Gating on is_projected attaches it to the current-year row only; without
       the gate today's values get stamped onto every prior year. */
    and gcy.is_projected
```

- [ ] **Step 4: Rewrite the `cumulative_y1_gpa_unweighted` description**

Replace that column's existing `description:` in the properties yml with:

```yaml
description:
  Cumulative unweighted Y1 GPA as of the end of that academic year. On the
  current-year row this is the projected end-of-year value, matching
  `cumulative_y1_gpa_projected_unweighted` in the course-grain extract, so it is
  the correct basis for goal comparison. Use
  `cumulative_y1_gpa_unweighted_as_of_today` for the running value.
```

- [ ] **Step 5: Run the build to verify it passes**

Same command as Step 2. Expected: PASS, including the existing
`unique_combination_of_columns` on `student_number` + `academic_year`.

- [ ] **Step 6: Verify the gate actually partitions the years**

```sql
select
    is_projected,
    count(*) as n_rows,
    count(distinct academic_year) as n_years,
    countif(cumulative_y1_gpa_unweighted_as_of_today is not null) as n_as_of_today,
    countif(gpa_needed_for_cumulative_3_0 is not null) as n_needed,
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
group by is_projected
```

Expected on the `is_projected = false` row: `n_as_of_today = 0` and
`n_needed = 0` across many years. **This is the assertion that matters** — a
non-zero count here means the gate leaked and the task is not done.

Expected on the `is_projected = true` row: `n_years = 1`, and `n_as_of_today`
non-zero.

`n_needed` is expected to be **0 even on the true row** at the time of writing,
and that is correct, not a failure. `gpa_needed_for_cumulative_3_0`,
`is_cumulative_3_0_attainable`, and `potential_gpa_credits_current_year` all
divide by or derive from `potentialcrhrs_current`, which upstream sums credit
hours only where `academic_year = var('current_academic_year')`. That var is
2026 — SY26-27 — which has no course credit hours yet, so `safe_divide` nulls
the family. Verified: 0 non-null across all 27,044 rows of
`int_powerschool__gpa_cumulative`, while the projected family is populated
(25,674). These three columns come alive once the year's courses land, which is
also when the cusp roster becomes meaningful. Do not add a `not_null` test on
them, and do not treat their emptiness as a blocker.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml </dev/null
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml
git commit -m "feat(dbt): attach current-state gpa enrichment to the year extract" \
  -m "Refs #4619"
```

---

### Task 2: Derive the two GPA band labels

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml`

**Interfaces:**

- Consumes: `gcy.cumulative_y1_gpa_unweighted` (all years),
  `gcc.cumulative_y1_gpa_unweighted` (current year only, from Task 1).
- Produces: `gpa_band_label` and `gpa_band_as_of_today_label`, both string, both
  taking exactly the values `3.5+`, `3.0-3.49`, `2.5-2.99`, `2.0-2.49`,
  `below 2.0`, or NULL. Task 5 and every dashboard distribution surface read
  `gpa_band_label`.

- [ ] **Step 1: Verify the docstring's projected-equals-current-year claim**

Before deriving the primary band from `gcy`, confirm that on the current-year
row `gcy.cumulative_y1_gpa_unweighted` really equals the projected value. Run
against prod:

```sql
select
    count(*) as n_current_year_rows,
    countif(
        round(y.cumulative_y1_gpa_unweighted, 4)
        = round(c.cumulative_y1_gpa_projected_unweighted, 4)
    ) as n_matching,
    countif(
        y.cumulative_y1_gpa_unweighted is null
        and c.cumulative_y1_gpa_projected_unweighted is null
    ) as n_both_null,
from `teamster-332318.kipptaf_tableau.rpt_tableau__gpa_cumulative_year` as y
inner join
    `teamster-332318.kipptaf_powerschool.int_powerschool__gpa_cumulative` as c
    on y.studentid = c.studentid
    and y.schoolid = c.schoolid
    and y._dbt_source_project = c._dbt_source_project
where y.is_projected
```

Expected: `n_matching + n_both_null = n_current_year_rows`. If they do not
reconcile, STOP and report — the whole band-sourcing decision rests on this, and
the spec's original `gcc`-based sourcing would need revisiting instead.

- [ ] **Step 2: Add the two contract entries and an accepted_values test**

Append to the `columns:` list:

```yaml
- name: gpa_band_label
  data_type: string
  description:
    Cumulative unweighted GPA band for that academic year, from
    `cumulative_y1_gpa_unweighted` — the year-end value on prior years and the
    projected value on the current year. Populated for every year, so this is
    the band the trend, splay, and equity surfaces use. NULL when the student
    has no cumulative GPA.
  data_tests:
    - accepted_values:
        arguments:
          values:
            - 3.5+
            - 3.0-3.49
            - 2.5-2.99
            - 2.0-2.49
            - below 2.0
    - not_null:
        config:
          where: >-
            school_level = 'HS' and cumulative_y1_gpa_unweighted is not null
- name: gpa_band_as_of_today_label
  data_type: string
  description:
    Cumulative unweighted GPA band as of the last gradebook sync, from
    `cumulative_y1_gpa_unweighted_as_of_today`. Current-year rows only, so NULL
    on every prior year by design — pair it with `gpa_band_label` only within
    the current academic year.
  data_tests:
    - accepted_values:
        arguments:
          values:
            - 3.5+
            - 3.0-3.49
            - 2.5-2.99
            - 2.0-2.49
            - below 2.0
    - not_null:
        config:
          where: >-
            is_projected and school_level = 'HS' and
            cumulative_y1_gpa_unweighted_as_of_today is not null
```

The `not_null` tests are `where`-scoped because both labels are legitimately
NULL outside their scope — `gpa_band_label` where the student has no cumulative
GPA at all, and `gpa_band_as_of_today_label` on every prior-year row. An
unscoped `not_null` would fail on correct data.

Move both entries to the top of the `columns:` list, above
`_dbt_source_relation` — repo convention sorts columns carrying per-column
`data_tests:` to the top for visibility.

- [ ] **Step 3: Run the build to confirm it fails**

Same command as Task 1 Step 2. Expected: FAIL on the contract — two declared
columns the SQL does not produce.

- [ ] **Step 4: Add the two case expressions to the SQL**

Append after the `gcc` plain-ref group, separated by a blank line. Case
statements sort last under ST06, so these go at the very end of the `SELECT`:

```sql
    case
        when gcy.cumulative_y1_gpa_unweighted >= 3.50
        then '3.5+'
        when gcy.cumulative_y1_gpa_unweighted >= 3.00
        then '3.0-3.49'
        when gcy.cumulative_y1_gpa_unweighted >= 2.50
        then '2.5-2.99'
        when gcy.cumulative_y1_gpa_unweighted >= 2.00
        then '2.0-2.49'
        when gcy.cumulative_y1_gpa_unweighted < 2.00
        then 'below 2.0'
    end as gpa_band_label,

    case
        when gcc.cumulative_y1_gpa_unweighted >= 3.50
        then '3.5+'
        when gcc.cumulative_y1_gpa_unweighted >= 3.00
        then '3.0-3.49'
        when gcc.cumulative_y1_gpa_unweighted >= 2.50
        then '2.5-2.99'
        when gcc.cumulative_y1_gpa_unweighted >= 2.00
        then '2.0-2.49'
        when gcc.cumulative_y1_gpa_unweighted < 2.00
        then 'below 2.0'
    end as gpa_band_as_of_today_label,
```

- [ ] **Step 5: Run the build to verify it passes**

Same command. Expected: PASS, including both `accepted_values` tests.

- [ ] **Step 6: Verify boundaries and history coverage**

```sql
select
    gpa_band_label,
    count(*) as n_rows,
    count(distinct academic_year) as n_years,
    round(min(cumulative_y1_gpa_unweighted), 3) as min_gpa,
    round(max(cumulative_y1_gpa_unweighted), 3) as max_gpa,
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
where school_level = 'HS'
group by gpa_band_label
```

Expected: five non-null bands plus a NULL row. Each band's `min_gpa`/`max_gpa`
must fall inside its own boundaries — `3.0-3.49` must not contain a 3.5, and
`below 2.0` must not contain a 2.0. Critically, `n_years` must be large (many
historical years) for every band, not 1. An `n_years` of 1 means the band is
reading `gcc` and history is dark.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml </dev/null
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml
git commit -m "feat(dbt): add five-band gpa labels to the year extract" \
  -m "Refs #4619"
```

---

### Task 3: Add the cusp flag and the default-year flag

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml`
- Create:
  `src/dbt/kipptaf/tests/test_rpt_tableau__gpa_cumulative_year__one_latest_graded_year.sql`

**Interfaces:**

- Consumes: `int_powerschool__gpa_term` (`yearid`, `gpa_y1`). The canonical
  conversion is `academic_year = yearid + 1990`.
- Produces: `is_on_cusp_3_0` (boolean), `is_latest_graded_year` (boolean). The
  dashboard's default year filter and the cusp-roster count read these.

- [ ] **Step 1: Write the singular test**

Create the test file:

```sql
with
    flagged_years as (
        select distinct academic_year,
        from {{ ref("rpt_tableau__gpa_cumulative_year") }}
        where is_latest_graded_year
    )

select count(*) as n_flagged_years,
from flagged_years
having count(*) != 1
```

- [ ] **Step 2: Add the singular test description and the two contract entries**

Add to `src/dbt/kipptaf/tests/properties.yml` under `data_tests:`:

```yaml
- name: test_rpt_tableau__gpa_cumulative_year__one_latest_graded_year
  description:
    Exactly one academic year may carry `is_latest_graded_year`. More than one
    means the latest-graded-year CTE fanned out; zero means no year has posted
    Y1 grades, which would leave the dashboard with no default year.
```

Append to the extract's `columns:` list:

```yaml
- name: is_on_cusp_3_0
  data_type: boolean
  description:
    True when the year's cumulative unweighted GPA sits at or above 2.75 and
    below 3.00 — near enough to the 3.0 line to be worth targeting.
- name: is_latest_graded_year
  data_type: boolean
  description:
    True on rows of the most recent academic year that has posted Y1 grades. The
    dashboard defaults its year filter to this rather than to the maximum
    academic year, because the current year carries loaded schedules with no
    grades for the first months and would open on an empty view.
```

- [ ] **Step 3: Run the build to confirm it fails**

Same command as Task 1 Step 2. Expected: FAIL on the contract for the two
declared-but-absent columns. The singular test will also fail to compile against
a model without `is_latest_graded_year`.

- [ ] **Step 4: Add the CTE, the cross join, and the two columns**

Wrap the model in a leading CTE. The file currently opens with `select`; it must
now open with `with`:

```sql
with
    latest_graded_year as (
        /* the most recent year with posted Y1 grades. Cumulative earned credits
           cannot serve as this signal — they include prior years, so a
           not-yet-started year's upperclassmen already carry credits. */
        select max(yearid) + 1990 as latest_graded_academic_year,
        from {{ ref("int_powerschool__gpa_term") }}
        where gpa_y1 is not null
    )

select
```

Add to the end of the `SELECT`, before the case statements from Task 2 (logicals
sort ahead of case statements under ST06):

```sql
    gcy.academic_year = lgy.latest_graded_academic_year as is_latest_graded_year,

    gcy.cumulative_y1_gpa_unweighted >= 2.75
    and gcy.cumulative_y1_gpa_unweighted < 3.00 as is_on_cusp_3_0,
```

Add the cross join after the `gcc` join and before the `where` clause:

```sql
cross join latest_graded_year as lgy
```

- [ ] **Step 5: Run the build to verify it passes**

Same command. Expected: PASS, including the new singular test.

- [ ] **Step 6: Verify the flag lands on the expected year**

```sql
select
    academic_year,
    is_latest_graded_year,
    count(*) as n_rows,
    countif(is_on_cusp_3_0) as n_on_cusp,
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
where academic_year >= 2024
group by academic_year, is_latest_graded_year
order by academic_year
```

Expected: exactly one `academic_year` with `is_latest_graded_year = true`, and
it must be a year with posted grades — as of this writing 2025, not 2026. If
2026 is flagged, the `gpa_y1 is not null` filter is not doing its job.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml \
  src/dbt/kipptaf/tests/test_rpt_tableau__gpa_cumulative_year__one_latest_graded_year.sql \
  src/dbt/kipptaf/tests/properties.yml </dev/null
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml \
  src/dbt/kipptaf/tests/test_rpt_tableau__gpa_cumulative_year__one_latest_graded_year.sql \
  src/dbt/kipptaf/tests/properties.yml
git commit -m "feat(dbt): add cusp and latest-graded-year flags to the year extract" \
  -m "Refs #4619"
```

---

### Task 4: Register the exposure and correct the stale guidance

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml`

**Interfaces:**

- Consumes: nothing new.
- Produces: exposure `cumulative_gpa_monitor`. No column changes.

- [ ] **Step 1: Add the exposure**

Append to `src/dbt/kipptaf/models/exposures/tableau.yml`, matching the shape of
the neighbouring entries:

```yaml
- name: cumulative_gpa_monitor
  label: Cumulative GPA Monitor
  type: dashboard
  owner:
    name: Data Team
  depends_on:
    - ref("rpt_tableau__gpa_cumulative_year")
    - ref("rpt_tableau__gpa_goals")
  # TODO(#4619): update to the published Cumulative GPA Monitor workbook URL
  url: http://SAC-RPT-01/#/site/KIPPNJ/workbooks/TBD
  config:
    meta:
      dagster:
        kinds:
          - tableau
```

- [ ] **Step 2: Correct the model docstring**

The current `description:` tells the reader the table is "Related to
`rpt_tableau__student_course_grades` in Tableau on `student_number`" — that
guidance produced a cross-year fan-out, because the relationship carries no
academic year. Replace that sentence with:

```yaml
      Read this table on its own for the Cumulative GPA Monitor — one row per
      student-year, so student-grain measures need no relationship. Do NOT relate
      it to rpt_tableau__student_course_grades on student_number alone: that
      match carries no academic year and fans a student across every year they
      attended. Current seniors carry up to ten rows here.
```

- [ ] **Step 3: Replace the stale Paterson TODO comment**

In the SQL's `where` clause, replace these two comment lines:

```sql
    /* Miami hard-excluded: region unsupported in the rebuilt dashboard
       (#4340) */
    -- TODO(#4340): add Paterson once PS gradebook data is populated
```

with:

```sql
    /* Newark and Camden are the only regions with HS students on record —
       Paterson runs ES and MS only, and Miami has no HS rows in any year. This
       is not a coverage gap for an HS-grain dashboard; the region dimension
       stays so a future Paterson HS appears automatically. */
```

- [ ] **Step 4: Confirm the exposure parses and the model still builds**

```bash
uv run dbt parse \
  --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor/src/dbt/kipptaf \
  --target dev
uv run dbt build --select rpt_tableau__gpa_cumulative_year \
  --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: parse succeeds with the exposure count increased by one; build passes.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/exposures/tableau.yml \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml </dev/null
git add src/dbt/kipptaf/models/exposures/tableau.yml \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml
git commit -m "feat(dbt): add cumulative gpa monitor exposure and correct join guidance" \
  -m "Refs #4619"
```

---

### Task 5: Reconcile against the topline indicator

**Files:**

- No file changes. This task produces a reconciliation result recorded in the PR
  body.

**Interfaces:**

- Consumes: the finished extract, plus
  `kipptaf_topline.int_topline__student_metrics`.
- Produces: a documented match or a named discrepancy.

- [ ] **Step 1: Compute the at-3.0 rate from the new extract**

For the latest graded year, HS only:

```sql
select
    academic_year,
    count(*) as n_students,
    countif(cumulative_y1_gpa_unweighted >= 3.00) as n_at_3_0,
    round(
        safe_divide(
            countif(cumulative_y1_gpa_unweighted >= 3.00),
            countif(cumulative_y1_gpa_unweighted is not null)
        ),
        4
    ) as rate_at_3_0,
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
where is_latest_graded_year and school_level = 'HS'
group by academic_year
```

- [ ] **Step 2: Compute the same rate from the topline indicator**

Use the same year Step 1 returned — do not hardcode it, it moves each August:

```sql
with
    latest_graded as (
        select max(yearid) + 1990 as academic_year,
        from `teamster-332318.kipptaf_powerschool.int_powerschool__gpa_term`
        where gpa_y1 is not null
    )

select
    m.academic_year,
    count(distinct m.student_number) as n_students,
    round(safe_divide(sum(m.metric_value), count(*)), 4) as rate_at_3_0,
from `teamster-332318.kipptaf_topline.int_topline__student_metrics` as m
inner join latest_graded as l on m.academic_year = l.academic_year
where m.indicator = 'Projected Unweighted Cumulative GPA'
group by m.academic_year
```

- [ ] **Step 3: Compare and record**

The two read the same underlying column, so a material gap means the filter sets
differ — most likely the topline metric is weekly-grained and includes non-HS or
differently-scoped students, while this extract is HS-only at year grain. Record
the two numbers and the reason for any gap in the PR body. Do NOT adjust either
model to force a match without first identifying which filter differs.

- [ ] **Step 4: Push and open the PR**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cumulative-gpa-monitor
git push
```

Open the PR with `.github/pull_request_template.md` as the body. Note in the
summary: the three deviations from the spec and their rationale, the
reconciliation result from Step 3, and that the Tableau workbook is a separate
manual deliverable.

---

## Tableau workbook — manual, not agent-executable

The workbook is a GUI artifact; no task above builds it. These steps are for a
human, after the dbt PR merges and the extract refreshes in prod.

1. New data source against `kipptaf_tableau.rpt_tableau__gpa_cumulative_year` as
   a **single table**. Add no second table and no relationship — that is what
   makes the cross-year fan-out structurally impossible rather than merely
   filtered away.
1. Second data source against `kipptaf_tableau.rpt_tableau__gpa_goals` for the
   goal tiles.
1. Set the year filter's default to `is_latest_graded_year = true`.
1. Build the tiles per the spec's dashboard-composition table. Every rate is
   `countd` over the student grain — never an average of a row-level flag.
1. Distribution panel: `gpa_band_as_of_today_label` against `gpa_band_label`,
   shown only when the year filter is the current academic year. Outside that
   window the two are identical or the as-of-today side is empty, so label the
   panel in-session-only or collapse it to one bar.
1. Goal tiles: read the not-yet-measurable state from
   `rpt_tableau__gpa_goals.n_students_measured`. A null rate with a non-zero
   `n_students_in_grain` and a zero `n_students_measured` means no grades have
   posted — label it, do not render a bare blank tile.
1. Cusp roster: filter `is_on_cusp_3_0`, show `student_name`, `school`,
   `cumulative_y1_gpa_unweighted_as_of_today`, gap to 3.0,
   `potential_gpa_credits_current_year`, and `gpa_needed_for_cumulative_3_0`.
   Access is governed by the existing Tableau region and role gates; record in
   the PR which groups the workbook is published to.

   Expect this roster to render mostly empty until SY26-27 grades post. The
   default year filter uses `is_latest_graded_year`, which currently resolves to
   2025, while the current-state columns attach to the `is_projected` year, 2026
   — different years today. On the default slice
   `cumulative_y1_gpa_unweighted_as_of_today`, `gpa_needed_for_cumulative_3_0`,
   `potential_gpa_credits_current_year`, `gpa_band_as_of_today_label`, and
   `is_cumulative_3_0_attainable` are all null, so the roster shows students
   with three of five columns blank and the spec's students-to-move tile reads
   zero. The two flags coincide from roughly November onward and everything
   populates. This is the expected pre-season state, not a broken join.

1. Update the `cumulative_gpa_monitor` exposure URL and drop the `TODO(#4619)`.

## Deferred to a separate spec

Every college-enrollment surface — the projected-enrollment tile, the
gap-to-goal box, the students-to-move count, and the enrollment-goal diamonds on
the by-grade chart. Those rest on an assumed constant (enrollment approximately
the 3.0-and-above rate plus 15 points) with no warehouse source. Fitting it
means joining historical graduating cohorts' HS cumulative GPA to their actual
`kippadb` college enrollment.
