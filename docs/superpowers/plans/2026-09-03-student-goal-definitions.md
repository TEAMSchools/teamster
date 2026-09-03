# Student-Grain GPA Goal Definitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put each student's GPA goal on their own row, so the Cumulative GPA
Monitor reads one Tableau data source instead of two.

**Architecture:** A new intermediate resolves every student to the org, region
and school goal for their grade. A new thin `rpt_` wrapper selects
`rpt_tableau__gpa_cumulative_year` unchanged and left joins those goal columns
on. Nothing published is modified.

**Tech Stack:** dbt (kipptaf project), BigQuery, `uv run dbt`.

**Spec:** `docs/superpowers/specs/2026-09-01-student-goal-definitions-design.md`

## Global Constraints

- Work in the worktree at
  `/workspaces/teamster/.worktrees/claude-student-goal-definitions`. Every git
  call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`.
- **Do not modify `rpt_tableau__gpa_cumulative_year`, `rpt_tableau__gpa_goals`
  or `rpt_tableau__student_course_grades`.** Two published dashboards read them.
  This constraint is the reason the wrapper exists.
- `--state` from a worktree must be the ABSOLUTE main-repo path
  `/workspaces/teamster/src/dbt/kipptaf/target/prod`.
- Models under `extracts/` are contract-enforced. Every column needs a
  `data_type` and a `description` in the properties yml or the build fails.
- Repo SQL rules: no import CTEs, no subqueries, no `ORDER BY`, no `QUALIFY`,
  max one level of function nesting, trailing commas, single quotes, explicit
  column lists in a final `rpt_` select.
- sqlfluff ST09: in an `ON` clause, the earlier-referenced table goes on the
  left.
- The project sets `data_tests: +severity: warn`. Every test in this plan needs
  an explicit `config: severity: error`.

---

## File Structure

| File                                                                                       | Responsibility                                                        |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/gpa/intermediate/int_gpa__student_goal_definitions.sql`            | Resolve student to goal at three rungs                                |
| `src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__student_goal_definitions.yml` | Contract-free properties, descriptions, uniqueness and not-null tests |
| `src/dbt/kipptaf/tests/int_gpa__student_goal_definitions__org_rung_covers_all_rungs.sql`   | Guard the inner join: no school or region goal without an org parent  |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql`               | Passthrough of the extract plus four goal columns                     |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml`    | Contract-enforced properties for 56 columns                           |
| `src/dbt/kipptaf/models/exposures/tableau.yml`                                             | Point the `gpa_cumulative_monitor` exposure at the wrapper            |

---

## Task 1: `int_gpa__student_goal_definitions`

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_gpa__student_goal_definitions.sql`
- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__student_goal_definitions.yml`
- Create:
  `src/dbt/kipptaf/tests/int_gpa__student_goal_definitions__org_rung_covers_all_rungs.sql`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments` (columns `academic_year`,
  `student_number`, `region`, `schoolid`, `grade_level`, `rn_year`);
  `int_google_sheets__gpa_goals` (columns `academic_year`, `org_level`,
  `region`, `schoolid`, `grade_low`, `grade_high`, `metric`, `threshold`,
  `direction`, `goal_proportion`, `higher_is_better`).
- Produces: a model at grain `(academic_year, student_number, metric)` with
  columns `academic_year` int64, `student_number` int64, `metric` string,
  `threshold` numeric, `direction` string, `higher_is_better` boolean,
  `goal_proportion_org` numeric, `goal_proportion_region` numeric,
  `goal_proportion_school` numeric. Task 2 joins on `student_number` and
  `academic_year`, filtered to `metric = 'cumulative_gpa_unweighted'`.

- [ ] **Step 1: Install dbt packages in the fresh worktree**

A new worktree has no `dbt_packages/`. Every later dbt call fails without this.

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/claude-student-goal-definitions/src/dbt/kipptaf
```

Expected: `Installed from ...` lines, no error.

- [ ] **Step 2: Find your dev schema name**

You need it to query build output. Run in the BigQuery MCP or `bq`:

```sql
select schema_name
from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA
where schema_name like 'zz_%kipptaf_gpa'
```

Note the result. Referred to below as `<dev_gpa_schema>`.

- [ ] **Step 3: Write the model SQL**

