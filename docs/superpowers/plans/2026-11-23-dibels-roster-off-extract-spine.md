# DIBELS roster off the extract spine (PR PM0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `int_students__dibels_participation_roster` stops reading
`int_extracts__student_enrollments_subjects`, with no change to its rows beyond
refresh timing, so a mart can read the roster and the 2 criteria models.

**Architecture:** The roster's `students` CTE reads enrollment from
`int_students__student_enrollments` and the 4 eligibility columns from
`int_amplify__benchmark_student_summary`. Nothing else in the model changes. The
proof is a dev build compared with prod, row for row, on the roster and on
`rpt_tableau__dibels_dashboard`, with every differing row traced to a cause.

**Tech Stack:** dbt on BigQuery (`uv run dbt`), the BigQuery MCP
(`execute_sql_readonly`) for the comparison queries, trunk for lint.

**Spec:**
`docs/superpowers/specs/2026-11-23-dibels-expected-test-facts-design.md` (_Step
0_). This plan covers PR PM0 only. PM1 to PM3 each get their own plan.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-dibels-expected-test-facts`
  (`<wt>` below), branch
  `anthonygwalters/feat/claude-dibels-expected-test-facts`. Every `git` call is
  `git -C <wt>`; every file path is under `<wt>`.
- Every dbt call is `uv run dbt ... --project-dir <wt>/src/dbt/kipptaf`, with
  `--state /workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute: the
  worktree has no prod manifest).
- Do not edit `rpt_tableau__dibels_dashboard.sql`, either criteria model, or
  `int_extracts__student_enrollments_subjects.sql`.
- The roster stays a view. Its filters stay: `enroll_status in (0, 2, 3)` and
  `grade_level <= 8`.
- No number on the live dashboard may change for a reason other than refresh
  timing. Any differing row with no named cause stops the work.
- Queries return aggregates only. Nothing in a commit, the PR or an issue names
  a student or shows a row. Counts under 10 read `<10` there; the terminal may
  show exact counts.
- The PR carries `Refs #6473` and `Refs #6461` and is not linked to either
  issue.
- Before any push: ask the user, in these words, "We need to update the skill
  and ref doc — do you authorize the update checks?" (the `dibels-dashboard`
  skill requires it for a branch that changes a `dibels` model).

## Review Focus

1. A student with no benchmark composite that year: the 4 eligibility columns
   must read `No Test`, so the student keeps Benchmark rows and matches no PM
   row. Pinned by Task 1 Step 7 (row counts by `model_type` match prod).
2. Miami: enrollment comes from Focus, with ids offset before academic
   year 2026. Miami must keep its rows in every year. Pinned by Task 1 Step 7
   (the comparison is by region and year).
3. A stint the domain model holds and the extract spine does not, or the
   reverse: it must show up as a traced timing difference, never as silent row
   loss. Pinned by Task 1 Step 8.
4. A student with 2 stints inside 1 round window: still 1 roster row. Pinned by
   the roster's existing uniqueness test in Task 1 Step 5.
5. A verdict that moves on the dashboard because `completed_test_round` moved:
   the criteria models read the roster, so a roster difference can change
   `met_pm_round_overall_criteria`. Pinned by Task 1 Step 9, which compares the
   whole dashboard model.

---

### Task 1: The roster reads the domain enrollment model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__dibels_participation_roster.sql:70-86`
  (the `students` CTE)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__dibels_participation_roster.yml:15-16`
  (model description)

**Interfaces:**

- Consumes: `int_students__student_enrollments` (`academic_year`, `region`,
  `student_number`, `enroll_status`, `grade_level`, `entrydate`, `exitdate`);
  `int_amplify__benchmark_student_summary` (`student_number`, `academic_year`,
  `measure_standard`, `boy_composite`, `moy_composite`, `boy_probe_eligible`,
  `moy_probe_eligible`).
- Produces: the roster with the same 15 columns, types and grain as today. No
  consumer changes.

- [ ] **Step 1: Install dbt packages in the worktree**

Run, in its own Bash call:

```bash
uv run dbt deps --project-dir <wt>/src/dbt/kipptaf 2>&1 | tail -n 5
```

Expected: `Installed from ...` lines and no error.

- [ ] **Step 2: Confirm the eligibility columns need no row pick**

Run through the BigQuery MCP:

```sql
with
    c as (
        select
            academic_year,
            student_number,
            count(
                distinct format(
                    '%T',
                    struct(
                        boy_composite,
                        moy_composite,
                        boy_probe_eligible,
                        moy_probe_eligible
                    )
                )
            ) as n_combos,
        from `teamster-332318.kipptaf_amplify.int_amplify__benchmark_student_summary`
        where measure_standard = 'Composite'
        group by academic_year, student_number
    )

