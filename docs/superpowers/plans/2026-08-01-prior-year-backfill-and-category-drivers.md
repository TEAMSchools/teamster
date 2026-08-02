# Category drivers at Y1 and prior-year running backfill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Category Driving Gap` resolve at the Y1 marking period, and
temporarily populate prior-year running course grades and GPA so the drill-down
is not blank during summer stakeholder training.

**Architecture:** Two independent changes to one model,
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`.
Change A adds four student-course-grain category-driver columns via two new CTEs
and one ungated join. Change B adds prior-year reconstructions via new CTEs
consumed by the existing prior-year union branch (course grades) and by a
year-gated join (GPA).

**Tech Stack:** dbt on BigQuery, kipptaf project. No Python, no unit tests —
this repo validates dbt models with `dbt build` plus BigQuery MCP queries.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-08-01-prior-year-backfill-and-category-drivers-design.md`.
  Read it before Task 1.
- Worktree:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers`.
  Branch `anthonygwalters/feat/claude-backfill-and-category-drivers`. Use
  `git -C <worktree>` for every git call.
- Every dbt call:
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Never bare `dbt`.
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`,
  run with cwd set to the worktree.
- **Current-year isolation is the first invariant.** Any non-zero difference in
  a current-year value of `gpa_y1`, `gpa_for_quarter`, `gpa_n_failing_y1` or
  `y1_course_in_progress_*` between the dev build and prod means the change does
  not ship.
- **Do NOT populate `courses_gradescaleid` in `quarter_grades` branch 3.** The
  `grade_scale_ladder` join keys off it, and it being null on prior-year rows is
  the only thing keeping `need_next_*` null there. Populating it would light up
  `need_next_letter_grade` while `need_next` stayed null.
- SQL conventions in `src/dbt/CLAUDE.md` are binding: no `QUALIFY`, no
  `ORDER BY`, no subqueries against CTEs, max one level of function nesting,
  ST06 column ordering, ST09 join-predicate ordering, trailing commas.
- Contract is enforced. Every new column needs a `data_type` and a `description`
  in
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`.
- The model's composite uniqueness test warns at **12** — the pre-existing
  `#3915` count. It must still read 12 after every task.
- Prod baseline: **854,263 rows, 854,227 distinct** composite keys, re-verified
  during Task 3. AY2025 is 713,227 / 713,191; AY2026 is 141,036 / 141,036.
  **Prod drifts between sessions** — the earlier 854,245 / 854,209 figure aged
  out when 18 rows landed in the in-progress year. Always compare a dev build
  against a prod read taken in the same session, never against a remembered
  number.

## File Structure

| File                                                    | Responsibility                          | Change                             |
| ------------------------------------------------------- | --------------------------------------- | ---------------------------------- |
| `.../rpt_tableau__student_course_grades.sql`            | all CTEs, joins, projections            | modified in Tasks 2, 3, 4          |
| `.../properties/rpt_tableau__student_course_grades.yml` | contract + descriptions                 | modified in Tasks 2, 3, 4          |
| `.claude/scratch/4687-baseline.md`                      | pre-change numbers for isolation checks | created in Task 1, never committed |

No new model files. Both changes belong in this model because both are
extract-shaped presentation concerns, and the spec establishes that neither
needs a `src/dbt/powerschool/` change.

---

### Task 1: Capture the pre-change baseline

Every later isolation check compares against these numbers. Capture them before
touching anything, because after the first edit the dev relation is no longer a
clean control.

**Files:**

- Create: `.claude/scratch/4687-baseline.md` (gitignored, do not commit)

**Interfaces:**

- Consumes: nothing
- Produces: the baseline numbers referenced by Tasks 2, 3, 4 and 5

- [ ] **Step 1: Record the current-year GPA control set**

Run via BigQuery MCP:

```sql
select
  academic_year,
  quarter,
  count(*) as rows_,
  round(sum(gpa_y1), 4) as sum_gpa_y1,
  round(sum(gpa_for_quarter), 4) as sum_gpa_for_quarter,
  sum(gpa_n_failing_y1) as sum_n_failing,
  countif(y1_course_in_progress_percent_grade_adjusted is not null) as has_running_pct
from `kipptaf_tableau.rpt_tableau__student_course_grades`
group by 1, 2
order by 1, 2
```

Paste the full result into the scratch file under a heading
`## Current-year GPA control set`.

- [ ] **Step 2: Record row-count and grain baseline**