Create
`src/dbt/kipptaf/models/gpa/intermediate/int_gpa__student_goal_definitions.sql`:

```sql
select
    e.academic_year,
    e.student_number,

    go.metric,
    go.threshold,
    go.direction,
    go.higher_is_better,
    go.goal_proportion as goal_proportion_org,

    gr.goal_proportion as goal_proportion_region,

    gs.goal_proportion as goal_proportion_school,
from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_google_sheets__gpa_goals") }} as go
    on e.academic_year = go.academic_year
    and e.grade_level between go.grade_low and go.grade_high
    and go.org_level = 'org'
left join
    {{ ref("int_google_sheets__gpa_goals") }} as gr
    on e.academic_year = gr.academic_year
    and e.region = gr.region
    and e.grade_level between gr.grade_low and gr.grade_high
    and go.metric = gr.metric
    and gr.org_level = 'region'
left join
    {{ ref("int_google_sheets__gpa_goals") }} as gs
    on e.academic_year = gs.academic_year
    and e.schoolid = gs.schoolid
    and e.grade_level between gs.grade_low and gs.grade_high
    and go.metric = gs.metric
    and gs.org_level = 'school'
where e.rn_year = 1
```

The inner join on the org rung scopes the population — a student in a grade with
no goal produces no row, which is how grades K through 8 drop out without a
`school_level` filter and without naming a region.

- [ ] **Step 4: Write the properties yml**

Create
`src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__student_goal_definitions.yml`:

```yaml
models:
  - name: int_gpa__student_goal_definitions
    description: >-
      Resolves each student to the GPA goal that applies to them, at the
      network, region, and school rung, for every metric with a goal. One row
      per student, academic year, and metric. Carries the goal definition — the
      threshold a student must clear and the target share of students expected
      to clear it — never a computed rate, so a consumer can compute its own
      actual rate against whatever population is on screen. Scoped by the inner
      join to the network-rung goal, so a student in a grade with no goal
      produces no row at all rather than a row of nulls. A null
      goal_proportion_region means that metric has no region-rung goal, which is
      true of y1_gpa_weighted.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - academic_year
              - student_number
              - metric
          config:
            severity: error
    columns:
      - name: academic_year
        data_type: int64
        description: KIPP academic year (July start) the goal applies to.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: student_number
        data_type: int64
        description:
          PowerSchool student number of the student the goal applies to.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: metric
        data_type: string
        description: >-
          Which GPA measure the goal is written against —
          `cumulative_gpa_unweighted` or `y1_gpa_weighted`.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: threshold
        data_type: numeric
        description: >-
          GPA a student must reach to count toward the goal. Read from the
          network-rung row; identical across rungs.
      - name: direction
        data_type: string
        description: >-
          Comparison operator the threshold is applied with, as text. Read from
          the network-rung row.
      - name: higher_is_better
        data_type: boolean
        description: >-
          True when clearing the threshold means scoring above it. Read from the
          network-rung row.
      - name: goal_proportion_org
        data_type: numeric
        description: >-
          Target share of students network-wide expected to clear the threshold,
          as a proportion.
      - name: goal_proportion_region
        data_type: numeric
        description: >-
          Target share for the student's region. NULL when the metric has no
          region-rung goal.
      - name: goal_proportion_school
        data_type: numeric
        description: >-
          Target share for the student's school. NULL when the metric has no
          school-rung goal.
```

`goal_proportion_org` gets no `not_null` test. The inner join makes it
non-nullable by construction, and the repo forbids a test that cannot fail.

- [ ] **Step 5: Write the coverage guard test**

Create
`src/dbt/kipptaf/tests/int_gpa__student_goal_definitions__org_rung_covers_all_rungs.sql`.
It returns rows when a school- or region-rung goal has no matching network-rung
goal — the one failure mode that would silently delete students from the model.

```sql
with
    org_goals as (
        select academic_year, metric, grade_low, grade_high,
        from {{ ref("int_google_sheets__gpa_goals") }}
        where org_level = 'org'
    )

select
    n.academic_year,
    n.metric,
    n.org_level,
    n.grade_low,
    n.grade_high,
from {{ ref("int_google_sheets__gpa_goals") }} as n
left join
    org_goals as o
    on n.academic_year = o.academic_year
    and n.metric = o.metric
    and n.grade_low = o.grade_low
    and n.grade_high = o.grade_high
where n.org_level != 'org' and o.academic_year is null
```

