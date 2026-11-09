# Branching Minds Intervention Episodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** One row per student, intervention, academic year, and continuous
assignment span from Branching Minds plans, with `is_current`, and `is_sipps` on
the enrollments hub rewired to read it.

**Architecture:** A source intermediate
`int_branchingminds__intervention_plans_rollup` splits each plan at the July 1
fiscal boundary, then collapses overlapping or back-to-back plans per student,
intervention, and year into episodes with a gaps-and-islands window pass.
`int_extracts__student_enrollments` drops its PowerSchool course join for
`is_sipps` and left-joins a distinct student-year projection of the rollup.

**Tech Stack:** dbt (kipptaf project), BigQuery, dbt unit tests, trunk
(sqlfluff, yamllint, markdownlint).

**Spec:**
`docs/superpowers/specs/2026-11-04-branchingminds-intervention-episodes-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-branchingminds-intervention-episodes`.
  Every path below is relative to it. Every `uv run dbt` call passes
  `--project-dir src/dbt/kipptaf` from the worktree root.
- `--state` is absolute: `/workspaces/teamster/src/dbt/kipptaf/target/prod`.
- Model name `int_branchingminds__intervention_plans_rollup` (A3 reshape
  suffix). Folder `src/dbt/kipptaf/models/branchingminds/intermediate/`.
- Grain: `student_number`, `intervention_name`, `academic_year`,
  `episode_start`. `academic_year` is the fiscal year's start year
  (`date_to_fiscal_year(..., start_month=7, year_source="start")`), matching the
  enrollment models.
- Two plans merge when the later one starts at most 1 day after the running max
  end of the earlier ones. A null end date is open-ended and keeps the episode
  open.
- `is_current` uses `current_date('{{ var("local_timezone") }}')`.
- `is_sipps` counts `intervention_name like 'SIPPS%'` (SIPPS and SIPPS
  Challenge), any episode in the year.
- No `qualify` (S1); no `group by 1, 2` (S2); the window pass is a CTE plus a
  `where`. Tests at `severity: error`. `config.meta.contains_pii: true` on the
  rollup.
- Unit-test fixtures use `format: sql` (the staging relation has no prod copy
  for dict-format introspection); `expect` dict scalars unquoted; every `expect`
  row lists the same columns.