select countif(n_combos > 1) as n_varying,
from c
```

Expected: `n_varying = 0` (it was 0 on 2026-11-23). If it is above 0, stop: the
`distinct` in Step 3 is then a masking dedup, and the model needs the extract's
latest-`client_date` pick with an A5 exemption instead. Ask the user.

- [ ] **Step 3: Replace the `students` CTE**

Replace lines 70-86 of the roster SQL with these 2 CTEs. Leave every other line
of the model as it is.

```sql
    -- grain projection, not dup-masking: the 4 columns are constant per student
    -- and year on Composite rows
    benchmark_composites as (
        select distinct
            student_number,
            academic_year,
            boy_composite,
            moy_composite,
            boy_probe_eligible,
            moy_probe_eligible,
        from {{ ref("int_amplify__benchmark_student_summary") }}
        where measure_standard = 'Composite'
    ),

    students as (
        select
            e.academic_year,
            e.region,
            e.student_number,
            e.enroll_status,
            e.grade_level,
            e.entrydate,
            e.exitdate,

            coalesce(b.boy_probe_eligible, 'No Test') as boy_probe_eligible,
            coalesce(b.moy_probe_eligible, 'No Test') as moy_probe_eligible,
            coalesce(b.boy_composite, 'No Test') as dibels_boy_composite,
            coalesce(b.moy_composite, 'No Test') as dibels_moy_composite,
        from {{ ref("int_students__student_enrollments") }} as e
        left join
            benchmark_composites as b
            on e.student_number = b.student_number
            and e.academic_year = b.academic_year
        where e.enroll_status in (0, 2, 3) and e.grade_level <= 8
    ),
```

- [ ] **Step 4: Update the model description**

In the properties yml, the description says enrolled students are "ELA
enrollments". Change that sentence to say the roster joins enrolled K-8 students
(`enroll_status` 0, 2 or 3) with each student's BOY and MOY composite level and
probe-eligible flag, `No Test` when the student has no composite that year. Do
not add history, counts or issue numbers to the description.

- [ ] **Step 5: Build the roster and its 3 consumers into dev**

```bash
uv run dbt build \
  --select int_students__dibels_participation_roster int_amplify__pm_met_criteria int_amplify__pm_met_criteria_aimline rpt_tableau__dibels_dashboard \
  --project-dir <wt>/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30
```

Expected: all 4 models build. The roster's
`dbt_utils.unique_combination_of_columns` test passes. The dashboard model's 3
singular tests may warn as they do in prod; they must not error. Use this exact
selection for every later rebuild: a narrower one re-points the unselected
models to prod and breaks the comparisons below.

- [ ] **Step 6: Find the dev datasets**

```sql
select schema_name,
from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA
where schema_name like 'zz_%_kipptaf_students'
```

Take the row for the current GitHub user. Its prefix before `_students` is
`<dev>` below, so the dev roster is
`<dev>_students.int_students__dibels_participation_roster` and the dev dashboard
model is `<dev>_tableau.rpt_tableau__dibels_dashboard`.

- [ ] **Step 7: Compare the dev roster with prod**

```sql
with
    p as (
        select
            *,
            format(
                '%T',
                (
                    academic_year,
                    region,
                    student_number,
                    grade_level,
                    model_type,
                    admin_season,
                    round_number
                )
            ) as k,
        from `teamster-332318.kipptaf_students.int_students__dibels_participation_roster`
    ),

    d as (
        select
            *,
            format(
                '%T',
                (
                    academic_year,
                    region,
                    student_number,
                    grade_level,
                    model_type,
                    admin_season,
                    round_number
                )
            ) as k,
        from `teamster-332318.<dev>_students.int_students__dibels_participation_roster`
    )