- [ ] **Step 6: Register the test's description and severity**

Add to `src/dbt/kipptaf/tests/properties.yml`, under the existing `data_tests:`
list:

```yaml
- name: int_gpa__student_goal_definitions__org_rung_covers_all_rungs
  description: >-
    Asserts every region- and school-rung GPA goal has a network-rung goal at
    the same academic year, metric, and grade band.
    int_gpa__student_goal_definitions inner joins the network rung to scope its
    population, so a school goal without a network parent would drop those
    students with no error.
  config:
    severity: error
```

- [ ] **Step 7: Build the model and run its tests**

```bash
uv run dbt build --select int_gpa__student_goal_definitions \
  --project-dir /workspaces/teamster/.worktrees/claude-student-goal-definitions/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: model builds; `unique_combination_of_columns`, three `not_null` tests,
and the coverage test all PASS.

If the uniqueness test FAILS, stop. It means `(student_number, academic_year)`
is not unique in `int_extracts__student_enrollments` at `rn_year = 1`, or an
overlapping grade band was added to the goals sheet. Diagnose before changing
the model — do not add a dedupe.

- [ ] **Step 8: Verify the join cannot fan out for the wrapper**

The wrapper filters to one metric. Confirm that yields at most one row per
student-year. Assert it directly; do not infer it from a row count.

```sql
select count(*) as offending_rows
from (
  select academic_year, student_number
  from `teamster-332318.<dev_gpa_schema>.int_gpa__student_goal_definitions`
  where metric = 'cumulative_gpa_unweighted'
  group by academic_year, student_number
  having count(*) > 1
)
```

Expected: `offending_rows = 0`.

- [ ] **Step 9: Verify the goal values match the published goals**

```sql
select distinct
  e.grade_level,
  g.threshold,
  g.goal_proportion_org,
from `teamster-332318.<dev_gpa_schema>.int_gpa__student_goal_definitions` as g
inner join `teamster-332318.kipptaf_tableau.rpt_tableau__gpa_cumulative_year` as e
  on g.student_number = e.student_number
  and g.academic_year = e.academic_year
where g.academic_year = 2026 and g.metric = 'cumulative_gpa_unweighted'
order by e.grade_level
```

Expected: exactly four rows. Threshold 3 at every grade, and
`goal_proportion_org` of 0.69 at grade 9, 0.64 at grade 10, 0.60 at grade 11,
0.56 at grade 12. More than four rows means a grade resolved to two different
goals.

- [ ] **Step 10: Lint**

```bash
cd /workspaces/teamster/.worktrees/claude-student-goal-definitions && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/gpa/intermediate/int_gpa__student_goal_definitions.sql \
  src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__student_goal_definitions.yml \
  src/dbt/kipptaf/tests/int_gpa__student_goal_definitions__org_rung_covers_all_rungs.sql \
  </dev/null
```

If `.trunk/tools/trunk` does not exist, use `~/.cache/trunk/launcher/trunk`.
Expected: no sqlfluff or yamllint findings. Formatting findings are fixed by the
commit hook.

- [ ] **Step 11: Commit**

```bash
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions add \
  src/dbt/kipptaf/models/gpa/intermediate/int_gpa__student_goal_definitions.sql \
  src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__student_goal_definitions.yml \
  src/dbt/kipptaf/tests/int_gpa__student_goal_definitions__org_rung_covers_all_rungs.sql \
  src/dbt/kipptaf/tests/properties.yml
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions commit -m "feat(dbt): resolve each student to their GPA goal at three org rungs

Refs #5097"
```

---

## Task 2: `rpt_tableau__gpa_goal_progress`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml`

**Interfaces:**

- Consumes: `rpt_tableau__gpa_cumulative_year` (52 columns, unchanged);
  `int_gpa__student_goal_definitions` from Task 1.
- Produces: a contract-enforced model at grain `(student_number, academic_year)`
  with those 52 columns under their original names plus `gpa_goal_threshold`
  numeric, `gpa_goal_proportion_org` numeric, `gpa_goal_proportion_region`
  numeric, `gpa_goal_proportion_school` numeric. The Cumulative GPA Monitor
  reads this model.

