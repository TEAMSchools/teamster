# Finalsite to Focus Reconciliation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the kipptaf `rpt_focus__*` models pure desired-state and move all
KIPP Miami finalsite-to-Focus reconciliation into the kippmiami layer, fixing
start-date-drift enrollment matching and scoping the other feeds to enrolled
students.

**Architecture:** kipptaf `rpt_focus__student_enrollment` drops its live-Focus
diff and filters to the current academic year; the kippmiami wrapper becomes the
only reconciliation layer, matching entry-existence and drop-target on
`(student_id, syear)` and keying a withdrawal to the student's open Focus
enrollment. The three other feeds gain an enrolled-only filter in kipptaf.

**Tech Stack:** dbt (BigQuery), dbt unit tests, sqlfluff/trunk, `uv run dbt`.

## Global Constraints

- `current_academic_year` is `2026` in both kipptaf and kippmiami
  `dbt_project.yml`. Reference it as `{{ var("current_academic_year") }}` in
  SQL, never hardcode `2026`.
- SQL follows `src/dbt/CLAUDE.md` conventions: BigQuery dialect, trailing commas
  in `SELECT`, single-quoted strings, 88-char lines, no `QUALIFY`, no
  `ORDER BY`, no subqueries against tables/CTEs, max one function-nesting level,
  cast once in the earliest CTE. The Focus import column order is contract-fixed
  — keep the `-- trunk-ignore(sqlfluff/ST06)` comment on every contract-ordered
  `SELECT`.
- Unit-test fixture scalars are UNQUOTED (yamllint `quoted-strings`), EXCEPT
  leading-zero strings like `grade_id: "05"` / `start_date: "20250812"` which
  MUST be quoted (yamllint `octal-values`). Unquoted `YYYY-MM-DD` parses as a
  date.
- A column added to an upstream in this PR is not yet in the deferred relation,
  so mock it with input `format: sql`, never dict format.
- These are district (kippmiami) and source-consuming (kipptaf) models that dbt
  Cloud CI does NOT exercise (`src/dbt/CLAUDE.md` → "dbt Cloud CI builds only
  kipptaf" is a no-op for a district PR, and the kipptaf changes here do not add
  a source column). Validate locally.
