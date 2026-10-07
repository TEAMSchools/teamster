# Focus Import v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the seven Focus SFTP import feed changes settled in
[#4769](https://github.com/TEAMSchools/teamster/issues/4769) — drop withdrawals
from enrollment, crosswalk contact relationship types, populate the four contact
custody flags, add callout and SMS flags, reject junk phone numbers, split the
extract onto two schedules, and disable the never-shipped `LINKED_STUDENTS`
model.

**Architecture:** The feed is two layers. `kipptaf` `rpt_focus__*` builds
desired state from Finalsite; `kippmiami` `rpt_focus__*` anti-joins that against
live Focus and is what ships. Value and logic changes land in the kipptaf layer;
column-contract changes land in both layers plus the Dagster transport config.
Tasks 1 through 3 are independent of each other and of the contacts work. Tasks
4 through 7 all edit
`src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql` and must run in
order — they touch overlapping regions of one file.

**Tech Stack:** dbt (BigQuery), Dagster, `uv` for all Python execution.

## Global Constraints

- All decisions are recorded as A through Q in
  [#4769](https://github.com/TEAMSchools/teamster/issues/4769). Where this plan
  and the issue disagree, the issue wins — re-read it before starting a task.
- Every Python or dbt invocation runs through `uv run`. Never bare `python`,
  `python3`, or `dbt`.
- Worktree absolute path:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2`
- Every `git` call uses `git -C <worktree>`. Every dbt call passes
  `--project-dir <worktree>/src/dbt/<project>`. Never
  `uv --directory <worktree> run dbt` — that overrides cwd to the worktree root,
  which has no `dbt_project.yml`.
- `--state` must be the MAIN repo's absolute prod manifest path
  (`/workspaces/teamster/src/dbt/<project>/target/prod`). The worktree has no
  `target/prod`.
- Do NOT run `trunk fmt` or `trunk check` by hand mid-task. The pre-commit hook
  formats; the pre-push hook checks. The one exception is the explicit
  `trunk check --force` step at the end of each task that edits SQL or YAML —
  the pre-commit hook runs `fmt` only, and sqlfluff fires at pre-push and CI.
- `clean_phone`, `stg_finalsite__contacts`, and
  `int_finalsite__contact_custom_attributes` are OUT OF SCOPE. Emergency and
  guardian phones are already E.164-normalized (decisions E, F, Q). Changing
  those files would move values for `rpt_parentsquare__parents`,
  `rpt_deanslist__family_contacts`, and `int_students__contacts`.
- `rpt_deanslist__family_contacts` is OUT OF SCOPE. Its 11-digit phone handling
  is pre-existing and stays. Do not add a leading-`1` strip.
- IDE Pyright errors on worktree files (`reportMissingImports`, "not accessed")
  are expected false positives — it resolves imports against the main checkout.
  Trust `uv run` executed against the worktree, not the IDE.
- dbt Cloud CI builds `kipptaf` only. A change confined to `src/dbt/kippmiami`
  gets no CI validation and no branch deployment — a local `dbt build` is the
  only pre-merge gate for it.

---

## Pre-flight

Run once before Task 1. Two of these are verifications the issue asserts but
does not prove; a failure changes the plan rather than the code.

- [ ] **P1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`. Without this, every `dbt` command fails
with "N package(s) specified in packages.yml, but only 0 package(s) installed".

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami
```

- [ ] **P2: Confirm subtask 2 needs no code (issue decision A, B, H)**

The issue claims all four presence filters already implement the decided rules.
Prove it by reading the four anti-joins, not by trusting the claim.

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  rg -n -A4 'focus_students as|focus_address as|focus_contact as|focus_year as' \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql
```

Expected: demographics anti-joins `stg_focus__students`; addresses anti-joins
`stg_focus__students_join_address`; contacts anti-joins
`stg_focus__students_join_people`; enrollment keys `focus_year` on
`(student_id, syear)`. All four already match decisions A and B, and all four
are already on the kippmiami side per decision H. No code change.

If any one differs from that, STOP and re-open subtask 2 with the user.

- [ ] **P3: Verify the Focus CONTACTS column position for the new SMS columns**

Task 7 adds `contactN_sms` for 7 slots. `focus.yaml` maps dbt column names to
Focus headers via `header_replacements`, which implies Focus matches on header
NAME. But both the model SQL and its properties YAML assert
`CONTACTS_LAYOUT order` is load-bearing. This plan places each `contactN_sms`
immediately after that slot's `contactN_callout`.

Confirm that placement against the Focus CONTACTS template before Task 7. This
is the one open external dependency in the plan. If Focus wants the SMS columns
appended at the end instead, only the column ORDER in Task 7 changes — the
values and tests are unaffected.

---

## File Structure

| File                                                                                   | Responsibility                                                                     | Tasks      |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------- |
| `src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`            | Reconcile desired enrollment against live Focus; entry rows only after this change | 1          |
| `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml` | Contract minus `end_date` and `drop_code`                                          | 1          |
| `src/teamster/code_locations/kippmiami/extracts/schedules.py`                          | Two `ScheduleDefinition`s on the Focus extract job                                 | 2          |
| `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml`      | Disable model, its 3 data tests, and its unit test                                 | 3          |
| `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml`    | Disable the wrapper model                                                          | 3          |
| `src/dbt/kippmiami/models/extracts/sources.yml`                                        | Disable the `rpt_focus__linked_students` source entry                              | 3          |
| `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`                        | Guardian and emergency contact rows in Focus CONTACTS shape; all value logic       | 4, 5, 6, 7 |
| `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`             | Contract, descriptions, `accepted_values`, unit tests                              | 4, 5, 6, 7 |
| `src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql`                      | Passthrough column list; widens with the contract                                  | 7          |
| `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml`           | Wrapper contract columns and its SQL-format unit test fixture                      | 7          |
| `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`                     | `header_replacements` for the 8 new columns                                        | 7          |

---

## Task 1: Exclude withdrawals from student enrollment

Implements issue subtask 1 and decision I. No withdrawal reaches the import —
not the exit rows, not the two columns, not the students.

**Files:**

- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__student_enrollment")` and
  `ref("stg_focus__student_enrollment")`. Neither changes.
- Produces: the same model minus two contract columns (`end_date`, `drop_code`).
  No later task in this plan reads it.

- [ ] **Step 1: Add a data test asserting no withdrawal rows survive**

Add to
`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`
in the model-level `data_tests:` block. If the model has no such block, create
it directly above `columns:`.

```yaml
data_tests:
  - dbt_utils.expression_is_true:
      arguments:
        expression: enrollment_code is not null
      config:
        severity: error
        where: true
```

Every surviving row is an entry row, and the entry branch always carries an
`enrollment_code` — the exit branch was the only producer of
`cast(null as string) as enrollment_code`. So this test fails while the `exits`
branch still exists and passes once it is gone.

- [ ] **Step 2: Run the test and confirm it fails**

```bash
uv run dbt build --select rpt_focus__student_enrollment \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: the `expression_is_true` test FAILS with roughly 9 failing rows (9 of
161 current rows are exits).

If it passes at this point, the exit branch is already producing no rows — stop
and check whether `main` moved
(`git -C <worktree> log $(git -C <worktree> merge-base origin/main HEAD)..origin/main`).

- [ ] **Step 3: Rewrite the model**

Replace the entire contents of
`src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`:

```sql
with
    -- live Focus enrollments, keys pre-formatted to the export string shapes so
    -- the joins below compare plain columns (no one-sided casts in ON)
    focus_enrollment as (
        select
            syear,

            cast(student_id as string) as student_id,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    -- entry-existence key. Match on (student_id, syear) only: ops manually edit
    -- the floored start_date in Focus after import, so a start_date match would
    -- re-open an already-loaded student-year as "new".
    focus_year as (select distinct student_id, syear, from focus_enrollment),

    -- desired state from kipptaf, scoped to the current academic year.
    -- Withdrawals are excluded outright (#4769 decision I): the feed creates
    -- enrollments only, so a row carrying an end_date has nothing to add and
    -- would otherwise import as an ACTIVE enrollment with no end date once the
    -- end_date column itself is dropped from the output.
    desired as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        where
            d.syear = {{ var("current_academic_year") }} and d.end_date is null
    ),

    -- entry branch: student-year absent from Focus -> send the entry row
    entries as (
        select d.*,
        from desired as d
        left join
            focus_year as fy on d.student_id = fy.student_id and d.syear = fy.syear
        where fy.student_id is null
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    enrollment_code,
    calendar_id,
    prior_dist,
    prior_state,
    prior_country,
    ed_choice,
    stdt_dis_affect,
    offender_transfer_stdt,
    came_from,
    moved_to,
    sec_sch,
    grde_prom_st,
    good_cause_exempt,
    graduation_requirement_program,
    next_school,
    next_grade,
    district_ood,
    sch_ood,
    include_in_class_rank,
    fl_days_present,
    fl_days_absent,
from entries
```

This drops the `exits` CTE and its `UNION ALL`, the `focus_open` CTE, the
`stg_focus__student_enrollment_codes` decode join, the `end_date` and
`drop_code` output columns, and the now-unused `end_date` / `drop_code`
selections in `focus_enrollment`.

- [ ] **Step 4: Remove the two dropped columns from the contract**

In
`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`,
delete the `- name: end_date` and `- name: drop_code` column blocks entirely,
including their `data_type` and `description` lines and any `data_tests` on
them.

Update the model `description:` so it no longer promises a withdrawal branch.
Replace any sentence describing the exit branch or drop-code decode with:

```yaml
Entry rows only. A student-year absent from Focus is sent as a new enrollment;
withdrawals are excluded entirely, so a student carrying an end_date in the
desired state is not sent at all (#4769 decision I).
```

- [ ] **Step 5: Run the build and confirm the test passes**

```bash
uv run dbt build --select rpt_focus__student_enrollment \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: PASS, all tests green.

- [ ] **Step 6: Confirm the row count dropped and no row carries an end date**

```bash
uv run dbt show --inline "select count(*) as n_rows from {{ ref('rpt_focus__student_enrollment') }}" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: fewer than the 161 rows the issue records, and by more than 9 — the 9
exit rows go, plus any entry row that carried an `end_date`. Record the actual
number in the commit message; it is the evidence that step 3's
`end_date is null` filter did something beyond deleting the exits branch.

- [ ] **Step 7: Lint the changed files**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml </dev/null
```

If `.trunk/tools/trunk` does not exist (cold Codespace, lazily populated), use
`~/.cache/trunk/launcher/trunk` instead; the first run creates the symlink.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): exclude withdrawals from the student enrollment import

Refs #4769"
```

---

## Task 2: Split the extract onto two schedules

Implements issue subtask 6. The existing 25-line comment justifies 12:45
entirely from the noon Finalsite push and the 2pm commitment; it needs
rewriting, not just retiming.

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/extracts/schedules.py`

**Interfaces:**

- Consumes: `focus_extract_asset_job` from
  `teamster.code_locations.kippmiami.extracts.jobs`, and `LOCAL_TIMEZONE`. Both
  unchanged.
- Produces: a `schedules` list of two `ScheduleDefinition` objects instead of
  one. Dagster discovers it by name; no other module imports the individual
  schedule objects.

- [ ] **Step 1: Confirm nothing imports the current schedule by name**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  rg -n 'focus_extract_assets_schedule' src/ tests/
```

Expected: matches only inside `schedules.py` itself. If another module imports
that symbol, keep the name for the 12:45-replacement schedule so the import
resolves.

- [ ] **Step 2: Replace the file**

Write `src/teamster/code_locations/kippmiami/extracts/schedules.py`:

```python
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

# Both schedules deliver the same four Focus import CSVs to the Focus SFTP
# `incoming/` folder. Enrollment ops run the Focus imports BY HAND, so a
# delivery is only useful if someone is on shift to consume it.
#
# NEITHER schedule is gated on its upstreams -- both are plain crons, so the gap
# between an upstream refresh and a delivery is a time budget, not a dependency.
#
# 13:15 is the staffed run. Leadership commits to stakeholders that a student
# entered in Finalsite by 12:00pm ET is usable in Focus by 2:00pm ET. Upstreams
# all run concurrently at 12:00 (the manual Finalsite SFTP push, the Finalsite
# contacts pull, the Focus dlt pull, and the dbt rebuild the
# automation-condition sensor fires off each). The binding term is the manual
# push: worst case ~11 min from push to rebuilt (5 min couchdrop sensor poll +
# 2m13s ingest + 3m34s dbt). Against the 75 min from 13:15 to the 2pm
# commitment, that leaves the 12:00-12:15 push window ample margin and keeps the
# 12:30 freshness check on #4736 actionable -- a push prompted by it at 12:31 is
# rebuilt by ~12:42 and still makes this delivery.
#
# Delivering EARLIER is not a safe fallback: it misses anything entered between
# the push and the noon cutoff, and anything before ~12:11 puts the late bound
# before noon, contradicting the "entered by 12:00" promise outright.
focus_extract_assets_schedule = ScheduleDefinition(
    name="focus_extract_assets_schedule",
    job=focus_extract_asset_job,
    cron_schedule="15 13 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

# 03:45 is the unstaffed run. It exists so the overnight state of Finalsite is
# already staged in Focus when ops start their shift, rather than waiting on the
# 13:15 delivery. Nobody is watching it, so it is deliberately NOT load-bearing
# for the 2pm commitment -- if it fails, 13:15 still satisfies the promise.
focus_extract_assets_overnight_schedule = ScheduleDefinition(
    name="focus_extract_assets_overnight_schedule",
    job=focus_extract_asset_job,
    cron_schedule="45 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
    focus_extract_assets_overnight_schedule,
]
```

The explicit `name=` on both is required: two `ScheduleDefinition`s on the same
job would otherwise derive the same default name and collide at definition load.

- [ ] **Step 3: Verify both schedules load and carry the right crons**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  VIRTUAL_ENV= uv run python -c "
from teamster.code_locations.kippmiami.extracts.schedules import schedules
assert len(schedules) == 2, len(schedules)
got = sorted((s.name, s.cron_schedule) for s in schedules)
assert got == sorted([
    ('focus_extract_assets_schedule', '15 13 * * *'),
    ('focus_extract_assets_overnight_schedule', '45 3 * * *'),
]), got
print('ok', got)
"
```

Expected: prints `ok` and the two pairs. A `DagsterInvalidDefinitionError` here
means the name collision described in step 2.

- [ ] **Step 4: Confirm the whole code location still loads**

A schedule that imports fine can still break definition loading.

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  VIRTUAL_ENV= uv run dagster definitions validate \
  -m teamster.code_locations.kippmiami.definitions 2>&1 | tail -20
```

Expected: validation succeeds. If the module path is wrong, find it with
`rg -n 'kippmiami' src/teamster/code_locations/kippmiami/definitions.py` and the
`deploy-prod-kippmiami.yaml` workflow.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): split the SFTP extract onto staffed and overnight schedules

Refs #4769"
```

---

## Task 3: Disable rpt_focus__linked_students

Implements issue subtask 8 and decision P. Disable, do not delete.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml`
- Modify: `src/dbt/kippmiami/models/extracts/sources.yml`

**Interfaces:**

- Consumes: nothing new.
- Produces: two fewer models and four fewer test nodes in the manifest. No task
  in this plan depends on it.

- [ ] **Step 1: Record the current node count as a baseline**

```bash
uv run dbt ls --resource-type model --resource-type test --resource-type unit_test \
  --select rpt_focus__linked_students \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target prod --output name 2>/dev/null | grep '^[a-z]' | sort
```

Expected: the model plus its three data tests
(`dbt_utils_unique_combination_of_columns_*`, two `not_null_*`) and the
`test_linked_students_normalizes_pair` unit test. Save this list — step 5
compares against it.

- [ ] **Step 2: Disable the kipptaf model, its data tests, and its unit test**

In
`src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml`:

Add `enabled: false` to the existing model `config:` block, which currently
holds only the contract:

```yaml
config:
  enabled: false
  contract:
    enforced: true
```

Disabling a model does NOT disable its tests — they stay in `nodes` and keep
scanning the stale prod relation. So add a `config:` to each test as well.

The model-level test becomes:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - primary_student_id
          - secondary_student_id
      config:
        enabled: false
```

Each column's `not_null` already carries a `config:` with `severity: error`; add
`enabled: false` beside it, for both `primary_student_id` and
`secondary_student_id`:

```yaml
data_tests:
  - not_null:
      config:
        severity: error
        enabled: false
```

And the unit test, as a sibling of its `model:` key:

```yaml
unit_tests:
  - name: test_linked_students_normalizes_pair
    config:
      enabled: false
```

Keep the unit test's `description`, `given`, and `expect` blocks in place — this
is a disable, not a delete.

- [ ] **Step 3: Disable the kippmiami wrapper model**

`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml`
is columns-only today, with no `config:` block. Add one directly under `name:`:

```yaml
models:
  - name: rpt_focus__linked_students
    config:
      enabled: false
    columns:
      - name: primary_student_id
        data_type: string
      - name: secondary_student_id
        data_type: string
```

- [ ] **Step 4: Disable the source entry**

The kippmiami wrapper reads
`source("kipptaf_extracts", "rpt_focus__linked_students")`, and that source
entry in `src/dbt/kippmiami/models/extracts/sources.yml` carries a
`meta.dagster.asset_key` pointing at the kipptaf asset that no longer exists
once step 2 lands. Add `enabled: false` to the entry's existing `config:` block,
alongside its `meta:`:

```yaml
- name: rpt_focus__linked_students
  config:
    enabled: false
    meta:
      dagster:
        asset_key:
          - kipptaf
          - extracts
          - rpt_focus__linked_students
```

Preserve the existing `meta.dagster` block exactly — read the file and match its
current indentation and key order rather than retyping from this snippet.

- [ ] **Step 5: Confirm every node is gone from both projects**

```bash
for p in kipptaf kippmiami; do
  echo "=== $p ==="
  uv run dbt ls --resource-type model --resource-type test --resource-type unit_test \
    --select rpt_focus__linked_students \
    --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/$p \
    --target prod --output name --no-partial-parse 2>/dev/null | grep '^[a-z]' | sort
done
```

Expected: empty output for both. `--no-partial-parse` is required — partial
parse caches node enable/disable state and under-reports.

- [ ] **Step 6: Confirm both projects still parse**

```bash
for p in kipptaf kippmiami; do
  uv run dbt parse --target prod --no-partial-parse \
    --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/$p || echo "PARSE FAILED: $p"
done
```

Expected: both succeed. A failure here usually means the source entry in step 4
was disabled while the wrapper model was not, or the YAML indentation drifted.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml \
  src/dbt/kippmiami/models/extracts/sources.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "chore(focus): disable the unshipped linked students export

Refs #4769"
```

---

## Task 4: Crosswalk contact relationship type

Implements issue subtask 3 and decision C. First of four tasks on
`rpt_focus__contacts.sql`.

Two branches feed `student_relation` today and both need crosswalking:

- `guardians` sets it from `rel.rel_type`, filtered to six lowercase values:
  `parent`, `guardian`, `grandparent`, `stepparent`, `relative`, `aunt/uncle`.
- `emergency_long` sets it from
  `coalesce(a.emrg_N_relationship_ss, a.emrg_N_relationship_txt)` — a Finalsite
  select-list value or free text, which is where the already-capitalized values
  (`Grandmother`, `Great Aunt`, `Sister`) come from.

Gender is available only on the guardian branch: `g` in that CTE IS
`stg_finalsite__contacts`, joined on `rel.rel_id = g.finalsite_enrollment_id`,
so it is the guardian's own record. Emergency rows are custom fields on the
student's record and have no contact gender.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts.gender`, which carries mixed forms. The
  repo already handles this in `rpt_focus__demographics` as
  `c.gender in ('M', 'Male')` / `c.gender in ('F', 'Female')` — match that
  pattern exactly rather than assuming one spelling.
- Produces: `student_relation` on the model output now always one of the 13
  Focus values. Tasks 5, 6, and 7 do not read it.

- [ ] **Step 1: Write a failing unit test for the crosswalk**

Append to the `unit_tests:` block in
`src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`. Use
`format: sql` for every input — dict format introspects the live relation schema
and these models carry array and struct columns.

```yaml
- name: test_contacts_relation_crosswalk
  description:
    A lowercase Finalsite rel_type is rolled up to its nearest Focus value,
    split by the guardian's own gender where gender is present and falling back
    to the non-gendered value otherwise. A value with no Focus equivalent
    becomes None.
  model: rpt_focus__contacts
  given:
    - input: ref('stg_finalsite__contact_relationships')
      format: sql
      rows: |
        select
            'enr-stu-1' as finalsite_enrollment_id,
            'rel-1' as relationship_id,
            'enr-mom' as rel_id,
            'parent' as rel_type,
            true as is_primary
        union all
        select 'enr-stu-1', 'rel-2', 'enr-dad', 'parent', false
        union all
        select 'enr-stu-1', 'rel-3', 'enr-nogender', 'parent', false
        union all
        select 'enr-stu-1', 'rel-4', 'enr-cousin', 'relative', false
    - input: ref('stg_finalsite__contacts')
      format: sql
      rows: |
        select
            'enr-mom' as finalsite_enrollment_id,
            'F' as gender,
            'enrolled' as status,
            'Mom' as first_name,
            'Lopez' as last_name,
            cast(null as string) as middle_name,
            cast(null as string) as email,
            cast(null as string) as phone_1_type,
            cast(null as string) as phone_1_number,
            cast(null as string) as phone_2_type,
            cast(null as string) as phone_2_number
        union all
        select 'enr-dad', 'Male', 'enrolled', 'Dad', 'Lopez',
            null, null, null, null, null, null
        union all
        select 'enr-nogender', null, 'enrolled', 'Nogender', 'Lopez',
            null, null, null, null, null, null
        union all
        select 'enr-cousin', 'F', 'enrolled', 'Cousin', 'Lopez',
            null, null, null, null, null, null
        union all
        select 'enr-stu-1', null, 'enrolled', 'Student', 'Lopez',
            null, null, null, null, null, null
    - input: ref('int_finalsite__enrollment_lifecycle')
      format: sql
      rows: |
        select 'enr-stu-1' as finalsite_enrollment_id
    - input: ref('int_finalsite__contact_id_attributes')
      format: sql
      rows: |
        select
            'enr-stu-1' as finalsite_enrollment_id,
            '8400001' as focus_student_id_prefixed
    - input: ref('int_finalsite__contact_address_of_record')
      format: sql
      rows: |
        select
            cast(null as string) as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip
    - input: ref('int_finalsite__contact_custom_attributes')
      format: sql
      rows: |
        select cast(null as string) as finalsite_enrollment_id
  expect:
    format: sql
    rows: |
      select 'Mother' as student_relation
      union all
      select 'Father'
      union all
      select 'Parent'
      union all
      select 'None'
```

The `expect` block asserts one column, so add `config: {} ` only if the model's
other unit tests do — otherwise dbt compares just the listed column. If dbt
rejects a single-column `expect` against this model, widen every `expect` row to
the full output column list, `null` for everything except `student_relation`,
per the repo rule that every `expect` row must list the same columns.

The four inputs above cover only the columns the crosswalk path reads. If the
build reports a missing column on any mocked ref, add it to that fixture as
`cast(null as <type>) as <name>` — do not switch to dict format.

- [ ] **Step 2: Run the unit test and confirm it fails**

```bash
uv run dbt test --select test_contacts_relation_crosswalk \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL. The actual rows come back as `parent`, `parent`, `parent`,
`relative` — the raw values, uncrosswalked.

- [ ] **Step 3: Carry the guardian's gender through to the union**

In `rpt_focus__contacts.sql`, the `guardians` CTE selects `g.first_name`,
`g.middle_name`, `g.last_name`, `g.email` from `stg_finalsite__contacts as g`.
Add the guardian's gender to that same group of plain column refs, directly
after `g.email`:

```sql
            g.gender as contact_gender,
```

In each of the four `emergency_long` UNION branches, add a null counterpart to
the block of `cast(null as string)` columns that already holds
`relationship_id`, `address`, and the rest:

```sql
            cast(null as string) as contact_gender,
```

In the `all_contacts` CTE, add `contact_gender,` to BOTH the `from guardians`
and the `from emergency_long` select lists, immediately after `email,` in each.
Both branches must list it or the UNION ALL fails on mismatched column counts.

- [ ] **Step 4: Add the crosswalk CTE**

Insert a new CTE between `all_contacts` and `ranked`. The `case` expression
cannot reference a select-list alias in the same list (BigQuery rejects lateral
column aliases), so it derives `student_relation` here and `ranked` reads the
plain column.

```sql
    crosswalked as (
        -- Focus does not enforce STUDENT_RELATION, and 12 rows of
        -- un-crosswalked lowercase feed values are already sitting in prod
        -- Focus. The accepted_values test on this output is the only gate.
        -- Domain verified against live Focus: 13 values, no 'Emergency'.
        -- Gender is present only on the guardian branch (a guardian's own
        -- stg_finalsite__contacts row); emergency rows are custom fields on the
        -- student's record and fall through to the non-gendered value.
        select
            * except (student_relation, contact_gender),

            case
                when
                    student_relation in (
                        'Mother',
                        'Father',
                        'Parent',
                        'Guardian',
                        'Grandmother',
                        'Grandfather',
                        'Aunt',
                        'Uncle',
                        'Stepfather',
                        'Stepmother',
                        'Stepparent',
                        'Surrogate'
                    )
                then student_relation
                when student_relation = 'parent' and contact_gender in ('F', 'Female')
                then 'Mother'
                when student_relation = 'parent' and contact_gender in ('M', 'Male')
                then 'Father'
                when student_relation = 'parent'
                then 'Parent'
                when
                    student_relation = 'grandparent'
                    and contact_gender in ('F', 'Female')
                then 'Grandmother'
                when
                    student_relation = 'grandparent'
                    and contact_gender in ('M', 'Male')
                then 'Grandfather'
                when
                    student_relation = 'aunt/uncle'
                    and contact_gender in ('F', 'Female')
                then 'Aunt'
                when
                    student_relation = 'aunt/uncle'
                    and contact_gender in ('M', 'Male')
                then 'Uncle'
                when
                    student_relation = 'stepparent'
                    and contact_gender in ('F', 'Female')
                then 'Stepmother'
                when
                    student_relation = 'stepparent'
                    and contact_gender in ('M', 'Male')
                then 'Stepfather'
                when student_relation = 'stepparent'
                then 'Stepparent'
                when student_relation = 'guardian'
                then 'Guardian'
                when student_relation = 'Great Aunt'
                then 'Aunt'
                when student_relation = 'Great Uncle'
                then 'Uncle'
                else 'None'
            end as student_relation,
        from all_contacts
    ),
```

Then change `ranked`'s `from all_contacts` to `from crosswalked`.

Note the deliberate omissions: `grandparent` and `aunt/uncle` have no
non-gendered Focus equivalent, so a gender-null row on either falls through to
`else 'None'` rather than getting its own branch. The issue records both as 100%
gender-populated today, so neither fallback is expected to fire — but it is
defined rather than left to chance.

- [ ] **Step 5: Run the unit test and confirm it passes**

```bash
uv run dbt test --select test_contacts_relation_crosswalk \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS.

- [ ] **Step 6: Add the accepted_values test on the crosswalked column**

In `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`,
find the `- name: student_relation` column block and give it the test. Move the
block to the top of the `columns:` list, per the repo rule that columns carrying
per-column tests sort first — the contract matches by name, not position, so the
reorder is safe.

```yaml
- name: student_relation
  data_type: string
  description:
    Relationship of the contact to the student, crosswalked to the Focus
    STUDENT_RELATION vocabulary. Guardian rows roll their lowercase Finalsite
    rel_type up to the nearest Focus value, split by the guardian's own gender
    where gender is populated. Emergency rows carry the Finalsite emrg_N
    relationship label through the same crosswalk and have no gender to split
    on. Anything without a Focus equivalent becomes None.
  data_tests:
    - not_null:
        config:
          severity: error
    - accepted_values:
        arguments:
          values:
            - Mother
            - Father
            - Parent
            - Guardian
            - Grandmother
            - Grandfather
            - Aunt
            - Uncle
            - Stepfather
            - Stepmother
            - Stepparent
            - Surrogate
            - None
        config:
          severity: error
```

Keep the `not_null`. `accepted_values` compiles to `where value not in (...)`,
which NULL never satisfies, so the pairing is the only thing making the enum
test reject NULL — even though `else 'None'` makes the column non-null by
construction.

- [ ] **Step 7: Build the model and run every test on it**

```bash
uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS, including `accepted_values` and every pre-existing unit test on
this model. A sibling unit test failing here means step 3's new `contact_gender`
column broke its fixture — the repo rule is that a column ADD breaks that
model's own unit tests, so add `contact_gender` to any failing fixture's inputs.

- [ ] **Step 8: Confirm the distribution matches the issue's projection**

```bash
uv run dbt show --limit 20 --inline "
select student_relation, count(*) as n
from {{ ref('rpt_focus__contacts') }}
group by student_relation
order by n desc
" --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: only values from the 13-item domain, and roughly the split the issue
projects — `Mother` near 1,089, `Father` near 759, `Parent` near 413. Exact
counts will drift from the issue's numbers since the data has moved since they
were taken; what matters is that no lowercase value survives and the gendered
buckets are non-trivial on both sides.

- [ ] **Step 9: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): crosswalk contact relationship type to the Focus vocabulary

Refs #4769"
```

---

## Task 5: Populate custody, resides-with, emergency, and pickup

Implements issue subtask 4 and decision G. Second task on
`rpt_focus__contacts.sql`.

All four are null for guardians today; only the emergency branch sets them.
`emergency` and `pick_up` become blanket `Y`. `resides_with_stud` and `custody`
share one rule: the first contact per student is `Y`, a later contact is `Y`
only when it shares a household with that first contact, and `N` when household
membership is unknown on either side.

Use household membership, not the doc's address string comparison —
`123 Main St` versus `123 Main Street`, or a unit number in `address` on one row
and `address2` on the other, both read as a false `N`.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts.household_ids`, an `ARRAY<STRING>` of every
  household id for a contact, already on the staging model. Prefer it over
  `stg_finalsite__contact_relationships.household_1_id`, which is
  `households[safe_offset(0)].id` and therefore only the first household.
- Produces: `resides_with_stud`, `custody`, `emergency`, `pickup` non-null on
  every row. Task 7 does not read them.

- [ ] **Step 1: Write a failing unit test**

Append to the `unit_tests:` block in the kipptaf properties YAML. Reuse the
fixture shape from Task 4 step 1, adding `household_ids` to the
`stg_finalsite__contacts` input.

```yaml
- name: test_contacts_custody_flags
  description:
    emergency and pickup are Y on every row. The first contact per student is Y
    for resides_with_stud and custody; a later contact sharing a household with
    the first is Y, and one with no household overlap is N.
  model: rpt_focus__contacts
  given:
    - input: ref('stg_finalsite__contact_relationships')
      format: sql
      rows: |
        select
            'enr-stu-2' as finalsite_enrollment_id,
            'rel-a' as relationship_id,
            'enr-adult-a' as rel_id,
            'guardian' as rel_type,
            true as is_primary
        union all
        select 'enr-stu-2', 'rel-b', 'enr-adult-b', 'guardian', false
        union all
        select 'enr-stu-2', 'rel-c', 'enr-adult-c', 'guardian', false
    - input: ref('stg_finalsite__contacts')
      format: sql
      rows: |
        select
            'enr-adult-a' as finalsite_enrollment_id,
            ['hh-1'] as household_ids,
            cast(null as string) as gender,
            'enrolled' as status,
            'Aaa' as first_name,
            'Aaa' as last_name,
            cast(null as string) as middle_name,
            cast(null as string) as email,
            cast(null as string) as phone_1_type,
            cast(null as string) as phone_1_number,
            cast(null as string) as phone_2_type,
            cast(null as string) as phone_2_number
        union all
        select 'enr-adult-b', ['hh-1'], null, 'enrolled', 'Bbb', 'Bbb',
            null, null, null, null, null, null
        union all
        select 'enr-adult-c', ['hh-9'], null, 'enrolled', 'Ccc', 'Ccc',
            null, null, null, null, null, null
        union all
        select 'enr-stu-2', cast(null as array<string>), null, 'enrolled',
            'Student', 'Two', null, null, null, null, null, null
    - input: ref('int_finalsite__enrollment_lifecycle')
      format: sql
      rows: |
        select 'enr-stu-2' as finalsite_enrollment_id
    - input: ref('int_finalsite__contact_id_attributes')
      format: sql
      rows: |
        select
            'enr-stu-2' as finalsite_enrollment_id,
            '8400002' as focus_student_id_prefixed
    - input: ref('int_finalsite__contact_address_of_record')
      format: sql
      rows: |
        select
            cast(null as string) as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip
    - input: ref('int_finalsite__contact_custom_attributes')
      format: sql
      rows: |
        select cast(null as string) as finalsite_enrollment_id
  expect:
    format: sql
    rows: |
      select
          'Aaa' as last_name, 'Y' as resides_with_stud, 'Y' as custody,
          'Y' as emergency, 'Y' as pickup
      union all
      select 'Bbb', 'Y', 'Y', 'Y', 'Y'
      union all
      select 'Ccc', 'N', 'N', 'Y', 'Y'
```

`Aaa` sorts first on the existing `ranked` ordering (`contact_group`,
`group_rank`, `last_name`), so it is the first contact. `Bbb` shares `hh-1` with
it; `Ccc` does not.

- [ ] **Step 2: Run the test and confirm it fails**

```bash
uv run dbt test --select test_contacts_custody_flags \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL. All four columns come back NULL for guardian rows.

- [ ] **Step 3: Carry household ids through to the union**

In the `guardians` CTE, add the guardian's household array next to the other
plain `g.` refs, after the `g.gender as contact_gender` line Task 4 added:

```sql
            g.household_ids,
```

In each of the four `emergency_long` branches, add the null counterpart. An
emergency contact is a custom field on the student's record, not a Finalsite
contact, so it has no household of its own.

```sql
            cast(null as array<string>) as household_ids,
```

Add `household_ids,` to both select lists in `all_contacts`, and to the
`* except (...)` in the `crosswalked` CTE only if you need to drop it — leave it
in, since step 4 reads it.

- [ ] **Step 4: Derive the first contact's household and compare**

Insert a new CTE between `crosswalked` and `ranked`. It needs the same ordering
`ranked` uses, so the "first contact" here and `sort_order = 1` there agree.

```sql
    household_compared as (
        -- resides_with_stud / custody: the first contact per student is always
        -- Y; a later contact is Y only when it shares a household with that
        -- first contact. Household membership rather than an address string
        -- comparison -- '123 Main St' vs '123 Main Street', or a unit number
        -- that sits in address on one row and address2 on the other, would
        -- both read as a false N. N is an explicit default when household
        -- membership is unknown on either side, not a guess.
        select
            *,

            first_value(household_ids) over (
                partition by student_id
                order by
                    contact_group asc,
                    group_rank asc,
                    last_name asc,
                    first_name asc,
                    relationship_id asc
            ) as first_contact_household_ids,
        from crosswalked
    ),

    household_flagged as (
        select
            * except (household_ids, first_contact_household_ids),

            (
                select count(*)
                from unnest(household_ids) as h
                where h in unnest(first_contact_household_ids)
            ) as shared_household_count,
        from household_compared
    ),
```

Then point `ranked` at `household_flagged` instead of `crosswalked`.

The scalar aggregate over `unnest` is the one blessed subquery form in this repo
— it is row-local. Do not rewrite it as an `order by ... limit 1` pick.

- [ ] **Step 5: Set the four flags in the final select**

In the final `select`, the four columns are currently plain refs carried up from
the branches. Replace them with derived values. They sit in the logicals group
of the select order, after the plain column refs.

```sql
    if(sort_order = 1 or shared_household_count > 0, 'Y', 'N') as resides_with_stud,
    if(sort_order = 1 or shared_household_count > 0, 'Y', 'N') as custody,
    'Y' as emergency,
    'Y' as pickup,
```

`shared_household_count` is `0` rather than NULL when either array is empty or
NULL, because `count(*)` over an empty `unnest` returns `0` — so the `> 0` test
yields the intended `N` with no extra null guard.

The branch-level `resides_with_stud`, `custody`, `emergency`, and `pickup`
columns in `guardians` and `emergency_long` are now dead. Leave them in place so
`all_contacts`' UNION ALL column lists stay aligned, but add
`shared_household_count` and drop nothing.

If sqlfluff ST06 complains, the two `if(...)` calls are logicals and belong
after the plain refs and before any `case` — move the whole group rather than
reordering within it.

- [ ] **Step 6: Run the test and confirm it passes**

```bash
uv run dbt test --select test_contacts_custody_flags \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS.

- [ ] **Step 7: Update the four column descriptions**

In the kipptaf properties YAML, replace the descriptions on `resides_with_stud`,
`custody`, `emergency`, and `pickup`. They currently say the values are not
sourced from Finalsite.

```yaml
- name: resides_with_stud
  data_type: string
  description:
    Y when this contact is the student's first contact by SORT_ORDER, or shares
    a Finalsite household with that first contact. N otherwise, including when
    household membership is unknown on either side.
- name: custody
  data_type: string
  description:
    Same rule as RESIDES_WITH_STUD — Y for the student's first contact by
    SORT_ORDER or any later contact sharing a household with it, N otherwise.
- name: emergency
  data_type: string
  description:
    Always Y. Every contact in this feed is treated as an emergency contact
    (#4769 decision G).
- name: pickup
  data_type: string
  description:
    Always Y. Every contact in this feed is authorized for pickup (#4769
    decision G). Note this overwrites the per-phone emrg_N_phone_N_opt_in
    consent signal that exists on the emergency branch only.
```

- [ ] **Step 8: Build, verify the flags are non-null, lint, commit**

```bash
uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

uv run dbt show --limit 10 --inline "
select
    countif(resides_with_stud is null) as null_resides,
    countif(custody is null) as null_custody,
    countif(emergency != 'Y') as bad_emergency,
    countif(pickup != 'Y') as bad_pickup,
    countif(resides_with_stud = 'Y') as y_resides,
    countif(resides_with_stud = 'N') as n_resides
from {{ ref('rpt_focus__contacts') }}
" --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: the four null/bad counts are all `0`, and `y_resides` and `n_resides`
are both non-zero. An `n_resides` of `0` means every contact is landing `Y` —
check that `household_ids` actually survived to `household_flagged` rather than
being dropped by an `except`.

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): populate contact custody, resides-with, emergency, and pickup

Refs #4769"
```

---

## Task 6: Reject junk phone numbers and map blank phone types

Implements issue subtask 7 and decisions J, Q. Third task on
`rpt_focus__contacts.sql`.

Both phone sources are ALREADY E.164-normalized — `stg_finalsite__contacts`
wraps `phone_1` through `phone_3` in `clean_phone`, and
`int_finalsite__contact_custom_attributes` wraps all 12 `emrg_N_phone_N_number`
columns. Do not touch either, and do not add a guard to the `clean_phone` macro:
it documents "never returns NULL for a non-null input", so a guard inside its
`CASE` would fall through to `coalesce(..., degarbled)` and emit raw
`5555555555` — un-normalizing junk rather than rejecting it — and would move
values for three other extracts.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: `contact1_value` through `contact3_value` as E.164 strings
  (`+1XXXXXXXXXX`), and `contact1_type` through `contact3_type` as free-typed
  Finalsite strings.
- Produces: the same three value columns with repeated-digit junk nulled, and
  the three type columns mapped to the Focus display vocabulary. Task 7 reads
  `contactN_type` to derive `contactN_sms`.

- [ ] **Step 1: Write a failing unit test**

```yaml
- name: test_contacts_phone_junk_and_type
  description:
    A repeated-digit number that survives clean_phone's NANP check is nulled. A
    real number passes through. A blank or unrecognized phone type defaults to
    Cell Phone rather than dropping the contact.
  model: rpt_focus__contacts
  given:
    - input: ref('stg_finalsite__contact_relationships')
      format: sql
      rows: |
        select
            'enr-stu-3' as finalsite_enrollment_id,
            'rel-p' as relationship_id,
            'enr-junk' as rel_id,
            'guardian' as rel_type,
            true as is_primary
        union all
        select 'enr-stu-3', 'rel-q', 'enr-good', 'guardian', false
    - input: ref('stg_finalsite__contacts')
      format: sql
      rows: |
        select
            'enr-junk' as finalsite_enrollment_id,
            cast(null as array<string>) as household_ids,
            cast(null as string) as gender,
            'enrolled' as status,
            'Junk' as first_name,
            'Aaa' as last_name,
            cast(null as string) as middle_name,
            cast(null as string) as email,
            '' as phone_1_type,
            '+15555555555' as phone_1_number,
            cast(null as string) as phone_2_type,
            cast(null as string) as phone_2_number
        union all
        select 'enr-good', cast(null as array<string>), null, 'enrolled',
            'Good', 'Bbb', null, null, 'Work', '+13055550134', null, null
        union all
        select 'enr-stu-3', cast(null as array<string>), null, 'enrolled',
            'Student', 'Three', null, null, null, null, null, null
    - input: ref('int_finalsite__enrollment_lifecycle')
      format: sql
      rows: |
        select 'enr-stu-3' as finalsite_enrollment_id
    - input: ref('int_finalsite__contact_id_attributes')
      format: sql
      rows: |
        select
            'enr-stu-3' as finalsite_enrollment_id,
            '8400003' as focus_student_id_prefixed
    - input: ref('int_finalsite__contact_address_of_record')
      format: sql
      rows: |
        select
            cast(null as string) as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip
    - input: ref('int_finalsite__contact_custom_attributes')
      format: sql
      rows: |
        select cast(null as string) as finalsite_enrollment_id
  expect:
    format: sql
    rows: |
      select
          'Aaa' as last_name,
          cast(null as string) as contact1_value,
          'Cell Phone' as contact1_type
      union all
      select 'Bbb', '+13055550134', 'Work Phone'
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
uv run dbt test --select test_contacts_phone_junk_and_type \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL. `contact1_value` comes back `+15555555555` and `contact1_type`
comes back as the empty string and `Work`.

- [ ] **Step 3: Add the phone-cleaning CTE**

Insert between `household_flagged` and `ranked`, and repoint `ranked` at it.

Only `0000000000` through `9999999999` where the repeated digit is 2 through 9
can reach this check — `clean_phone`'s NANP regex `^[2-9]\d{2}[2-9]\d{6}$`
already rejects a leading `0` or `1`, so `0000000000` and `1111111111` never
arrive. The eight listed are the ones that genuinely survive.

```sql
    phones_cleaned as (
        -- clean_phone already normalized both phone sources to E.164, and its
        -- contract is to never return NULL -- unparseable input passes through
        -- de-garbled. So repeated-digit junk (which is NANP-valid) survives it
        -- as a well-formed +1XXXXXXXXXX. Reject it here rather than in the
        -- macro: the macro is shared by rpt_parentsquare__parents,
        -- rpt_deanslist__family_contacts, and int_students__contacts, and a
        -- guard inside its CASE would emit the raw digits instead of nulling
        -- them. Only repeated digits 2-9 can reach this -- clean_phone's NANP
        -- check already rejects a leading 0 or 1. See #4769 decision Q.
        select
            * except (
                contact1_value,
                contact2_value,
                contact3_value,
                contact1_type,
                contact2_type,
                contact3_type
            ),

            if(
                contact1_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact1_value
            ) as contact1_value,
            if(
                contact2_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact2_value
            ) as contact2_value,
            if(
                contact3_value in (
                    '+12222222222',
                    '+13333333333',
                    '+14444444444',
                    '+15555555555',
                    '+16666666666',
                    '+17777777777',
                    '+18888888888',
                    '+19999999999'
                ),
                cast(null as string),
                contact3_value
            ) as contact3_value,

            -- A blank or unrecognized type defaults to Cell Phone rather than
            -- dropping the contact (#4769 decision J). Consequence to know:
            -- under the SMS rule in the final select this makes an untyped
            -- number an SMS target, so a mistyped work line can receive texts.
            {{ focus_phone_type("contact1_type") }} as contact1_type,
            {{ focus_phone_type("contact2_type") }} as contact2_type,
            {{ focus_phone_type("contact3_type") }} as contact3_type,
        from household_flagged
    ),
```

- [ ] **Step 4: Add the phone-type display macro**

Create `src/dbt/kipptaf/macros/focus_phone_type.sql`. A macro rather than three
copies of the same 8-line `CASE`, and it keeps the plan's "one display map"
commitment.

```sql
{% macro focus_phone_type(column) %}
    {#-
      Map a free-typed Finalsite phone type to the Focus display vocabulary.
      A blank or unrecognized type defaults to Cell Phone rather than dropping
      the contact (#4769 decision J).
    -#}
    case
        when lower(trim({{ column }})) in ('cell', 'mobile') then 'Cell Phone'
        when lower(trim({{ column }})) = 'home' then 'Home Phone'
        when lower(trim({{ column }})) in ('work', 'business', 'office')
        then 'Work Phone'
        when lower(trim({{ column }})) = 'workplace' then 'Workplace'
        when lower(trim({{ column }})) in ('alternate', 'day', 'daytime')
        then 'Alternate Phone'
        else 'Cell Phone'
    end
{% endmacro %}
```

The `cell|mobile`, `home`, `work|business|office`, and `day` groupings mirror
the existing regex vocabulary in `stg_focus__people_join_contacts`, so the two
agree on what a title means. `daytime` maps to `Alternate Phone` because Focus
has no daytime slot.

Add its documentation to `src/dbt/kipptaf/macros/properties.yml` if that file
exists and documents other macros; check with
`rg -n 'name:' src/dbt/kipptaf/macros/properties.yml | head`.

- [ ] **Step 5: Run the test and confirm it passes**

```bash
uv run dbt test --select test_contacts_phone_junk_and_type \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS. A `Function not found: focus_phone_type` error means the macro
call is missing its `{{ }}` — that form is valid SQL, so it passes parse and
sqlfluff and fails only at build.

- [ ] **Step 6: Build and confirm the type domain closed**

```bash
uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

uv run dbt show --limit 20 --inline "
select contact1_type, count(*) as n
from {{ ref('rpt_focus__contacts') }}
group by contact1_type
order by n desc
" --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: only `Cell Phone`, `Home Phone`, `Work Phone`, `Workplace`,
`Alternate Phone`. No empty string, no lowercase value, no NULL.

- [ ] **Step 7: Add accepted_values on the three type columns and update
      descriptions**

For each of `contact1_type`, `contact2_type`, `contact3_type`, replace the
column block and move it to the top of `columns:` with the others carrying
tests:

```yaml
- name: contact1_type
  data_type: string
  description:
    Phone type for the first contact slot, mapped to the Focus display
    vocabulary. A blank or unrecognized Finalsite type defaults to Cell Phone
    rather than dropping the contact.
  data_tests:
    - not_null:
        config:
          severity: error
    - accepted_values:
        arguments:
          values:
            - Cell Phone
            - Home Phone
            - Work Phone
            - Workplace
            - Alternate Phone
        config:
          severity: error
```

Repeat verbatim for `contact2_type` and `contact3_type`, changing only the name
and the ordinal word in the description. Do not write "same as `contact1_type`"
— each block stands alone.

Also update the three value-column descriptions to record the junk rejection:

```yaml
- name: contact1_value
  data_type: string
  description:
    Phone number for the first contact slot in E.164 form. Repeated-digit
    placeholder numbers that survive clean_phone's NANP validation are nulled
    here.
```

- [ ] **Step 8: Build, lint, commit**

```bash
uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml \
  src/dbt/kipptaf/macros/focus_phone_type.sql </dev/null

git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add src/dbt/kipptaf/macros/focus_phone_type.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): reject junk phone numbers and map blank phone types

Refs #4769"
```

---

## Task 7: Add callout and SMS flags across all seven slots

Implements issue subtask 5 and decisions D, G, L, M. Last task on
`rpt_focus__contacts.sql`, and the riskiest — it widens the CSV column contract
from 50 to 58 columns across five files.

**Do not start until Pre-flight P3 is answered.** This task places each
`contactN_sms` immediately after that slot's `contactN_callout`; if Focus wants
them appended at the end, only the ordering changes.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`
- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml`
- Modify: `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`

**Interfaces:**

- Consumes: `contactN_type` as produced by Task 6 — one of the five Focus
  display values, never NULL.
- Produces: 8 new columns. `contact7_callout` (decision L: the existing select
  ends at `contact7_unlisted`, which is treated as a truncation bug), and
  `contact1_sms` through `contact7_sms`.

- [ ] **Step 1: Confirm the current column count is 50**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  echo "kipptaf yml: $(rg -c '^      - name: ' src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml)" && \
  echo "kippmiami yml: $(rg -c '^      - name: ' src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml)" && \
  echo "focus.yaml header_replacements: $(sed -n '/name: rpt_focus__contacts/,/destination_config/p' src/teamster/code_locations/kippmiami/extracts/config/focus.yaml | rg -c ': [A-Z]')"
```

Expected: all three agree at 50. If they already disagree, reconcile that BEFORE
adding columns — a mismatch between the model and `header_replacements` means
the CSV already ships a header Focus does not expect.

- [ ] **Step 2: Write a failing unit test for the callout and SMS rules**

```yaml
- name: test_contacts_callout_and_sms
  description:
    callout is Y on every slot. sms is Y except on Work Phone and Workplace,
    which get N. Both apply per slot rather than to slot 1 only.
  model: rpt_focus__contacts
  given:
    - input: ref('stg_finalsite__contact_relationships')
      format: sql
      rows: |
        select
            'enr-stu-4' as finalsite_enrollment_id,
            'rel-w' as relationship_id,
            'enr-worker' as rel_id,
            'guardian' as rel_type,
            true as is_primary
    - input: ref('stg_finalsite__contacts')
      format: sql
      rows: |
        select
            'enr-worker' as finalsite_enrollment_id,
            cast(null as array<string>) as household_ids,
            cast(null as string) as gender,
            'enrolled' as status,
            'Work' as first_name,
            'Worker' as last_name,
            cast(null as string) as middle_name,
            cast(null as string) as email,
            'Work' as phone_1_type,
            '+13055550111' as phone_1_number,
            'Cell' as phone_2_type,
            '+13055550222' as phone_2_number
        union all
        select 'enr-stu-4', cast(null as array<string>), null, 'enrolled',
            'Student', 'Four', null, null, null, null, null, null
    - input: ref('int_finalsite__enrollment_lifecycle')
      format: sql
      rows: |
        select 'enr-stu-4' as finalsite_enrollment_id
    - input: ref('int_finalsite__contact_id_attributes')
      format: sql
      rows: |
        select
            'enr-stu-4' as finalsite_enrollment_id,
            '8400004' as focus_student_id_prefixed
    - input: ref('int_finalsite__contact_address_of_record')
      format: sql
      rows: |
        select
            cast(null as string) as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip
    - input: ref('int_finalsite__contact_custom_attributes')
      format: sql
      rows: |
        select cast(null as string) as finalsite_enrollment_id
  expect:
    format: sql
    rows: |
      select
          'Y' as contact1_callout,
          'N' as contact1_sms,
          'Y' as contact2_callout,
          'Y' as contact2_sms,
          'Y' as contact7_callout,
          'Y' as contact7_sms
```

Slot 1 is the Work Phone, so its `sms` is `N` while its `callout` is `Y`. Slot 2
is the Cell, so both are `Y`. Slot 7 is empty but still carries both flags,
proving the rule is per-slot and not gated on a populated number.

- [ ] **Step 3: Run the test and confirm it fails**

```bash
uv run dbt test --select test_contacts_callout_and_sms \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL with an unrecognized-name error on `contact1_sms` — the column
does not exist yet.

- [ ] **Step 4: Replace the flag columns in the kipptaf final select**

In the final `select` of `src/dbt/kipptaf/.../rpt_focus__contacts.sql`, the flag
columns are currently `cast(null as string)` for `blocked`, `unlisted`, and
`callout`, with `contact7_callout` missing entirely. Replace each slot's flag
group. Slots 1 through 3 keep their real `contactN_type` and `contactN_value`
above them; slots 4 through 7 keep their null type and value.

For slots 1 through 3, the group reads:

```sql
    cast(null as string) as contact1_blocked,
    cast(null as string) as contact1_unlisted,
    'Y' as contact1_callout,
    if(contact1_type in ('Work Phone', 'Workplace'), 'N', 'Y') as contact1_sms,
```

Repeat for slots 2 and 3, substituting the ordinal in both the column names and
the `contactN_type` reference.

For slots 4 through 7 there is no type column to test, and Task 6 guarantees
`contactN_type` is NULL for them, so `sms` is unconditionally `Y`:

```sql
    cast(null as string) as contact4_type,
    cast(null as string) as contact4_value,
    cast(null as string) as contact4_blocked,
    cast(null as string) as contact4_unlisted,
    'Y' as contact4_callout,
    'Y' as contact4_sms,
```

Repeat for slots 5, 6, and 7. Slot 7 gains `contact7_callout`, which does not
exist today.

`blocked` and `unlisted` stay NULL on every slot — no rule has been defined for
them.

- [ ] **Step 5: Add the 8 columns to the kipptaf contract**

In the kipptaf properties YAML, add `contact7_callout` after
`contact7_unlisted`, and a `contactN_sms` block after each `contactN_callout`.
Eight new blocks. Write each one out; do not cross-reference.

```yaml
- name: contact1_sms
  data_type: string
  description:
    SMS opt-in flag for the first contact slot. Y except on a Work Phone or
    Workplace type, which get N.
```

Repeat for slots 2 through 7, changing the ordinal word. For slots 4 through 7,
the description reads:

```yaml
- name: contact4_sms
  data_type: string
  description:
    SMS opt-in flag for the fourth contact slot. Always Y — the slot is never
    populated, so no Work Phone exclusion can apply.
```

And `contact7_callout`:

```yaml
      - name: contact7_callout
        data_type: string
        description:
          Callout flag for the seventh contact slot. Always Y. This column was
          absent from the select before #4769; its omission was a truncation
          bug, not a contract difference.
```

Update the model `description:`, which currently says "Produces 50 columns in
`CONTACTS_LAYOUT` order" and "`CONTACT4` through `CONTACT7` are always null".
Change the count to 58 and add:

```yaml
Every slot carries CALLOUT Y and an SMS flag; SMS is N only on a Work Phone or
Workplace type. CONTACT4 through CONTACT7 have null type and value but still
carry both flags.
```

- [ ] **Step 6: Widen the kippmiami passthrough and its contract**

`src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql` enumerates
every column. Add `contact7_callout` after `contact7_unlisted`, and
`contactN_sms` after each `contactN_callout`, matching the kipptaf order
exactly. Its final list ends:

```sql
    contact7_type,
    contact7_value,
    contact7_blocked,
    contact7_unlisted,
    contact7_callout,
    contact7_sms,
from diffed
```

Add the same 8 names to
`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml` as
`data_type: string` blocks with no descriptions — that file is a thin
cross-project wrapper, which the repo keeps contract-columns-only, with
descriptions living on the kipptaf source view.

That YAML also carries a unit test whose `format: sql` fixture enumerates every
column. Add all 8 to that fixture as `cast(null as string) as contactN_sms` and
`cast(null as string) as contact7_callout`. A column ADD breaks the model's own
unit test, since the fixture and `expect` blocks enumerate the full output.

- [ ] **Step 7: Add the 8 header replacements**

In `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`, the
`rpt_focus__contacts` block's `header_replacements` currently ends at
`contact7_unlisted: CONTACT7_UNLISTED`. Add each `contactN_sms` after that
slot's `contactN_callout`, plus `contact7_callout`, so the mapping order matches
the model:

```yaml
contact1_callout: CONTACT1_CALLOUT
contact1_sms: CONTACT1_SMS
```

through

```yaml
contact7_unlisted: CONTACT7_UNLISTED
contact7_callout: CONTACT7_CALLOUT
contact7_sms: CONTACT7_SMS
```

Confirm the uppercase header spellings against the Focus CONTACTS template from
Pre-flight P3. `CONTACT1_SMS` is this plan's assumption, not a verified value.

- [ ] **Step 8: Run the unit test and confirm it passes**

```bash
uv run dbt test --select test_contacts_callout_and_sms \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS.

- [ ] **Step 9: Run every unit test in the directory, not just this model's**

Sibling models mock the same refs, so a column add breaks their fixtures too.

```bash
uv run dbt test --select "test_type:unit,extracts.focus" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all PASS.

- [ ] **Step 10: Build both projects and confirm 58 columns everywhere**

```bash
uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

uv run dbt build --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod

cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  echo "kipptaf yml: $(rg -c '^      - name: ' src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml)" && \
  echo "kippmiami yml: $(rg -c '^      - name: ' src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml)" && \
  echo "focus.yaml: $(sed -n '/name: rpt_focus__contacts/,/destination_config/p' src/teamster/code_locations/kippmiami/extracts/config/focus.yaml | rg -c ': [A-Z]')"
```

Expected: both builds PASS with contracts enforced, and all three counts
read 58. A contract failure naming a column absent from the YAML means step 5 or
6 missed one; the error lists the offending name.

- [ ] **Step 11: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml \
  src/teamster/code_locations/kippmiami/extracts/config/focus.yaml </dev/null

git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 commit -m "feat(focus): add callout and SMS flags across all seven contact slots

Refs #4769"
```

---

## Final verification

- [ ] **F1: Full build of both affected model trees**

```bash
uv run dbt build --select +rpt_focus__contacts +rpt_focus__student_enrollment \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

uv run dbt build --select rpt_focus__contacts rpt_focus__student_enrollment \
    rpt_focus__addresses rpt_focus__demographics \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

- [ ] **F2: Confirm no shared upstream moved**

The whole point of decisions E, F, and Q is that this branch changes no shared
model. Prove it.

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-import-v2 \
  diff --stat origin/main...HEAD -- \
  src/dbt/finalsite/ src/dbt/focus/ \
  src/dbt/kipptaf/models/extracts/deanslist/ \
  src/dbt/kipptaf/models/extracts/parentsquare/ \
  src/dbt/kipptaf/models/students/
```

Expected: empty. Any output means a shared upstream or a sibling extract was
touched — stop and revert that file.

- [ ] **F3: Open the PR**

Use `.github/pull_request_template.md` as the body. Include `Closes #4769`. Note
in the body that the kippmiami models get no dbt Cloud CI coverage and were
validated by local `dbt build` only, and that the `CONTACT1_SMS` header spelling
depends on Pre-flight P3.

## Self-review notes

Checked against issue #4769:

- Subtask 1 → Task 1. Subtask 2 → Pre-flight P2, verification only (decisions A,
  B, H are already satisfied by existing code). Subtask 3 → Task 4. Subtask 4 →
  Task 5. Subtask 5 → Task 7. Subtask 6 → Task 2. Subtask 7 → Task 6. Subtask 8
  → Task 3.
- Decisions with no task, because existing code already satisfies them: E and F
  (both phone sources already `clean_phone`-normalized), and the "leave
  DeansList alone" constraint, enforced negatively by F2.
- Type consistency: `contact_gender` is introduced in Task 4 step 3 and consumed
  in Task 4 step 4, then dropped by the `except` in that same CTE.
  `household_ids` is introduced in Task 5 step 3 and consumed in step 4.
  `shared_household_count` is produced in Task 5 step 4 and consumed in step 5.
  `contactN_type` is produced in Task 6 step 3 and consumed in Task 7 step 4.
- Known unverified assumption: the Focus CONTACTS template position and header
  spelling for the SMS columns (Pre-flight P3, Task 7 step 7).