- Commit messages are conventional commits ending with the
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` line. Never push to
  `main`.
- Before pushing, lint changed files:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from the worktree root. Formatting findings are the commit hook's.

## Review Focus

1. A plan whose end date is before its start date (BrM data error): the row must
   not crash the window pass; it yields an episode with
   `episode_end < episode_start` and `is_current = false`. Test in Task 1.
2. The same plan id exported twice with identical dates (staging dedupes on plan
   id, so this only arrives as 2 distinct ids with the same dates): 1 episode
   with `plans_in_episode = 2`. Test in Task 1.
3. A plan with a null end that started in a prior school year: 1 row per year
   from its start year through the current school year, the last one open. Test
   in Task 1.
4. A SIPPS Challenge plan with no plain SIPPS plan sets `is_sipps`. Test in Task
   2 (dev build check, since the hub has no unit test harness).
5. Two overlapping plans at 2 different BrM schools: 1 episode, `school_id` from
   the later-starting plan. Test in Task 1.

---

### Task 1: The rollup model, its properties, and unit tests

**Files:**

- Create:
  `src/dbt/kipptaf/models/branchingminds/intermediate/int_branchingminds__intervention_plans_rollup.sql`
- Create:
  `src/dbt/kipptaf/models/branchingminds/intermediate/properties/int_branchingminds__intervention_plans_rollup.yml`

**Interfaces:**

- Consumes: `ref("stg_branchingminds__intervention_plans")` columns
  `intervention_plan_id int64`, `student_number int64`,
  `intervention_name string`, `intervention_subject_area string`,
  `district string`, `school_id int64`, `intervention_start_date date`,
  `intervention_end_date date`.
- Produces: `int_branchingminds__intervention_plans_rollup` with columns
  `intervention_episode_key string`, `student_number int64`,
  `intervention_name string`, `intervention_subject_area string`,
  `district string`, `school_id int64`, `academic_year int64`,
  `episode_start date`, `episode_end date` (null when open),
  `plans_in_episode int64`, `intervention_plan_ids array<int64>`,
  `is_current bool`.

- [ ] **Step 1: Write the properties file with the unit tests**

Model block: description per the spec (grain, merge rule, planned-end limit in
plain words), `config.meta.contains_pii: true`, model-level
`dbt_utils.unique_combination_of_columns` on the 4 grain columns at `error`,
then columns with tests first: `intervention_episode_key` (`unique`, error),
`student_number`, `intervention_name`, `episode_start` (`not_null`, error), then
the rest with descriptions.

Unit tests, each `model: int_branchingminds__intervention_plans_rollup`, each
`given` an `input: ref("stg_branchingminds__intervention_plans")` with
`format: sql` rows that select the 8 consumed columns (cast dates with
`cast('YYYY-MM-DD' as date)`; `cast(null as date)` for a null end), each
`expect` row listing `student_number`, `intervention_name`, `academic_year`,
`episode_start`, `episode_end`, `plans_in_episode`, `school_id`:

- `test_rollup_merges_overlapping_plans`: plans 1 (2026-09-14 to 2026-10-27,
  school 2) and 2 (2026-10-01 to 2026-12-15, school 3), same student and
  intervention. Expect 1 row: start 2026-09-14, end 2026-12-15,
  `plans_in_episode` 2, `school_id` 3, `academic_year` 2026.
- `test_rollup_merges_adjacent_plans`: plan 1 ends 2026-10-27, plan 2 starts
  2026-10-28. Expect 1 row, end = plan 2's end.
- `test_rollup_splits_on_gap`: plan 1 ends 2026-10-27, plan 2 starts 2026-10-29.
  Expect 2 rows with `plans_in_episode` 1 each.
- `test_rollup_null_end_keeps_episode_open`: plan 1 (2026-09-14, null end), plan
  2 (2026-11-01 to 2026-11-30). Expect 1 row, `episode_end` null,
  `plans_in_episode` 2.
- `test_rollup_splits_at_fiscal_year`: 1 plan 2026-06-15 to 2026-09-30. Expect 2
  rows: (`academic_year` 2025, start 2026-06-15, end 2026-06-30) and
  (`academic_year` 2026, start 2026-07-01, end 2026-09-30), each
  `plans_in_episode` 1.
- `test_rollup_null_end_spans_to_current_year`: 1 plan starting 2025-09-01, null
  end. Expect rows for 2025 (end 2026-06-30) and 2026 (end null). Pin the
  current-year count by asserting on these 2 rows only; this fixture breaks on
  2027-07-01, and that is the intended reminder to revisit.
- `test_rollup_end_before_start_does_not_merge_or_crash`: 1 plan 2026-10-01 to
  2026-09-01. Expect 1 row with those dates unchanged and `plans_in_episode` 1.
- `test_rollup_two_ids_same_dates_count_twice`: plan ids 1 and 2 with identical
  dates. Expect 1 row, `plans_in_episode` 2.
- `test_rollup_separates_interventions`: same student, plan `SIPPS` and plan
  `UFLI Foundations (Ongoing)` overlapping. Expect 2 rows.

- [ ] **Step 2: Run the unit tests to verify they fail**

Run:
`uv run dbt test --project-dir src/dbt/kipptaf --select int_branchingminds__intervention_plans_rollup,test_type:unit --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`

Expected: a compilation error naming the missing model (no SQL file yet).

- [ ] **Step 3: Write the model SQL**

CTEs, in order:

1. `plans`: from `ref("stg_branchingminds__intervention_plans")`, the 8 consumed
   columns, plus `start_academic_year` and `end_academic_year` via
   `date_to_fiscal_year` on start and on `coalesce(end, current_date(tz))`;
   `where intervention_start_date is not null`.
2. `plan_years`: cross join
   `unnest(generate_array(start_academic_year, end_academic_year)) as academic_year`;
   `year_start` = `greatest(start, date(academic_year, 7, 1))`; `year_end` =
   `least(end, date(academic_year + 1, 6, 30))` when end is not null, else
   `date(academic_year + 1, 6, 30)` when `academic_year < end_academic_year`,
   else null; `year_end_or_max` =
   `coalesce(year_end, cast('9999-12-31' as date))` for the window.
3. `plans_ranked`:
   `max(year_end_or_max) over (partition by student_number, intervention_name, academic_year order by year_start, year_end_or_max rows between unbounded preceding and 1 preceding) as prior_max_end`.
4. `plans_flagged`:
   `if(prior_max_end is null or year_start > date_add(prior_max_end, interval 1 day), 1, 0) as is_new_episode`.
5. `plans_numbered`:
   `sum(is_new_episode) over (partition by student_number, intervention_name, academic_year order by year_start, year_end_or_max rows between unbounded preceding and current row) as episode_number`,
   plus
   `row_number() over (same partition and episode_number order by year_start desc, intervention_plan_id desc) as rn_latest`
   for the attribute pick.
6. `episodes`: group by `student_number`, `intervention_name`, `academic_year`,
   `episode_number`: `min(year_start) as episode_start`,
   `max(year_end_or_max) as episode_end_or_max`, `count(*) as plans_in_episode`,
   `array_agg(intervention_plan_id order by intervention_plan_id) as intervention_plan_ids`,
   and `max(if(rn_latest = 1, school_id, null))`, same for `district` and
   `intervention_subject_area`.

Final select: the grain columns, attributes,
`if(episode_end_or_max = '9999-12-31', null, episode_end_or_max) as episode_end`,
`is_current` as
`current_date(tz) >= episode_start and current_date(tz) <= episode_end_or_max`,
and
`{{ dbt_utils.generate_surrogate_key(["student_number", "intervention_name", "academic_year", "episode_start"]) }} as intervention_episode_key`.
Put a 1-line comment on the sentinel literal (S20) and on the 1-day adjacency
literal.

- [ ] **Step 4: Run the unit tests to verify they pass**

Same command as Step 2. Expected: `PASS=9`.

- [ ] **Step 5: Stage the BrM externals into your dev schema and build the
      chain**

Run (personal schema, no consent needed):
`uv run dbt run-operation stage_external_sources --project-dir src/dbt/kipptaf --args "select: branchingminds.src_branchingminds__intervention_plans" --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kipptaf, ext_full_refresh: true}' --target dev 2>&1 | tail -n 10`