- **Which project-dir to use per task** — a kipptaf model and its unit tests
  live in the kipptaf project; the kippmiami wrapper and the `focus`-package
  `stg_focus__*` build via the kippmiami project:
  - Tasks 1, 3, 4 (kipptaf `rpt_focus__*`): `--project-dir <wt>/src/dbt/kipptaf`
    and `--state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  - Tasks 2, 5 (kippmiami wrapper, `stg_focus__student_enrollment`):
    `--project-dir <wt>/src/dbt/kippmiami` and
    `--state /workspaces/teamster/src/dbt/kippmiami/target/prod`.
  - `<wt>` =
    `/workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation`.
  - The two projects have separate `test_type:unit,extracts.focus` sets; each
    task runs only its own project's tests.
- Fresh worktrees have no `dbt_packages/`. Run
  `uv run dbt deps --project-dir <wt>/src/dbt/kipptaf` and
  `uv run dbt deps --project-dir <wt>/src/dbt/kippmiami` once before the first
  build in each project.
- Use `git -C <wt>` for git. `--state` paths are the MAIN repo's absolute
  `target/prod` (worktrees have no refreshed manifest).
- After any fixture/contract edit, run the WHOLE focus unit-test directory for
  that project (`--select "test_type:unit,extracts.focus"`), not just one model
  — siblings mock the same refs.
- IDE Pyright/SQL diagnostics on worktree files are false positives; trust
  `uv run dbt` inside the worktree.

---

### Task 1: kipptaf `rpt_focus__student_enrollment` becomes desired-state

Remove the live-Focus diff, add the current-academic-year filter. The model
emits one desired row per current-AY in-scope student, with `end_date` and the
raw `drop_code` label populated for transfer-outs. Run all commands with
`--project-dir <wt>/src/dbt/kipptaf`.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `int_finalsite__enrollment_lifecycle` (`finalsite_enrollment_id`,
  `school_year_start`, `grade_canonical_name`, `promotion_status`,
  `assigned_school`, `enrollment_start_date`, `enrollment_end_date`,
  `is_transfer_out`), `int_focus__school_year_first_day` (`syear`,
  `first_day_of_school`), `int_finalsite__contact_id_attributes`
  (`finalsite_enrollment_id`, `focus_student_id_prefixed`),
  `int_finalsite__contact_custom_attributes` (`finalsite_enrollment_id`,
  `fl_state_withdraw_codes_ss`, `withdrawal_school_txt`),
  `int_people__location_crosswalk` (`location_name`,
  `location_focus_school_id`).
- Produces: the 28-column Focus `STUDENT_ENROLLMENT` layout consumed by the
  kippmiami wrapper. Same column names/types as today; the only behavioral
  change is no delta suppression and current-AY-only rows. `drop_code` remains
  the RAW Finalsite label (decoded downstream).

- [ ] **Step 1: Update the four existing unit tests (they are the failing
      test)**

Edit `properties/rpt_focus__student_enrollment.yml`:

1. **Delete the entire `test_student_enrollment_focus_delta` unit test** (its
   delta logic moves to the kippmiami wrapper in Task 2).
1. In `test_student_enrollment_shape`, `test_student_enrollment_transfer_out`,
   and `test_student_enrollment_start_date_floor`: **remove the
   `source('kippmiami_dlt_focus', 'student_enrollment')` given input block**
   (the model no longer reads Focus).
1. Change every `school_year_start` / `syear` fixture value that is not `2026`
   to `2026`, and shift the matching `enrollment_start_date` / expected
   `start_date` / `first_day_of_school` into the 2026 school year, because the
   new current-AY filter drops non-2026 rows. Concretely:
   - `test_student_enrollment_shape`: set the two emitted rows and the excluded
     pre-enrollment row to `school_year_start = 2026`; set
     `enrollment_start_date` to `2026-08-12`; set the
     `int_focus__school_year_first_day` row to
     `select 2026 as syear, date '2026-08-11' as first_day_of_school`; set
     expected `syear: 2026` and `start_date: "20260812"`.
   - `test_student_enrollment_transfer_out`: `school_year_start = 2026`,
     `enrollment_start_date = 2026-08-12`, `enrollment_end_date = 2027-01-15`,
     first-day row `2026`/`2026-08-11`; expected `syear: 2026`,
     `start_date: "20260812"`, `end_date: "20270115"`.
   - `test_student_enrollment_start_date_floor`: keep only two rows, both
     `school_year_start = 2026` — `ef1` starting `2026-07-15` (floored up to
     `2026-08-11`) and `ef2` starting `2026-09-02` (unchanged). Delete rows
     `ef3` (2025) and `ef4` (2099) and their
     `int_finalsite__contact_custom_attributes` /
     `int_finalsite__contact_id_attributes` rows. The
     `int_focus__school_year_first_day` input keeps only
     `select 2026 as syear, date '2026-08-11' as first_day_of_school`. Expected
     rows: `84009009001` → `start_date "20260811"`, `84009009002` →
     `start_date "20260902"`.
1. Update the model `description:` — replace the "delta feed … suppressed …"
   sentences (matching on `student_id`/`syear`/`start_date`) with desired-state
   language: one row per current-academic-year in-scope enrollment; no Focus
   reconciliation here (the kippmiami wrapper reconciles).

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: FAIL — the model SQL still filters via the old delta / lacks the
current-AY filter, so the shape/transfer/floor expectations do not match.

- [ ] **Step 3: Rewrite the model SQL**

Replace the entire contents of
`src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql` with:

```sql
with
    enrollments as (
        select
            l.school_year_start,
            l.grade_canonical_name,
            l.promotion_status,
            l.assigned_school,
            l.enrollment_end_date,
            l.is_transfer_out,
            l.finalsite_enrollment_id,

            -- Finalsite emits pre-first-day enrolled_dates (contract/registration
            -- dates); Focus matches enrollment on the first attendance calendar
            -- date, so floor the start date up to the school year's first day
            -- (derived per school year from the Focus attendance calendar). Rows
            -- already on/after the first day, and years with no calendar, are
            -- left unchanged.
            greatest(
                l.enrollment_start_date,
                coalesce(fd.first_day_of_school, l.enrollment_start_date)
            ) as start_date,
        from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd
            on l.school_year_start = fd.syear
        -- enrolled-only + current-academic-year desired state. Pre-enrollment
        -- statuses carry no enrolled_date and are deferred until Finalsite mints
        -- enrollment_start_date; a freshly enrolled student with no school
        -- assignment yet is likewise deferred (Focus needs a school id). Prior
        -- and future school years are out of scope — the kippmiami wrapper
        -- reconciles this desired state against live Focus.
        where
            l.enrollment_start_date is not null
            and l.assigned_school is not null
            and l.school_year_start = {{ var("current_academic_year") }}
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    e.school_year_start as syear,

    sch.location_focus_school_id as school_id,

    ida.focus_student_id_prefixed as student_id,

    if(
        e.grade_canonical_name = 'k',
        'KG',
        -- non-digit grade names (e.g. pk) yield null here; Miami is K-9 today
        lpad(regexp_extract(e.grade_canonical_name, r'\d+'), 2, '0')
    ) as grade_id,

    format_date('%Y%m%d', e.start_date) as start_date,

    -- enrollment_code is the entry action and does not change on transfer_out;
    -- a withdrawal is expressed by drop_code + end_date, not by clearing the
    -- entry code.
    case when e.grade_canonical_name = 'k' then 'E05' else 'E01' end as enrollment_code,

    -- enrollment_end_date is gated to transfer_out upstream in
    -- int_finalsite__enrollment_lifecycle, so end_date needs no re-gating.
    format_date('%Y%m%d', e.enrollment_end_date) as end_date,

    -- Focus import header is drop_code; this carries the raw Finalsite withdraw
    -- label, which the kippmiami reconciliation layer decodes to the Focus
    -- short_name. fl_state_withdraw_codes_ss is a raw contact custom attribute
    -- (NOT gated upstream), so gate it to transfer_out here — a withdraw code is
    -- only meaningful for a withdrawal, and an ungated value would emit a drop
    -- code for a still-enrolled student downstream.
    if(
        e.is_transfer_out, cca.fl_state_withdraw_codes_ss, cast(null as string)
    ) as drop_code,

    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,

    if(e.is_transfer_out, cca.withdrawal_school_txt, cast(null as string)) as moved_to,

    cast(null as string) as sec_sch,

    e.promotion_status as grde_prom_st,

    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
from enrollments as e
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on e.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
left join
    {{ ref("int_finalsite__contact_custom_attributes") }} as cca
    on e.finalsite_enrollment_id = cca.finalsite_enrollment_id
left join
    {{ ref("int_people__location_crosswalk") }} as sch
    on e.assigned_school = sch.location_name
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: PASS (the three kipptaf enrollment unit tests, plus the unchanged
demographics/addresses/contacts tests).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "refactor(focus): make kipptaf enrollment extract desired-state, current-AY only

Refs #4481"
```

---

### Task 2: kippmiami `rpt_focus__student_enrollment` reconciliation

Rewrite the wrapper into an entry/exit reconciliation keyed on
`(student_id, syear)`, with the exit branch targeting the student's open Focus
enrollment. Run all commands with `--project-dir <wt>/src/dbt/kippmiami`.

**Files:**

- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__student_enrollment")` (the
  Task 1 desired state — 28 columns, raw `drop_code` label),
  `stg_focus__student_enrollment` (`syear`, `student_id` int64, `start_date`
  date, `end_date` date, `drop_code` int64),
  `stg_focus__student_enrollment_codes` (`title`, `short_name`, `type`).
- Produces: the 28-column Focus SFTP feed (the file the extract job pushes).

- [ ] **Step 1: Rewrite the four unit tests (the failing test)**

Replace the `unit_tests:` block in
`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`
with four cases. In every `stg_focus__student_enrollment` mock, add a `syear`
column (the reconciliation now matches on it). Keep the full 28-column layout in
each `source(...)` given and each `expect` (copy the column boilerplate from the
existing cases in this same file — only the values called out below differ).

1. `entry_new_student_year_emitted` — desired
   `(student 8400000001, syear 2026, start_date "20260811")`;
   `stg_focus__student_enrollment` empty (`from (select 1) where false`, columns
   `syear int64, student_id int64, start_date date, end_date date, enrollment_code int64, drop_code int64`);
   codes seed as today. Expect the full desired row passed through with
   `enrollment_code E01` and (no exit) `end_date`/`drop_code` null.
1. `entry_absent_year_resends_despite_drifted_focus_startdate` — desired
   `(8400000002, 2026, "20260811")`; Focus has the SAME student in a DIFFERENT
   year only (`syear 2025, start_date date '2025-08-12'`), so `(student, 2026)`
   is absent → the 2026 entry is emitted in full. Confirms year scoping.
1. `exit_open_row_drift_emits_drop_on_focus_startdate` — desired
   `(8400000003, 2026, "20260811", end_date "20270115", drop_code '(W02) In District Transfer')`;
   Focus has an OPEN 2026 row with a DRIFTED start_date
   (`syear 2026, start_date date '2026-08-25', end_date null, drop_code null`).
   Expect ONE row: `syear 2026`, `start_date "20260825"` (the Focus open row's
   date), `enrollment_code null`, `end_date "20270115"`, `drop_code 'W02'`,
   other columns passed through from desired.
1. `exit_suppressed_when_open_row_has_drop_or_closed` — two desired withdrawal
   rows: `(8400000004, 2026, end_date "20270115", drop_code '(W02)…')` whose
   Focus 2026 open row ALREADY has a `drop_code`, and
   `(8400000005, 2026, end_date "20270115", drop_code '(W02)…')` whose only
   Focus 2026 row is CLOSED (`end_date` set, so no open row). Expect EMPTY
   (`from (select 1) where false`).

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: FAIL — the wrapper still matches on `(student_id, start_date)` and has
no entry/exit split.

- [ ] **Step 3: Rewrite the model SQL**

Replace the entire contents of
`src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`
with:

```sql
with
    -- live Focus enrollments, keys pre-formatted to the export string shapes so
    -- the joins below compare plain columns (no one-sided casts in ON)
    focus_enrollment as (
        select
            syear,
            cast(student_id as string) as student_id,
            format_date('%Y%m%d', start_date) as start_date,
            end_date,
            drop_code,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    -- entry-existence key. Match on (student_id, syear) only: ops manually edit
    -- the floored start_date in Focus after import, so a start_date match would
    -- re-open an already-loaded student-year as "new".
    focus_year as (select distinct student_id, syear, from focus_enrollment),

    -- exit target: the student-year's open (end_date is null) Focus row and
    -- whether it already carries a drop_code. A withdrawal attaches here, keyed
    -- to the open row's actual (possibly drifted) start_date. At most one open
    -- row per (student_id, syear) is expected — enforced by a data test on
    -- stg_focus__student_enrollment.
    focus_open as (
        select
            syear,
            student_id,
            min(start_date) as start_date,
            logical_or(drop_code is not null) as has_drop_code,
        from focus_enrollment
        where end_date is null
        group by syear, student_id
    ),

    -- desired state from kipptaf with the raw drop_code label decoded to the
    -- Focus short_name
    desired as (
        select d.*, dc.short_name as drop_code_decoded,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.drop_code = dc.title
            and dc.type = 'Drop'
    ),

    -- entry branch: student-year absent from Focus -> send the full entry row
    -- (with a same-run exit filled in if the desired row already carries one)
    entries as (
        select d.*,
        from desired as d
        left join
            focus_year as fy
            on d.student_id = fy.student_id
            and d.syear = fy.syear
        where fy.student_id is null
    ),

    -- exit branch: student-year present, its open row lacks a drop_code, and
    -- Finalsite now shows a withdrawal -> send the drop keyed to the open row's
    -- start_date; enrollment_code stays null so the entry is never overwritten
    exits as (
        select d.*, fo.start_date as focus_open_start_date,
        from desired as d
        inner join
            focus_open as fo
            on d.student_id = fo.student_id
            and d.syear = fo.syear
        where d.end_date is not null and not fo.has_drop_code
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    enrollment_code,
    end_date,
    drop_code_decoded as drop_code,
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

union all

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    focus_open_start_date as start_date,
    cast(null as string) as enrollment_code,
    end_date,
    drop_code_decoded as drop_code,
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
from exits
```

Update the model `description:` in the properties yml to describe the entry/exit
reconciliation and `(student_id, syear)` matching.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: PASS (all four kippmiami wrapper unit tests).

- [ ] **Step 5: Build the model end-to-end to confirm the contract holds**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev \
  --select rpt_focus__student_enrollment
```

Expected: PASS (contract columns match, model builds). If the desired-state
`kipptaf_extracts` source is stale in dev, add `--favor-state`.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "refactor(focus): reconcile kippmiami enrollment on student and year, drop to open row

Refs #4481"
```

---

### Task 3: enrolled-only filter on demographics and addresses

Run all commands with `--project-dir <wt>/src/dbt/kipptaf`.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql`
- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts.status` (the student's own contact record,
  aliased `c` in both models).
- Produces: unchanged column layouts; rows now restricted to
  `status = 'enrolled'`.

- [ ] **Step 1: Update the unit tests (the failing test)**

In `properties/rpt_focus__demographics.yml` `test_demographics_shape`: the
`stg_finalsite__contacts` mock is dict format with no `status` field. Add
`status: enrolled` to the three emitted rows (`enr-001`, `enr-002`, `enr-003`)
and to `enr-004` (already excluded for a missing minted id). Add a fifth contact
`enr-005` with `status: applied`, plus a matching
`int_finalsite__enrollment_lifecycle` row and a
`int_finalsite__contact_id_attributes` row (`select 'enr-005', '84001001005'`);
it must NOT appear in `expect` (excluded by the enrolled-only filter). Leave the
three expected rows unchanged.

In `properties/rpt_focus__addresses.yml` `test_addresses_shape`: apply the same
pattern — add `status: enrolled` to the emitted contact row(s), and add one
`status`-not-`enrolled` contact (with a minted id and a lifecycle row) that must
NOT appear in `expect`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: FAIL — the new non-enrolled fixture row is emitted (no filter yet).

- [ ] **Step 3: Add the filter to both models**

In `rpt_focus__demographics.sql`, append as the final line (after the last
`left join ... lcc ...`):

```sql
where c.status = 'enrolled'
```

In `rpt_focus__addresses.sql`, append after the last join:

```sql
where c.status = 'enrolled'
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "feat(focus): restrict demographics and addresses feeds to enrolled students

Refs #4481"
```

---

### Task 4: enrolled-only filter on contacts (gated on the student)

The contacts model's driving `stg_finalsite__contacts` alias `g` is the
GUARDIAN. Gate on the STUDENT's status via a new join. Run all commands with
`--project-dir <wt>/src/dbt/kipptaf`.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts` joined a second time on the student key
  (`rel.finalsite_enrollment_id`) for `status`.
- Produces: unchanged column layout; guardian rows now restricted to students
  whose `status = 'enrolled'`.

- [ ] **Step 1: Update the unit test (the failing test)**

In `properties/rpt_focus__contacts.yml` `test_contacts_two_guardians`: the mock
provides student and guardian `stg_finalsite__contacts` rows. Add
`status: enrolled` to the STUDENT contact row(s) that should emit. Add a second
student whose `status` is not `enrolled` (with a guardian relationship, a
lifecycle row, and a minted `int_finalsite__contact_id_attributes` id) and
assert its guardian rows do NOT appear in `expect`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: FAIL — the non-enrolled student's guardians are emitted (no filter
yet).

- [ ] **Step 3: Add the student join and filter**

In `rpt_focus__contacts.sql`, the model currently ends:

```sql
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on rel.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
where
    rel.rel_type
    in ('parent', 'guardian', 'grandparent', 'stepparent', 'relative', 'aunt/uncle')
```

Add a student-contact join immediately before the `where`, and a status
predicate in the `where`:

```sql
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on rel.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
inner join
    {{ ref("stg_finalsite__contacts") }} as stu
    on rel.finalsite_enrollment_id = stu.finalsite_enrollment_id
where
    rel.rel_type
    in ('parent', 'guardian', 'grandparent', 'stepparent', 'relative', 'aunt/uncle')
    and stu.status = 'enrolled'
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "feat(focus): restrict contacts feed to enrolled students

Refs #4481"
```

---

### Task 5: one-open-enrollment-per-student-year data test

Guards the exit-branch assumption that a `(student_id, syear)` has at most one
open (`end_date is null`) Focus enrollment. `stg_focus__student_enrollment` is a
`focus`-package model — run commands with
`--project-dir <wt>/src/dbt/kippmiami`.

**Files:**

- Modify:
  `src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `stg_focus__student_enrollment` (`student_id`, `syear`, `end_date`).
- Produces: a warn-level test result.

- [ ] **Step 1: Add the test**

In `properties/stg_focus__student_enrollment.yml`, add a model-level
`data_tests:` block (above `columns:`) scoped to open rows:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_id
          - syear
      config:
        where: end_date is null
        severity: warn
```

Rationale for `warn`: a duplicate open row is a Focus data-hygiene issue for
enrollment ops, not a pipeline defect; the wrapper's `focus_open` `min()` picks
one deterministically.

- [ ] **Step 2: Validate the test compiles and runs against prod**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev \
  --select stg_focus__student_enrollment
```

Expected: the new test executes (PASS, or WARN if Focus currently holds a
duplicate open row — record the count if so).

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  src/dbt/focus/models/staging/properties/stg_focus__student_enrollment.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "test(focus): warn on multiple open enrollments per student-year

Refs #4481"
```

---

### Task 6: update the reference doc

**Files:**

- Modify: `docs/reference/finalsite-focus-import.md`

**Interfaces:**

- Consumes: nothing (documentation).
- Produces: behavior documentation matching the new pipeline.

- [ ] **Step 1: Edit the doc**

Update `docs/reference/finalsite-focus-import.md` for the four behavior changes:

1. Enrollment feed is current-academic-year only (prior/future-year enrollments
   do not flow).
1. Demographics, Addresses, and Contacts flow only for students whose Finalsite
   status is `enrolled` (pre-enrollment statuses no longer flow). Update the
   "Demographics is not held back this way" and "What gets sent" sections.
1. A withdrawal now targets the student's OPEN Focus enrollment matched on
   student and school year (not the imported start date), so an ops-edited Focus
   start date no longer breaks the match. Update the "How the pipeline knows
   Focus already has an enrollment" section.
1. A `drop_code` is no longer backfilled onto an ALREADY-CLOSED Focus enrollment
   (only onto an open one). Update the "Withdraw / drop codes" and "Where to
   make corrections" sections.

- [ ] **Step 2: Lint the doc**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/finalsite-focus-import.md </dev/null
```

Expected: no markdownlint issues (prettier reflow is applied by the pre-commit
hook).

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation add \
  docs/reference/finalsite-focus-import.md
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation commit -m "docs(focus): document enrolled-only feeds and open-enrollment drop matching

Refs #4481"
```

---

### Task 7: final verification

- [ ] **Step 1: Full focus tests in both projects**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select "test_type:unit,extracts.focus"
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation/src/dbt/kippmiami \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev \
  --select "rpt_focus__student_enrollment stg_focus__student_enrollment test_type:unit,extracts.focus"
```

Expected: all unit tests and the kippmiami build PASS.

- [ ] **Step 2: Trunk-check the changed SQL/YAML from inside the worktree**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-focus-import-consolidation && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql </dev/null
```

Expected: no sqlfluff/yamllint issues.

- [ ] **Step 3: Open the PR**

Push the branch and open a PR against `main` using
`.github/pull_request_template.md`, body referencing `Closes #4481`. Note in the
PR that these are district/package models not exercised by dbt Cloud CI, so
validation is the local `dbt build`/unit tests above.