select
    coalesce(p.academic_year, d.academic_year) as academic_year,
    coalesce(p.region, d.region) as region,
    coalesce(p.model_type, d.model_type) as model_type,
    count(*) as n_keys,
    countif(d.k is null) as n_prod_only,
    countif(p.k is null) as n_dev_only,
    countif(
        format(
            '%T',
            (
                p.enroll_status,
                p.assessment_type,
                p.expected_row_count,
                p.actual_row_count,
                p.completed_test_round,
                p.participation_group,
                p.round_test_status
            )
        ) != format(
            '%T',
            (
                d.enroll_status,
                d.assessment_type,
                d.expected_row_count,
                d.actual_row_count,
                d.completed_test_round,
                d.participation_group,
                d.round_test_status
            )
        )
    ) as n_value_differs,
from p
full join d on p.k = d.k
group by academic_year, region, model_type
```

Expected: every region, Miami included, has rows in every year it has in prod.
`n_prod_only`, `n_dev_only` and `n_value_differs` are 0 or a few rows per group,
nearly all in the current year. A whole region, year or `model_type` missing, or
a difference in the hundreds, is a logic error: stop and fix Step 3.

- [ ] **Step 8: Trace every differing roster row to a cause**

Two causes are expected, both refresh timing. The extract spine is a table
rebuilt at 01:00; the dev roster reads enrollment and composites live. The
extract chain applies no filter and no inner join to enrollment rows: both
extract models select from the enrollment model and left join everything else.
So a stint that differs between the spine and the domain model changed after the
spine's last rebuild. If stint differences number in the hundreds, that
reasoning no longer holds: stop and read both extract models again.

```sql
with
    stint_side as (
        select
            'spine' as side,
            academic_year,
            student_number,
            format(
                '%T', (entrydate, exitdate, region, grade_level, enroll_status)
            ) as v,
        from `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments_subjects`
        where discipline = 'ELA' and grade_level <= 8

        union all

        select
            'domain' as side,
            academic_year,
            student_number,
            format(
                '%T', (entrydate, exitdate, region, grade_level, enroll_status)
            ) as v,
        from `teamster-332318.kipptaf_students.int_students__student_enrollments`
        where grade_level <= 8
    ),

    stint_diffs as (
        select academic_year, student_number, v,
        from stint_side
        group by academic_year, student_number, v
        having count(distinct side) = 1
    ),

    composites as (
        select distinct
            student_number,
            academic_year,
            boy_composite,
            moy_composite,
            boy_probe_eligible,
            moy_probe_eligible,
        from `teamster-332318.kipptaf_amplify.int_amplify__benchmark_student_summary`
        where measure_standard = 'Composite'
    ),

    composite_diffs as (
        select s.academic_year, s.student_number,
        from
            `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments_subjects`
            as s
        left join
            composites as c
            on s.student_number = c.student_number
            and s.academic_year = c.academic_year
        where
            s.discipline = 'ELA'
            and format(
                '%T',
                (
                    s.boy_probe_eligible,
                    s.moy_probe_eligible,
                    s.dibels_boy_composite,
                    s.dibels_moy_composite
                )
            ) != format(
                '%T',
                (
                    coalesce(c.boy_probe_eligible, 'No Test'),
                    coalesce(c.moy_probe_eligible, 'No Test'),
                    coalesce(c.boy_composite, 'No Test'),
                    coalesce(c.moy_composite, 'No Test')
                )
            )
    ),

    p as (
        select academic_year, student_number, to_json_string(t) as j,
        from
            `teamster-332318.kipptaf_students.int_students__dibels_participation_roster`
            as t
    ),

    d as (
        select academic_year, student_number, to_json_string(t) as j,
        from
            `teamster-332318.<dev>_students.int_students__dibels_participation_roster`
            as t
    ),

    roster_side as (
        select 'prod' as side, academic_year, student_number, j,
        from p

        union all

        select 'dev' as side, academic_year, student_number, j,
        from d
    ),

    differing_students as (
        select distinct academic_year, student_number,
        from
            (
                select academic_year, student_number, j,
                from roster_side
                group by academic_year, student_number, j
                having count(distinct side) = 1
            )
    )

select
    count(*) as n_students_differing,
    countif(sd.student_number is not null) as n_stint_timing,
    countif(
        sd.student_number is null and cd.student_number is not null
    ) as n_composite_timing,
    countif(sd.student_number is null and cd.student_number is null) as n_unexplained,