Then:
`uv run dbt build --project-dir src/dbt/kipptaf --select stg_branchingminds__intervention_plans int_branchingminds__intervention_plans_rollup --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`

Expected: 2 models build, 3 tests on the rollup pass, 9 unit tests pass.

- [ ] **Step 6: Validate against the known snapshot**

Query via the BigQuery MCP against `zz_<user>_kipptaf_branchingminds`:

```sql
select
    countif(intervention_name = 'SIPPS') as sipps_episodes,
    countif(intervention_name = 'SIPPS' and is_current) as sipps_current,
    count(distinct if(intervention_name = 'SIPPS', student_number, null)) as sipps_students,
from `teamster-332318.zz_<user>_kipptaf_branchingminds.int_branchingminds__intervention_plans_rollup`
```

Expected on the 2026-10-22 snapshot: `sipps_episodes` 381, `sipps_students` 381,
`sipps_current` 185 (Camden plans end 2027-01-05; Newark and Paterson ended
2026-10-27). A different `sipps_current` means the snapshot in
`gs://teamster-test` moved or the date rule drifted; check the episode end dates
before changing code.

- [ ] **Step 7: Lint and commit**

Run trunk check on the 2 files (Global Constraints). Then:

```bash
git add src/dbt/kipptaf/models/branchingminds/intermediate/
git commit -m "feat(dbt): add Branching Minds intervention episodes rollup

Refs #6269

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Rewire `is_sipps` on the enrollments hub

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments.sql`
  (line 366 `is_sipps` expression; lines 586-593 the `sip` join; a new CTE at
  the top of the `with` block)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`
  (the `is_sipps` column entry near line 991)

**Interfaces:**

- Consumes: Task 1's rollup, columns `student_number`, `academic_year`,
  `intervention_name`.
- Produces: `int_extracts__student_enrollments.is_sipps bool`, unchanged name
  and type, same grain.

- [ ] **Step 1: Add the projection CTE**

In the `with` block, after `school_year_start`, add:

```sql
    sipps as (
        -- grain projection, not dup-masking: 1 row per student and year
        select distinct student_number, academic_year,
        from {{ ref("int_branchingminds__intervention_plans_rollup") }}
        where intervention_name like 'SIPPS%'
    ),