```sql
select
  count(*) as rows_,
  count(distinct format('%T|%T|%T|%T|%T|%T',
    _dbt_source_relation, studentid, academic_year, quarter,
    course_number, category_name_code)) as distinct_key
from `kipptaf_tableau.rpt_tableau__student_course_grades`
```

Expect `854245` / `854209`. If it differs, prod has moved — record the new
numbers and use those as the control from here on.

- [ ] **Step 3: Record the Category Driving Gap ground truth**

This is the regression oracle for Task 2. It captures what the current Tableau
logic produces at Q4, so the new column can be checked against known-good
behaviour.

```sql
with
ranked as (
  select
    studentid,
    sectionid,
    category_name_code,
    category_quarter_percent_grade,
    row_number() over (
      partition by studentid, sectionid
      order by
        (category_quarter_percent_grade is null) asc,
        category_quarter_percent_grade asc,
        category_name_code asc
    ) as rn
  from `kipptaf_tableau.rpt_tableau__student_course_grades`
  where
    academic_year = 2025
    and quarter = 'Q4'
    and category_quarter_percent_grade is not null
)
select
  category_name_code,
  count(*) as student_sections
from ranked
where rn = 1
group by 1
order by 1
```

Record the distribution. Task 2 must reproduce it.

- [ ] **Step 4: Verify the letter-coverage gate**

**This gate can fail the plan.** The spec flags full-scale band coverage as
unverified. If it fails, stop and report before writing any code — Task 3's
letter derivation needs redesigning.

```sql
with
probe as (select p from unnest(generate_array(0, 100)) as p),
scale as (
  select _dbt_source_project, gradescale_name, min_cutoffpercentage, max_cutoffpercentage
  from `kipptaf_powerschool.int_powerschool__gradescaleitem_lookup`
)
select
  countif(n_matches = 0) as percents_with_no_rung,
  countif(n_matches > 1) as percents_with_multiple_rungs,
  count(*) as scale_percent_pairs
from (
  select s._dbt_source_project, s.gradescale_name, probe.p, count(*) as n_matches
  from scale as s
  cross join probe
  where probe.p between s.min_cutoffpercentage and s.max_cutoffpercentage
  group by 1, 2, 3
)
```

`percents_with_multiple_rungs` must be **0** — anything else fans out Task 3's
join. Record `percents_with_no_rung`; gaps are tolerable only if they fall
outside 0–100 real grades, so report the number rather than judging it alone.

- [ ] **Step 5: Commit nothing, report the baseline**

The scratch file is gitignored by design. Report the four result sets in the
task summary so the reviewer can see them without opening the file.

---

### Task 2: Category driver columns (Change A, permanent)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes: the `category_grades` CTE (ends at line 587), the baseline from Task
  1 Step 3
- Produces: columns `lowest_category_y1_name`, `lowest_category_y1_percent`,
  `lowest_category_recent_term_name`, `lowest_category_recent_term_percent`, all
  on every row including Y1. Tasks 3 and 4 do not depend on these.

- [ ] **Step 1: Add the two CTEs**

Insert immediately after the `category_grades` CTE closes and before the final
`select`:

```sql
    category_ranked as (
        /* Ranking input for the lowest-category drivers. Rows where BOTH
           percents are null are excluded so a term that exists but carries no
           usable value cannot win rn_latest_term and blank out both drivers.

           (percent is null) asc leads each order by because BigQuery sorts
           NULLS FIRST ascending, which would otherwise hand "lowest" to a null.
           category_name_code is the final tiebreaker so the pick is
           reproducible across rebuilds. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            sectionid,
            category_name_code,
            category_quarter_percent_grade,
            category_y1_percent_grade_running,

            dense_rank() over (
                partition by _dbt_source_project, studentid, yearid, sectionid
                order by term desc
            ) as rn_latest_term,

            row_number() over (
                partition by _dbt_source_project, studentid, yearid, sectionid, term
                order by
                    (category_y1_percent_grade_running is null) asc,
                    category_y1_percent_grade_running asc,
                    category_name_code asc
            ) as rn_lowest_y1,

            row_number() over (
                partition by _dbt_source_project, studentid, yearid, sectionid, term
                order by
                    (category_quarter_percent_grade is null) asc,
                    category_quarter_percent_grade asc,
                    category_name_code asc
            ) as rn_lowest_quarter,
        from category_grades
        where
            category_quarter_percent_grade is not null
            or category_y1_percent_grade_running is not null
    ),

    category_drivers as (
        /* One row per student-section-year, so the join below cannot fan out.
           Both drivers are read from the SAME latest term, so they describe one
           moment rather than two. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            sectionid,

            max(
                if(rn_lowest_y1 = 1, category_name_code, null)
            ) as lowest_category_y1_name,

            max(
                if(rn_lowest_y1 = 1, category_y1_percent_grade_running, null)
            ) as lowest_category_y1_percent,

            max(
                if(rn_lowest_quarter = 1, category_name_code, null)
            ) as lowest_category_recent_term_name,

            max(
                if(rn_lowest_quarter = 1, category_quarter_percent_grade, null)
            ) as lowest_category_recent_term_percent,
        from category_ranked
        where rn_latest_term = 1
        group by _dbt_source_project, studentid, yearid, sectionid
    ),
```