- [ ] **Step 1: Write the model SQL**

Create
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql`.
Every passthrough column keeps its exact name — Tableau's Replace Data Source
only preserves calculated fields when captions match, and this model is
eventually replaced by the extract itself.

```sql
select
    cy._dbt_source_relation,
    cy._dbt_source_project,
    cy.studentid,
    cy.academic_year,
    cy.schoolid,
    cy.grade_level,
    cy.is_projected,
    cy.earned_credits_cum,
    cy.potential_gpa_credits_cum,
    cy.cumulative_y1_gpa,
    cy.cumulative_y1_gpa_unweighted,
    cy.student_number,
    cy.student_name,
    cy.academic_year_display,
    cy.region,
    cy.school_level,
    cy.school,
    cy.enroll_status,
    cy.cohort,
    cy.graduation_year,
    cy.gender,
    cy.ethnicity,
    cy.advisory,
    cy.year_in_school,
    cy.year_in_network,
    cy.rn_undergrad,
    cy.is_pathways,
    cy.is_retained_year,
    cy.is_retained_ever,
    cy.student_slideback,
    cy.lunch_status,
    cy.lep_status,
    cy.gifted_and_talented,
    cy.iep_status,
    cy.is_504,
    cy.salesforce_id,
    cy.ktc_cohort,
    cy.is_counseling_services,
    cy.is_student_athlete,
    cy.ada,
    cy.ada_above_or_at_80,
    cy.hos,
    cy.school_leader,
    cy.school_leader_tableau_username,
    cy.cumulative_y1_gpa_unweighted_as_of_today,
    cy.gpa_needed_for_cumulative_3_0,
    cy.is_cumulative_3_0_attainable,
    cy.potential_gpa_credits_current_year,
    cy.is_latest_graded_year,
    cy.is_on_cusp_3_0,
    cy.gpa_band_label,
    cy.gpa_band_as_of_today_label,

    gd.threshold as gpa_goal_threshold,
    gd.goal_proportion_org as gpa_goal_proportion_org,
    gd.goal_proportion_region as gpa_goal_proportion_region,
    gd.goal_proportion_school as gpa_goal_proportion_school,
from {{ ref("rpt_tableau__gpa_cumulative_year") }} as cy
left join
    {{ ref("int_gpa__student_goal_definitions") }} as gd
    on cy.student_number = gd.student_number
    and cy.academic_year = gd.academic_year
    and gd.metric = 'cumulative_gpa_unweighted'
```

- [ ] **Step 2: Generate the passthrough properties yml**

Writing 52 column blocks by hand invites a typo that fails the contract. Emit
them. Run from the main repo:

```bash
uv run --no-project python - <<'PY' > /workspaces/teamster/.claude/scratch/goal-progress-cols.yml
import subprocess, json
sql = """select column_name, lower(data_type) as data_type
from `teamster-332318.kipptaf_tableau.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'rpt_tableau__gpa_cumulative_year' order by ordinal_position"""
out = subprocess.run(
    ["/usr/local/share/google-cloud-sdk/bin/bq", "query", "--project_id=teamster-332318",
     "--use_legacy_sql=false", "--format=json", "--max_rows=200", sql],
    capture_output=True, text=True, check=True).stdout
for c in json.loads(out):
    print(f"      - name: {c['column_name']}")
    print(f"        data_type: {c['data_type']}")
    print("        description: "
          "Passthrough from `rpt_tableau__gpa_cumulative_year`, unchanged.")
PY
```

Expected: 52 three-line blocks in the scratch file. Confirm with
`grep -c 'name:' /workspaces/teamster/.claude/scratch/goal-progress-cols.yml` —
it must print 52.

If `bq` returns a reauthentication error, run the same query through the
BigQuery MCP and format the output by hand instead.

- [ ] **Step 3: Assemble the properties yml**

Create
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml`
with this header, then paste the generated blocks under `columns:`, then append
the four goal columns shown below.