```

- [ ] **Step 2: Swap the join and the expression**

Replace the
`left join {{ ref("base_powerschool__course_enrollments") }} as sip ... and not sip.is_dropped_section`
block with:

```sql
left join
    sipps as sip
    on e.student_number = sip.student_number
    and e.academic_year = sip.academic_year
```

Change line 366 to
`if(sip.student_number is not null, true, false) as is_sipps,`.

- [ ] **Step 3: Update the column description**

Replace `description: Conditional on students_student_number.` on `is_sipps`
with a description saying the student held a SIPPS or SIPPS Challenge plan in
Branching Minds at any point in the academic year, per
`int_branchingminds__intervention_plans_rollup`.

- [ ] **Step 4: Compile and column-check the hub against dev**

Run:
`uv run dbt build --project-dir src/dbt/kipptaf --select int_extracts__student_enrollments --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --empty 2>&1 | tail -n 20`

Expected: the model builds (columns resolve; `--empty` leaves the dev relation
with 0 rows, which is fine here). `--favor-state` resolves the rollup to the dev
copy Task 1 built, since prod has none; if it errors on a missing rollup
relation, add `int_branchingminds__intervention_plans_rollup` to `--select` and
drop `--empty`.

- [ ] **Step 5: Value-check `is_sipps` with a prod-shaped query**

Via the BigQuery MCP, reproduce the join on prod enrollment rows and the dev
rollup:

```sql
select e._dbt_source_project, countif(s.student_number is not null) as sipps_students,
from `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as e
left join (
    select distinct student_number, academic_year,
    from `teamster-332318.zz_<user>_kipptaf_branchingminds.int_branchingminds__intervention_plans_rollup`
    where intervention_name like 'SIPPS%'
) as s
on e.student_number = s.student_number and e.academic_year = s.academic_year
where e.academic_year = 2026 and e.rn_year = 1
group by e._dbt_source_project
```

Expected on the 2026-10-22 snapshot: Camden 184, Newark 205, Paterson 33 (422
total, Challenge included). Review Focus 4: the Paterson count is 33 only
because SIPPS Challenge counts; a plain `= 'SIPPS'` would drop Paterson Prep
Middle to 0.

- [ ] **Step 6: Lint and commit**

Run trunk check on the 2 files. Then:

```bash
git add src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments.sql src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml
git commit -m "feat(dbt): read is_sipps from Branching Minds episodes

Replaces the PowerSchool SEM01099G1 course join, which carried rows only
for Camden in AY2025.

Refs #6269

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Push and open the PR

**Files:**

- Read: `.github/pull_request_template.md`

- [ ] **Step 1: Push the branch**

`git push origin HEAD` from the worktree.

- [ ] **Step 2: Open the PR with `mcp__github__create_pull_request`**

Base `main`, head
`anthonygwalters/feat/claude-branchingminds-intervention-episodes`, title
`feat(dbt): Branching Minds intervention episodes and is_sipps cutover`. Body
from the template. Summary: what the rollup is, the `is_sipps` cutover, the
AY2025 Camden history loss as a decision. Reviewer Notes: the planned-end
semantics of `is_current`; the 1-day adjacency rule; `--favor-state` dev
validation numbers (381 episodes, 185 current, 422 `is_sipps` students). For
Claude fold-out: spec and plan paths; prerequisite that the BrM sensor
`kipptaf__branchingminds__sftp_sensor` is started and the 9 BrM assets run in
prod before the models carry data; that dbt Cloud CI reads the
`zz_stg_kipptaf_branchingminds` externals from the 2026-10-22 branch deployment.
`Closes #6269`. End with the
`🤖 Generated with [Claude Code](https://claude.com/claude-code)` line.

- [ ] **Step 3: Confirm the returned title and body match intent**, then offer
      to watch CI and to respond to `claude-review` (invoke `pr-ci-review` on a
      yes).