from differing_students as ds
left join
    (select distinct academic_year, student_number, from stint_diffs) as sd
    on ds.academic_year = sd.academic_year
    and ds.student_number = sd.student_number
left join
    (select distinct academic_year, student_number, from composite_diffs) as cd
    on ds.academic_year = cd.academic_year
    and ds.student_number = cd.student_number
```

Expected: `n_unexplained = 0`. Above 0, stop. Find the cause with counts only
(by region, grade, `model_type`, `admin_season`), fix Step 3 or report to the
user, and rerun Steps 5, 7 and 8. Never widen the "explained" set to make the
number 0.

Record `n_students_differing`, `n_stint_timing` and `n_composite_timing` with
the time of day the query ran. They go in the PR body, masked.

- [ ] **Step 9: Compare the dev dashboard model with prod**

```sql
with
    p as (
        select model_type, academic_year, student_number, to_json_string(t) as j,
        from `teamster-332318.kipptaf_tableau.rpt_tableau__dibels_dashboard` as t
    ),

    d as (
        select model_type, academic_year, student_number, to_json_string(t) as j,
        from `teamster-332318.<dev>_tableau.rpt_tableau__dibels_dashboard` as t
    ),

    sides as (
        select 'prod' as side, model_type, academic_year, student_number, j,
        from p

        union all

        select 'dev' as side, model_type, academic_year, student_number, j,
        from d
    ),

    one_sided as (
        select model_type, academic_year, student_number, j, min(side) as side,
        from sides
        group by model_type, academic_year, student_number, j
        having count(distinct side) = 1
    )

select
    model_type,
    academic_year,
    side,
    count(*) as n_rows,
    count(distinct student_number) as n_students,
from one_sided
group by model_type, academic_year, side
```

Expected: no rows, or a few rows whose students are all in Step 8's
`differing_students`. To check, rerun Step 8 with `one_sided` in place of
`differing_students`; `n_unexplained` must be 0. This is the measure of the risk
the spec names: how many dashboard rows can read differently because the roster
now reads enrollment live. Record `n_rows` and `n_students` by side for the PR
body and for the user's decision in Task 3.

- [ ] **Step 10: Lint and commit**

```bash
cd <wt> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__dibels_participation_roster.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__dibels_participation_roster.yml \
  </dev/null 2>&1 | tail -n 20
```

Expected: no lint issues (a formatting-only finding is the commit hook's job).

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(dbt): read DIBELS roster enrollment from the domain model"
```

End the commit message with `Refs #6473`, `Refs #6461` and the `Co-Authored-By`
line the session's attribution rule gives.

### Task 2: Reference doc and skill match the new roster

**Files:**

- Modify: `docs/models/dibels-dashboard-data-model.md` (lines near 111-117,
  331-333, 650-652, 830-836)
- Modify: `.claude/skills/dibels-dashboard/references/model-architecture.md`
  (contents list, and 1 new section)

**Interfaces:**

- Consumes: Task 1's recorded counts and the roster's new upstreams.
- Produces: nothing later tasks read.

- [ ] **Step 1: Correct the reference doc**

Make these 4 changes in `docs/models/dibels-dashboard-data-model.md`. Open it
with the Read tool first.

1. _How it fits together_ (near line 111) and _Shared upstreams_ (near line
   650): the extract spine drives the dashboard's 3 branches and sight words,
   and no longer the roster. The roster reads enrollment from
   `int_students__student_enrollments` and composites from
   `int_amplify__benchmark_student_summary`.
2. `rpt_tableau__dibels_dashboard` grain (near line 331) and _Duplicate
   dashboard rows_ (near line 830): remove the claim that more than 1 matching
   ELA section repeats a row. The ELA join returns at most 1 section per row,
   because `rn_core_subject_year` is numbered within source project, year,
   school, student and core subject. State what does repeat a row: on the
   Benchmark branch, a student who sat a measure at 2 grades (the score join has
   no grade); on the PM branches, a small number of keys repeat as identical
   rows, cause not yet traced.
3. Add a _Worth knowing_ bullet under `rpt_tableau__dibels_dashboard`: the
   dashboard's own rows read enrollment from the 01:00 spine, and the roster
   reads enrollment live. A stint that changes between 01:00 and the 05:00
   refresh can leave that student's rows without a round status until the next
   night.
4. Do not add counts or dates outside the _Known issues_ section's existing
   style.

- [ ] **Step 2: Add the trap to the skill**