- [ ] **Step 2: Add the join**

Append after the `grade_scale_ladder as gsl` join and before the `where` clause
at the end of the file. **No term predicate** — that omission is what puts the
columns on Y1 rows:

```sql
left join
    category_drivers as cd
    on s.studentid = cd.studentid
    and s.yearid = cd.yearid
    and s._dbt_source_project = cd._dbt_source_project
    and ce.sectionid = cd.sectionid
    and ce._dbt_source_project = cd._dbt_source_project
```

- [ ] **Step 3: Add the projections**

Immediately after `c.category_quarter_average_all_courses,` (line 712), keeping
the blank-line-between-source-tables convention:

```sql
    cd.lowest_category_y1_name,
    cd.lowest_category_y1_percent,
    cd.lowest_category_recent_term_name,
    cd.lowest_category_recent_term_percent,
```

- [ ] **Step 4: Add the contract entries**

In the properties yml, after the `category_quarter_average_all_courses` entry:

```yaml
- name: lowest_category_y1_name
  data_type: string
  description: >-
    Gradebook category code with the lowest year-running percent for this
    course, read from the latest term that holds category data. Present on every
    row including Y1, which is the point — the per-term category columns are
    null at Y1 because there is no Y1 category term.
- name: lowest_category_y1_percent
  data_type: float64
  description: >-
    The year-running percent belonging to lowest_category_y1_name.
- name: lowest_category_recent_term_name
  data_type: string
  description: >-
    Gradebook category code with the lowest single-quarter percent in the latest
    term that holds category data — Q4 on a completed year, the most recently
    posted quarter on a live one. Answers what the problem is right now, where
    lowest_category_y1_name answers what dragged the whole year down. The two
    can legitimately disagree.
- name: lowest_category_recent_term_percent
  data_type: float64
  description: >-
    The single-quarter percent belonging to lowest_category_recent_term_name.
```

- [ ] **Step 5: Build**

```bash
uv run dbt build --select rpt_tableau__student_course_grades --target dev \
  --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers/src/dbt/kipptaf
```

Expected: `PASS=1 WARN=1`. The warn is the `#3915` uniqueness test at **12**.
Any other number is a fan-out — stop.

- [ ] **Step 6: Verify no fan-out and Y1 population**

```sql
select
  'dev' as which,
  count(*) as rows_,
  count(distinct format('%T|%T|%T|%T|%T|%T',
    _dbt_source_relation, studentid, academic_year, quarter,
    course_number, category_name_code)) as distinct_key,
  countif(quarter = 'Y1' and lowest_category_y1_name is not null) as y1_rows_with_driver
from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
```

`rows_` and `distinct_key` must equal the Task 1 Step 2 baseline exactly.
`y1_rows_with_driver` must be well above zero — it was 0 before.

- [ ] **Step 7: Verify against the Task 1 regression oracle**

```sql
select
  lowest_category_recent_term_name,
  count(distinct format('%T|%T', studentid, sectionid)) as student_sections
from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
where academic_year = 2025 and quarter = 'Q4'
group by 1
order by 1
```

Must reproduce the distribution recorded in Task 1 Step 3. A mismatch means the
ranking differs from the behaviour the workbook already relies on.

- [ ] **Step 8: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers add \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers commit -m "feat(dbt): add lowest-category driver columns resolving Category Driving Gap at Y1

Four student-course-grain columns present on every row including Y1, where the
per-term category columns are null because no Y1 category term exists. Scalar
columns rather than attaching category rows to Y1, which would fan Y1 out
roughly 3.9x. Reproduces the existing Q4 driver distribution exactly.