```yaml
models:
  - name: rpt_tableau__gpa_goal_progress
    description: >-
      The Cumulative GPA Monitor's single data source. Passes through every
      column of rpt_tableau__gpa_cumulative_year unchanged and adds the GPA goal
      that applies to each student, at the network, region, and school rung.
      Exists as a separate model rather than columns on the extract because two
      published dashboards read the extract through a Tableau relationship that
      declares it unique, and it is a view, so a fan-out there would ship
      silently. Fold this model into the extract once that change can be made
      behind its own controls, then disable this one.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
          config:
            severity: error
    columns:
      # <-- paste the 52 generated blocks here
      - name: gpa_goal_threshold
        data_type: numeric
        description: >-
          Cumulative unweighted GPA the student must reach to count toward their
          grade's goal. NULL for grades with no goal.
      - name: gpa_goal_proportion_org
        data_type: numeric
        description: >-
          Target share of students network-wide expected to reach the threshold,
          as a proportion. NULL for grades with no goal.
      - name: gpa_goal_proportion_region
        data_type: numeric
        description: >-
          Target share for the student's region, as a proportion. NULL for
          grades with no goal.
      - name: gpa_goal_proportion_school
        data_type: numeric
        description: >-
          Target share for the student's school, as a proportion. NULL for
          grades with no goal.
```

- [ ] **Step 4: Build the model and run its test**

```bash
uv run dbt build --select rpt_tableau__gpa_goal_progress \
  --project-dir /workspaces/teamster/.worktrees/claude-student-goal-definitions/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: builds clean, uniqueness test PASSES.

A contract error naming a column means the generated yml and the select list
disagree — fix the yml, not the SQL.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/claude-student-goal-definitions && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml \
  </dev/null
```

Expected: no sqlfluff or yamllint findings.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions add \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions commit -m "feat(dbt): add rpt_tableau__gpa_goal_progress for the Cumulative GPA Monitor

Refs #5097"
```

---

## Task 3: Exposure, cross-model verification, and PR

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` — the
  `gpa_cumulative_monitor` exposure's `depends_on` list, near line 800

**Interfaces:**

- Consumes: both models from Tasks 1 and 2.
- Produces: nothing new. This task proves the wrapper is a faithful superset of
  the extract and opens the PR.

- [ ] **Step 1: Repoint the exposure**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, find the exposure whose
`depends_on` reads:

```yaml
depends_on:
  - ref("rpt_tableau__gpa_cumulative_year")
  - ref("rpt_tableau__gpa_goals")
```

Replace those two lines with:

```yaml
depends_on:
  - ref("rpt_tableau__gpa_goal_progress")
```

The dashboard now reads one model. Leave the `TODO(#4619)` URL comment below it
alone.

- [ ] **Step 2: Verify row parity for every year**

Not just 2026. A join that fans out on one historical year would be invisible in
a current-year check.

```sql
select
  coalesce(a.academic_year, b.academic_year) as academic_year,
  a.n as extract_rows,
  b.n as wrapper_rows,
from (
  select academic_year, count(*) as n
  from `teamster-332318.kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
  group by academic_year
) as a
full join (
  select academic_year, count(*) as n
  from `teamster-332318.<dev_tableau_schema>.rpt_tableau__gpa_goal_progress`
  group by academic_year
) as b on a.academic_year = b.academic_year
where a.n != b.n or a.n is null or b.n is null
```

Expected: zero rows. `<dev_tableau_schema>` is your `zz_..._kipptaf_tableau`
schema; find it with the Step 2 query from Task 1, changing the `like` pattern
to `'zz_%kipptaf_tableau'`.

- [ ] **Step 3: Verify column-name parity**

Compare column lists rather than eyeballing them. A silent rename here becomes
hand-rebuilt Tableau calculations at merge time.

```sql
select column_name, 'missing from wrapper' as problem
from `teamster-332318.kipptaf_tableau.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'rpt_tableau__gpa_cumulative_year'
  and column_name not in (
    select column_name
    from `teamster-332318.<dev_tableau_schema>.INFORMATION_SCHEMA.COLUMNS`
    where table_name = 'rpt_tableau__gpa_goal_progress'
  )
```

Expected: zero rows.

- [ ] **Step 4: Verify goal values and K-8 nulls**