In `.claude/skills/dibels-dashboard/references/model-architecture.md`, add 1
line to the _What's in here_ list and 1 section, titled "The roster reads
enrollment live, the dashboard spine reads it nightly". It says:

- which model reads which enrollment source;
- that a roster-versus-dashboard difference for a handful of students is refresh
  timing until shown otherwise, and the query shape that separates the two (Task
  1 Step 8: compare stints and composites between the spine and the live models
  before looking at logic);
- that the roster must not move back onto the extract spine, because the 2
  criteria models read it and a mart may not reach an `int_extracts__` model
  (A12).

State behavior only: no run dates, PR numbers or counts.

- [ ] **Step 3: Check nothing stale is left**

```bash
cd <wt> && rg -n 'more than one section|matching ELA section' docs/models/dibels-dashboard-data-model.md
```

Expected: no output.

- [ ] **Step 4: Lint and commit**

```bash
cd <wt> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/models/dibels-dashboard-data-model.md \
  .claude/skills/dibels-dashboard/references/model-architecture.md \
  </dev/null 2>&1 | tail -n 20
```

Expected: no lint issues.

```bash
git -C <wt> add -u
git -C <wt> commit -m "docs(dbt): DIBELS roster reads enrollment live"
```

Same message footer as Task 1.

### Task 3: Checks, owner decision, push and PR

**Files:**

- Modify: none expected. `src/dbt/kipptaf/standard-baseline.tsv` only if Step 1
  reports a stale row.

**Interfaces:**

- Consumes: Task 1's recorded counts (Steps 8 and 9).
- Produces: an open PR, PM0, that PM1 waits on.

- [ ] **Step 1: Run the layer check as CI does**

```bash
cd <wt> && git diff -U0 --no-renames origin/main...HEAD > <scratchpad>/pm0.diff \
  && uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir src/dbt/kipptaf 2>&1 | tail -n 3 \
  && uv run python scripts/check_dbt_standard.py --project-dir src/dbt/kipptaf --diff <scratchpad>/pm0.diff 2>&1 | tail -n 20
```

`<scratchpad>` is the session's scratchpad directory. Expected: no new
violation. The `distinct` in `benchmark_composites` is a grain projection, not a
row pick, so A5 does not fire. If the check reports a stale baseline row, remove
exactly that row from `standard-baseline.tsv` and commit it.

- [ ] **Step 2: Rebuild and re-run the comparisons on the final commit**

Repeat Task 1 Steps 5, 7, 8 and 9. Expected: the same results as before, within
timing. `n_unexplained = 0` on both.

- [ ] **Step 3: Give the owner the numbers and get the decision**

Show the user, in the terminal, with exact counts and the time of day each query
ran:

- roster rows that differ between dev and prod, by cause (Step 8);
- dashboard rows and students that differ (Step 9);
- the reading: these were measured in the daytime, hours after the 01:00 spine
  rebuild, so they are an upper bound on what the 05:00 dashboard refresh can
  see.

Ask whether that risk to the live dashboard is acceptable. Do not push until the
user says yes. On a no, stop and report; do not look for a workaround alone.

- [ ] **Step 4: Ask the skill's push question**

Ask the user, in these words: "We need to update the skill and ref doc — do you
authorize the update checks?" On yes, check both files from Task 2 against what
the branch changed and fix any gap. On no, push as asked and say in the PR body
that the reference doc and skill were not checked.

- [ ] **Step 5: Push and open the PR**

```bash
git -C <wt> push 2>&1 | tail -n 3
```

Open the PR with `mcp__github__create_pull_request`, base `main`, body from
`.github/pull_request_template.md`. Title:
`refactor(dbt): read DIBELS roster enrollment from the domain model`. The body
says, in plain language:

- what changed and why (the roster no longer reads the extract spine, so marts
  can read the roster and the criteria models);
- the proof: roster and dashboard model compared with prod, differing rows by
  cause, every count under 10 written `<10`, no student or row shown;
- the known risk and the owner's decision on it;
- `Refs #6473` and `Refs #6461`, each on its own line.

Read the returned PR back and check the title and body match.

- [ ] **Step 6: Offer the follow-ups**

Offer to watch the PR's CI and to respond to the `claude-review` findings. On a
yes to either, invoke `pr-ci-review` and arm a Monitor in that turn.