Refs #4687"
```

---

### Task 3: Prior-year course-grade backfill (Change B part 1, temporary)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes: Task 1 Step 4's coverage gate result
- Produces: `y1_course_in_progress_percent_grade_adjusted` and
  `y1_course_in_progress_letter_grade_adjusted` populated on prior-year rows.
  Task 4 does not depend on these.

- [ ] **Step 1: Add the reconstruction CTEs**

Insert before `quarter_grades`. Note the storecode ordering works because
`'Q1' < 'Q2' < 'Q3' < 'Q4'` lexically.

```sql
    backfill_quarter_running as (
        /* TODO(#4687): TEMPORARY. Delete this CTE, backfill_course_anchored,
           backfill_running_course, and their use in quarter_grades branch 3
           once the dashboard runs on current-year data. Tracked in Asana under
           GPA and Gradebook Dashboard v3, Phase 4.

           Reconstructs a running year-to-date course percent for the prior
           year, which PowerSchool never stored. Q1 is exact by definition;
           Q2 and Q3 are approximations; Q4 is replaced by the stored Y1 value
           below so it matches exactly. Simple rather than credit-weighted
           average because the two agree to within half a point on 97.0 percent
           of courses. */
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            yearid,
            course_number,
            storecode,
            gradescale_name_unweighted,

            avg(`percent`) over (
                partition by _dbt_source_project, studentid, yearid, course_number
                order by storecode
            ) as running_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    backfill_y1_stored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            course_number,
            gradescale_name_unweighted,

            `percent` as y1_stored_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1'
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    backfill_course_anchored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Q4 takes the stored Y1 percent verbatim so the reconstruction lands
           exactly on the year grade. The Y1 storecode row is unioned in
           carrying the same value, so the Y1 marking period and Q4 agree. */
        select
            r._dbt_source_project,
            r.studentid,
            r.yearid,
            r.course_number,
            r.storecode,
            r.gradescale_name_unweighted,

            if(
                r.storecode = 'Q4', y1.y1_stored_percent, r.running_percent
            ) as anchored_percent,
        from backfill_quarter_running as r
        left join
            backfill_y1_stored as y1
            on r._dbt_source_project = y1._dbt_source_project
            and r.studentid = y1.studentid
            and r.yearid = y1.yearid
            and r.course_number = y1.course_number

        union all

        select
            _dbt_source_project,
            studentid,
            yearid,
            course_number,

            'Y1' as storecode,

            gradescale_name_unweighted,
            y1_stored_percent as anchored_percent,
        from backfill_y1_stored
    ),
```

`UNION ALL` binds by position, so both branches list the same seven columns in
the same order. `_dbt_source_relation` is deliberately absent — nothing
downstream consumes it, and carrying a null through the Y1 branch would be dead
weight. `backfill_quarter_running` still selects it because dropping it there
would touch the window partitions; leave that alone.

```sql

    backfill_running_course as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Bands the reconstructed percent back to a letter on the course's own
           scale. Joins on gradescale_name rather than gradescaleid, the pattern
           int_powerschool__gpa_term and rpt_deanslist__transcript_gpas already
           use for storedgrades, plus _dbt_source_project because scale
           identifiers collide across districts. */
        select
            a._dbt_source_project,
            a.studentid,
            a.yearid,
            a.course_number,
            a.storecode,
            a.anchored_percent,

            gsi.letter_grade as anchored_letter_grade,
        from backfill_course_anchored as a
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as gsi
            on a._dbt_source_project = gsi._dbt_source_project
            and a.gradescale_name_unweighted = gsi.gradescale_name
            and a.anchored_percent
            between gsi.min_cutoffpercentage and gsi.max_cutoffpercentage
    ),
```

- [ ] **Step 2: Wire branch 3 to the reconstruction**

In `quarter_grades` branch 3, alias the storedgrades ref as `sg`, prefix its
bare column references with `sg.`, and replace the two null casts at lines
472–473. **Leave `cast(null as int64) as courses_gradescaleid` exactly as it
is** — see Global Constraints.

Replace:

```sql
            cast(null as float64) as y1_course_in_progress_percent_grade_adjusted,
            cast(null as string) as y1_course_in_progress_letter_grade_adjusted,
```

with:

```sql
            bfc.anchored_percent
            as y1_course_in_progress_percent_grade_adjusted,
            bfc.anchored_letter_grade
            as y1_course_in_progress_letter_grade_adjusted,