```sql
select
  grade_level,
  count(*) as students,
  countif(gpa_goal_proportion_org is null) as null_goal,
  min(gpa_goal_proportion_org) as goal_min,
  max(gpa_goal_proportion_org) as goal_max,
from `teamster-332318.<dev_tableau_schema>.rpt_tableau__gpa_goal_progress`
where academic_year = 2026
group by grade_level
order by grade_level
```

Expected: grades 0 through 8 have `null_goal = students` and null min/max.
Grades 9 through 12 have `null_goal = 0` and min = max = 0.69, 0.64, 0.60, 0.56
respectively.

- [ ] **Step 5: Reconcile the computed rate against the published one**

This is the check that proves the dashboard will agree with the goals model.
Tableau will compute its actual rate from these student rows; that rate has to
land where `rpt_tableau__gpa_goals` already publishes it.

```sql
with
    wrapper as (
        select
            grade_level,
            countif(cumulative_y1_gpa_unweighted >= gpa_goal_threshold) as met,
            countif(cumulative_y1_gpa_unweighted is not null) as measured,
        from `teamster-332318.<dev_tableau_schema>.rpt_tableau__gpa_goal_progress`
        where academic_year = 2026 and gpa_goal_threshold is not null
        group by grade_level
    )

select
    w.grade_level,
    w.met,
    w.measured,
    round(safe_divide(w.met, w.measured), 3) as wrapper_rate,
    round(g.metric_rate, 3) as published_rate,
from wrapper as w
inner join
    `teamster-332318.kipptaf_tableau.rpt_tableau__gpa_goals` as g
    on cast(w.grade_level as string) = g.grade_band
where
    g.academic_year = 2026
    and g.metric = 'cumulative_gpa_unweighted'
    and g.org_level = 'org'
order by w.grade_level
```

Expected: four rows, grades 9 through 12, with `wrapper_rate` within 0.005 of
`published_rate` at every grade. The goals model rounds `metric_rate` to three
decimals and builds its population with slightly different enrollment rules, so
exact equality is not expected. A gap of a whole percentage point or more is a
real disagreement — investigate before opening the PR.

- [ ] **Step 6: Confirm nothing published changed**

```bash
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions \
  diff --stat origin/main...HEAD -- src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goals.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql
```

Expected: no output. Any output means the primary constraint was violated — stop
and revert those files.

- [ ] **Step 7: Lint the exposure and the plan doc**

```bash
cd /workspaces/teamster/.worktrees/claude-student-goal-definitions && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/exposures/tableau.yml \
  docs/superpowers/plans/2026-09-03-student-goal-definitions.md \
  </dev/null
```

Expected: no findings.

- [ ] **Step 8: Commit and push**

```bash
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions add \
  src/dbt/kipptaf/models/exposures/tableau.yml
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions commit -m "feat(dbt): point the Cumulative GPA Monitor exposure at the wrapper

Refs #5097"
git -C /workspaces/teamster/.worktrees/claude-student-goal-definitions push
```

- [ ] **Step 9: Open the PR**

Use `.github/pull_request_template.md` as the body. State in Reviewer Notes:
`rpt_tableau__gpa_cumulative_year` is untouched by design, with the Step 5 diff
as evidence; the wrapper is `rpt_`-on-`rpt_`, which ten models in this project
already do, three inside `extracts/tableau/`; and it is temporary, with the
merge path written in the spec.

Body must reference `Closes #5097`.

- [ ] **Step 10: Watch both CI surfaces**

dbt Cloud is a commit status; Trunk, CodeQL and `claude` are check runs. Check
both before calling it green. Note that a dbt-only PR selects `state:modified+`,
so this one does build the new models.

---

## Notes for whoever executes this

**The build order matters.** Task 2 refs Task 1's model. Running Task 2's build
before Task 1 is committed fails with an unresolved `ref`.

**IDE Pyright errors on worktree files are false positives.** It resolves
against the main checkout. Trust `uv run` executed against the worktree.

**Do not run two dbt commands against this worktree concurrently.** They share
`target/` and corrupt the partial-parse manifest.

**If the uniqueness test on Task 1 fails**, the cause is one of two things: an
overlapping grade band was added to the GPA goals Google Sheet, or
`int_extracts__student_enrollments` is not unique on
`(student_number, academic_year)` at `rn_year = 1`. Both are real findings worth
reporting. Neither is fixed by adding a dedupe to this model.