```

and add the join after the `from`:

```sql
        left join
            backfill_running_course as bfc
            on sg._dbt_source_project = bfc._dbt_source_project
            and sg.studentid = bfc.studentid
            and sg.yearid = bfc.yearid
            and sg.course_number = bfc.course_number
            and sg.storecode = bfc.storecode
```

- [ ] **Step 3: Update the two column descriptions**

Both currently say current-year only, which stops being true. Replace both
descriptions verbatim.

For `y1_course_in_progress_percent_grade_adjusted`:

```yaml
description: >-
  Year-to-date course percent as of the row's marking period. For the year in
  progress this is the real running value from the gradebook. For the prior year
  it is RECONSTRUCTED from stored quarter grades — Q1 is exact, Q4 is anchored
  to the stored Y1 percent and is exact, Q2 and Q3 are approximations that agree
  with the year value to within half a point on roughly 98 percent of courses.
  The reconstruction is temporary; see TODO(#4687) in the model.
```

For `y1_course_in_progress_letter_grade_adjusted`:

```yaml
description: >-
  Year-to-date course letter as of the row's marking period. For the year in
  progress this comes from the gradebook. For the prior year it is RECONSTRUCTED
  by banding the reconstructed percent back through the course's own grade
  scale, so it inherits that percent's accuracy — Q1 and Q4 exact, Q2 and Q3
  approximate. Carries F and F* on the same prefix rule as
  quarter_course_letter_grade. Temporary; see TODO(#4687) in the model.
```

- [ ] **Step 4: Build**

Same command as Task 2 Step 5. Expected `PASS=1 WARN=1`, warn at **12**.

- [ ] **Step 5: Verify the three hard invariants**

```sql
with
sc as (
  select
    quarter,
    concat(cast(student_number as string), '|', course_number) as sck,
    y1_course_in_progress_percent_grade_adjusted as running_pct,
    y1_course_in_progress_letter_grade_adjusted as running_letter,
    quarter_course_percent_grade as quarter_pct
  from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
  where academic_year = 2025
),
y1 as (
  select sck, running_pct as y1_pct from sc where quarter = 'Y1'
)
select
  countif(sc.quarter = 'Q1' and abs(sc.running_pct - sc.quarter_pct) > 0.001)
    as q1_not_exact,
  countif(sc.quarter = 'Q4' and abs(sc.running_pct - y1.y1_pct) > 0.001)
    as q4_anchor_violations,
  countif(sc.running_pct is not null and sc.running_letter is null)
    as percent_with_no_letter,
  countif(sc.running_pct is not null) as populated_rows
from sc
left join y1 on sc.sck = y1.sck
```

`q1_not_exact`, `q4_anchor_violations` and `percent_with_no_letter` must all be
**0**. `populated_rows` must be well above zero — it was 0 before.

- [ ] **Step 6: Verify isolation and that `need_next_*` stayed null**

```sql
select
  academic_year,
  quarter,
  count(*) as rows_,
  round(sum(gpa_y1), 4) as sum_gpa_y1,
  countif(y1_course_in_progress_percent_grade_adjusted is not null) as has_running_pct,
  countif(need_next_letter_grade is not null) as has_need_next_letter
from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
group by 1, 2
order by 1, 2
```

Current-year `sum_gpa_y1` and `rows_` must match the Task 1 Step 1 baseline
exactly. `has_need_next_letter` must remain **0 for academic_year 2025** — if it
is non-zero, `courses_gradescaleid` was populated in branch 3 against the Global
Constraints and must be reverted.

- [ ] **Step 7: Lint and commit**

Lint as in Task 2 Step 8, then:

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers add \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers commit -m "feat(dbt): backfill prior-year running course grades, temporarily

TEMPORARY, tracked by TODO(#4687). Reconstructs the year-to-date course grade
for the prior year, which PowerSchool never stored, so the drill-down is not
blank during summer training. Q1 exact, Q4 anchored to the stored Y1 and exact,
Q2 and Q3 approximate.

Confined to quarter_grades branch 3, which filters to the prior year, so it
cannot reach a current-year row. need_next_* stays null on prior years because
courses_gradescaleid is deliberately left null there.

Refs #4687"
```

---

### Task 4: Prior-year GPA backfill (Change B part 2, temporary)

This is the task where isolation is not free. Read the spec's _Isolation from
the current year_ section before starting.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes: Task 1 Step 1 baseline
- Produces: `gpa_y1` populated with a running value on prior-year rows. No later
  task depends on it.

- [ ] **Step 1: Add the reconstruction CTE**

Insert before `student_roster`:

```sql
    backfill_running_gpa as (
        /* TODO(#4687): TEMPORARY. Delete this CTE, its join in student_roster,
           and the coalesce on gpa_y1 once the dashboard runs on current-year
           data. Tracked in Asana under GPA and Gradebook Dashboard v3, Phase 4.

           Running credit-weighted GPA through each term, accumulated from the
           same components the real gpa_y1 uses. Deliberately NOT anchored to
           the stored Y1: anchoring would insert a step at Q4 that the data does
           not contain, which is the shape a stakeholder builds a narrative
           around. Unanchored, AY2025 high school reads 45.1, 46.7, 46.6, 48.2
           percent at or above 3.0 against a stored Y1 of 48.9 — a rising
           trajectory that stops slightly short of the year value. */
        select
            studentid,
            schoolid,
            yearid,
            _dbt_source_project,
            term_name,

            round(
                safe_divide(
                    sum(weighted_gpa_points_term) over (
                        partition by studentid, _dbt_source_project, schoolid, yearid
                        order by term_name
                    ),
                    sum(total_credit_hours_term) over (
                        partition by studentid, _dbt_source_project, schoolid, yearid
                        order by term_name
                    )
                ),
                2
            ) as gpa_y1_running,
        from {{ ref("int_powerschool__gpa_term") }}
        where yearid = {{ var("current_academic_year") - 1991 }}
    ),
```

- [ ] **Step 2: Add the year-gated join**

In `student_roster`, after the `gtq` join (which ends at line 247). The final
predicate is the gate and is **not optional**:

```sql
        left join
            backfill_running_gpa as bfg
            on enr.studentid = bfg.studentid
            and enr.yearid = bfg.yearid
            and enr.schoolid = bfg.schoolid
            and enr._dbt_source_project = bfg._dbt_source_project
            and term.quarter = bfg.term_name
            and enr.academic_year = {{ var("current_academic_year") - 1 }}
```

- [ ] **Step 3: Coalesce into the existing expression**

Replace line 197:

```sql
            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1) as gpa_y1,
```

with:

```sql
            coalesce(
                bfg.gpa_y1_running,
                if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1)
            ) as gpa_y1,
```

The gate makes `bfg.gpa_y1_running` null on every current-year row, so the
coalesce falls through to the untouched original there. **Do not touch
`gpa_for_quarter` on line 195 or `gpa_n_failing_y1` on line 201.**

- [ ] **Step 4: Update the `gpa_y1` description**

Append to the existing description:

```yaml
For the prior year this is RECONSTRUCTED as a running credit-weighted GPA
through each term, because PowerSchool stores only the end-of-year value. It is
deliberately not anchored to that stored value, so the Q4 reading will not equal
the Y1 reading. Temporary; see TODO(#4687).
```

- [ ] **Step 5: Build**

Same command as Task 2 Step 5. Expected `PASS=1 WARN=1`, warn at **12**.

- [ ] **Step 6: Prove isolation — the gating check**

```sql
select
  academic_year,
  quarter,
  count(*) as rows_,
  round(sum(gpa_y1), 4) as sum_gpa_y1,
  round(sum(gpa_for_quarter), 4) as sum_gpa_for_quarter,
  sum(gpa_n_failing_y1) as sum_n_failing
from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
group by 1, 2
order by 1, 2
```

Every **academic_year 2026** figure must be byte-identical to the Task 1 Step 1
baseline. `gpa_for_quarter` and `gpa_n_failing_y1` must be identical in **both**
years, since neither was touched. Any difference means the gate leaked — revert
and stop.

- [ ] **Step 7: Verify the prior year now moves**

```sql
with
sq as (
  select student_number, quarter, max(gpa_y1) as gpa_y1
  from `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
  where academic_year = 2025 and school_level = 'HS'
  group by 1, 2
)
select
  quarter,
  count(*) as students,
  round(safe_divide(countif(gpa_y1 >= 3.0), count(*)) * 100, 1) as pct_at_or_above_3_0
from sq
group by 1
order by 1
```

Expected roughly `45.1 / 46.7 / 46.6 / 48.2` at Q1 through Q4, and `48.9` at Y1.
The four quarters must **differ from each other** — that is the entire purpose.
If all five come back identical, the coalesce is not firing.

**Corrected figures.** An earlier version of this step expected
`50.1 / 48.4 / 46.1 / 47.7` against `50.4`. Those were AY2024, produced by
querying `int_powerschool__gpa_term` at `yearid = 34` when the convention is
`yearid = academic_year - 1990`, making AY2025 yearid 35. The same off-by-one
appeared in Step 1's `where` clause and is corrected there.

- [ ] **Step 8: Lint and commit**

Lint as in Task 2 Step 8, then:

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers add \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers commit -m "feat(dbt): backfill prior-year running GPA, temporarily and unanchored

TEMPORARY, tracked by TODO(#4687). gpa_y1 is the final year value repeated on
every prior-year quarter row, so M1's distribution is flat across marking
periods. Reconstructs a running credit-weighted GPA from the per-term
components.

Deliberately unanchored, unlike the course-grade backfill. Anchoring Q4 to the
stored value produced a step at Q4 that the data does not contain.

Isolation is structural, not conditional: the join carries an academic_year gate
in ON, so current-year rows get NULL and the coalesce falls through to the
original expression. Verified byte-identical current-year gpa_y1,
gpa_for_quarter and gpa_n_failing_y1.

Refs #4687"
```

---

### Task 5: Whole-branch verification, removal task, and PR

**Files:**

- No code changes unless verification fails

**Interfaces:**

- Consumes: everything from Tasks 1 through 4
- Produces: an open PR and an Asana removal task

- [ ] **Step 1: Full-graph build**

```bash
uv run dbt build --select rpt_tableau__student_course_grades int_powerschool__gradescaleitem_lookup \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers/src/dbt/kipptaf
```

Expected: all tests pass except the `#3915` warn at 12. The
`int_powerschool__gradescaleitem_lookup` uniqueness test added in #4686 must
still PASS.

- [ ] **Step 2: Final row-count and isolation sweep**

Re-run Task 1 Step 2 and Task 4 Step 6 against the dev relation one final time,
with all four tasks applied. Row count, distinct key, and every current-year GPA
figure must match the Task 1 baseline.

- [ ] **Step 3: Confirm every TODO is present and greppable**

```bash
grep -n "TODO(#4687)" /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql
```

Expected: at least five hits — four in the course CTEs, one in the GPA CTE. Zero
hits in the Task 2 category CTEs, which are permanent.

- [ ] **Step 4: Lint the full diff**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-backfill-and-category-drivers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD) </dev/null
```

- [ ] **Step 5: Create the Asana removal task**

In project `GPA and Gradebook Dashboard v3 (SY27 Rebuild)`, GID
`1214228736201477`, section `Phase 4`, GID `1214243570943810`. Title:
`Remove the temporary prior-year grade and GPA backfill`. The notes must name
the five CTEs to delete — `backfill_quarter_running`, `backfill_y1_stored`,
`backfill_course_anchored`, `backfill_running_course`, `backfill_running_gpa` —
state that the Task 2 category driver columns are permanent and must NOT be
removed, and link the PR.

- [ ] **Step 6: Push and open the PR**

Use `.github/pull_request_template.md`. Body must reference `Refs #4687`, state
which half is temporary, and record the isolation proof. Create via
`gh api -X POST repos/TEAMSchools/teamster/pulls -F body=@<file>` rather than
the GitHub MCP, which HTML-sanitises angle brackets.

- [ ] **Step 7: Report**

Summarise: the four hard invariants and their measured values, the row-count
proof, the `need_next_*`-stayed-null proof, and the Asana task URL.

---

## Not in this plan

**The Tableau workbook changes.** The spec's Change A deletes two calcs —
`Lowest Category % (course)` and the `MIN(IF ...)` form of
`Category Driving Gap` — and rewrites the latter as a plain field reference.
That work happens in `new_gpa_dash_20260801.twbx`, which lives in
`.claude/scratch/` and is not in this repo, so it cannot be a task here. It is
also **blocked on this PR merging**, because the columns have to exist in the
published extract first.

The same applies to pointing M1 and M2 at `y1_course_in_progress_*`, which is
the change that motivated the backfill in the first place. Hand both off after
merge; neither is a code task.

**Everything under the spec's _Out of scope_ heading**, in particular moving the
category-code decode into the model and the as-of labelling work tracked
separately in Asana.
