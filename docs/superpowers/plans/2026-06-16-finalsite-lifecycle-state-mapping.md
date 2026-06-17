# Finalsite → Focus Lifecycle Scope & State Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Miami-only dbt intermediate model that filters Finalsite
contacts to the enrollment-eligible set and classifies each one's Focus
enrollment action (`create` / `re_enroll` / `transfer_out`), sourcing the
enrollment start/end dates from the Status Report.

**Architecture:** One intermediate model in the `kippmiami` dbt project
(`int_finalsite__enrollment_lifecycle`) joins the `finalsite` package's
`stg_finalsite__contacts` (status, enrollment_type, grade, school year) to the
latest-partition snapshot of `stg_finalsite__status_report` (enrolled/withdrawal
dates) on `finalsite_enrollment_id`. The Status Report is partitioned and holds
many rows per enrollment, so it is deduplicated to its newest
`_dagster_partition_key` before the join. The model is pure dbt — kippmiami's
dbt assets auto-load into Dagster, so no Python/orchestration change is needed.

**Tech Stack:** dbt (BigQuery), `dbt_utils.deduplicate`, dbt unit tests,
sqlfluff (BigQuery dialect).

---

## Context & References

- **Design spec:**
  [docs/superpowers/specs/2026-05-29-finalsite-focus-integration-design.md](2026-05-29-finalsite-focus-integration-design.md)
  — this plan implements **Component 2 (Lifecycle scope & state mapping)**.
- **Umbrella issue:** #4073. Branch
  `cbini/feat/claude-finalsite-lifecycle-mapping` (worktree
  `.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping`).
- **Upstream (already merged, PR #4194):**
  - `src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql` — scalar
    columns used here: `finalsite_enrollment_id`, `status`, `enrollment_type`,
    `school_year_start`, `grade_canonical_name`.
  - `src/dbt/finalsite/models/staging/stg_finalsite__status_report.sql` — grain
    `(finalsite_enrollment_id, _dagster_partition_key)`; date columns used here:
    `enrolled_date`, `mid_year_withdrawal_date`, `summer_withdraw_date`,
    `not_enrolling_date`, `assigned_school`.

### Scope boundary (what this plan does NOT do)

- **No crosswalk / identity resolution.** Whether a `create` is really an
  _update_ of an existing Focus student is decided in Component 3 (crosswalk),
  not here. This model emits the Finalsite-side intended action only.
- **No Focus code mapping.** Translating `lifecycle_action` / withdrawal reason
  into Focus `ENROLLMENT_CODE` / `DROP_CODE` is Component 4 (output models).
- **No SFTP output.** That is Component 5.

### Eligibility & classification rules (spec-validated)

- **Active in-scope statuses** (25-status catalog → the accepted→enrolled set):
  `accepted`, `enrollment_in_progress`, `assigned_school`, `enrolled`,
  `retained`.
- **Transfer-out in-scope:** a student who _was_ enrolled (`enrolled_date`
  present) and now has a withdrawal date (`mid_year_withdrawal_date` or
  `summer_withdraw_date`) — must reach Focus to be end-dated even if their
  current status left the active set.
- `lifecycle_action`:
  - `transfer_out` — enrolled, then has a withdrawal end date.
  - `re_enroll` — active status, `enrollment_type = 'returning'`, no end date.
  - `create` — active status, `enrollment_type = 'new'`, no end date.
- `not_enrolling_date` alone (never enrolled) is **excluded**: `enrolled_date`
  is null, so the transfer-out gate fails and the active-status filter drops it.

### Running dbt locally (developer path)

All commands run with the repo profile + ADC (no 1Password needed):

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt \
  uv run dbt <cmd> --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping/src/dbt/kippmiami
```

`--target prod` and `stage_external_sources` are out of scope here — this model
only `ref()`s already-staged models, no external-table work.

---

## File Structure

- **Create:**
  `src/dbt/kippmiami/models/finalsite/intermediate/int_finalsite__enrollment_lifecycle.sql`
  — the lifecycle model.
- **Create:**
  `src/dbt/kippmiami/models/finalsite/intermediate/properties/int_finalsite__enrollment_lifecycle.yml`
  — descriptions, uniqueness/not-null/accepted-values tests, the unit test.
- **Modify:** `src/dbt/kippmiami/dbt_project.yml` — add a `finalsite:` model
  config block (schema + table materialization for the intermediate layer).

---

## Task 1: Verify source data and prepare the worktree

**Files:** none (verification only — no commit).

- [ ] **Step 1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`. Run once:

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping/src/dbt/kippmiami
```

Expected: `Installed from ...` lines, no error. (If it errors with "0 package(s)
installed", rerun — deps must succeed before any build/test.)

- [ ] **Step 2: Confirm the `status` and `enrollment_type` values in staged
      contacts**

Use the BigQuery MCP (`mcp__bigquery__execute_sql`). The merged staging table is
`teamster-332318.kippmiami_finalsite.stg_finalsite__contacts` (if Dagster has
not yet materialized it post-merge, fall back to the Plan-1 validation table
`teamster-332318.zz_stg_kippmiami_finalsite.contacts`).

```sql
select status, enrollment_type, count(*) as n
from `teamster-332318`.`kippmiami_finalsite`.`stg_finalsite__contacts`
group by status, enrollment_type
order by n desc
```

Expected: `status` values are a subset of the 25-status catalog; the active set
(`accepted`, `enrollment_in_progress`, `assigned_school`, `enrolled`,
`retained`) appears; `enrollment_type` is exactly `new` / `returning` (confirm
casing — the model and unit test assume lowercase). If casing differs, adjust
the literals in Task 3 / Task 2 to match.

- [ ] **Step 3: Confirm the school-year distribution**

```sql
select school_year_start, count(*) as n
from `teamster-332318`.`kippmiami_finalsite`.`stg_finalsite__contacts`
group by school_year_start
order by school_year_start
```

Expected: values cluster at `2025` (= `current_academic_year`) and possibly
`2026` (next-year re-enrollment). Confirms the
`school_year_start >= {{ var("current_academic_year") }}` filter keeps the
current and forward cohorts and drops historical years. If only `2025` is
present, the filter still behaves correctly.

- [ ] **Step 4: Confirm the Status Report has multiple partitions per
      enrollment**

```sql
select count(*) as total_rows,
  count(distinct finalsite_enrollment_id) as distinct_enrollments,
  count(distinct _dagster_partition_key) as distinct_partitions
from `teamster-332318`.`kippmiami_finalsite`.`stg_finalsite__status_report`
```

Expected: `total_rows > distinct_enrollments` (more than one partition's worth),
confirming the dedupe-to-latest-partition step in Task 3 is required.

---

## Task 2: Write the failing unit test (with a wrong-output stub)

**Files:**

- Create:
  `src/dbt/kippmiami/models/finalsite/intermediate/int_finalsite__enrollment_lifecycle.sql`
  (stub)
- Create:
  `src/dbt/kippmiami/models/finalsite/intermediate/properties/int_finalsite__enrollment_lifecycle.yml`
  (unit test only)

- [ ] **Step 1: Write a stub model that compiles but classifies wrong**

The stub returns the right columns and the right eligibility filter but
hard-codes `lifecycle_action` to `'create'`, so the unit test's `re_enroll` and
`transfer_out` expectations fail (true red, not a parse error).

```sql
with
    status_report_latest as (
        {{
            dbt_utils.deduplicate(
                relation=ref("finalsite", "stg_finalsite__status_report"),
                partition_by="finalsite_enrollment_id",
                order_by="_dagster_partition_key desc",
            )
        }}
    ),

    contacts as (
        select
            finalsite_enrollment_id,
            status as finalsite_status,
            enrollment_type,
            school_year_start,
            grade_canonical_name,
        from {{ ref("finalsite", "stg_finalsite__contacts") }}
        where school_year_start >= {{ var("current_academic_year") }}
    )

select
    c.finalsite_enrollment_id,
    c.finalsite_status,
    c.enrollment_type,
    c.school_year_start,
    c.grade_canonical_name,

    sr.assigned_school,
    sr.enrolled_date as enrollment_start_date,

    cast(null as date) as enrollment_end_date,
    cast(null as string) as withdrawal_reason,

    'create' as lifecycle_action,
from contacts as c
left join status_report_latest as sr
    on c.finalsite_enrollment_id = sr.finalsite_enrollment_id
where
    c.finalsite_status in (
        'accepted',
        'enrollment_in_progress',
        'assigned_school',
        'enrolled',
        'retained'
    )
```

- [ ] **Step 2: Write the unit test in the properties yml**

dbt unit-test fixture scalars must be UNQUOTED (yamllint `quoted-strings` fires
at CI otherwise; unquoted `YYYY-MM-DD` parses as a date). Every input column the
model reads is provided; every output column is asserted in `expect`.

```yaml
unit_tests:
  - name: test_enrollment_lifecycle_classification
    description:
      Classifies new/returning/withdrawn contacts and applies the eligibility
      and school-year filters.
    model: int_finalsite__enrollment_lifecycle
    given:
      - input: ref('finalsite', 'stg_finalsite__contacts')
        rows:
          - {
              finalsite_enrollment_id: c_new,
              status: enrolled,
              enrollment_type: new,
              school_year_start: 2025,
              grade_canonical_name: KF,
            }
          - {
              finalsite_enrollment_id: c_ret,
              status: enrolled,
              enrollment_type: returning,
              school_year_start: 2025,
              grade_canonical_name: 01,
            }
          - {
              finalsite_enrollment_id: c_xfer,
              status: enrolled,
              enrollment_type: returning,
              school_year_start: 2025,
              grade_canonical_name: 02,
            }
          - {
              finalsite_enrollment_id: c_old,
              status: enrolled,
              enrollment_type: new,
              school_year_start: 2024,
              grade_canonical_name: 03,
            }
          - {
              finalsite_enrollment_id: c_denied,
              status: denied,
              enrollment_type: new,
              school_year_start: 2025,
              grade_canonical_name: 04,
            }
          - {
              finalsite_enrollment_id: c_notenroll,
              status: not_enrolling,
              enrollment_type: new,
              school_year_start: 2025,
              grade_canonical_name: 05,
            }
      - input: ref('finalsite', 'stg_finalsite__status_report')
        rows:
          - {
              finalsite_enrollment_id: c_new,
              _dagster_partition_key: 2026-06-15,
              enrolled_date: 2025-08-15,
              mid_year_withdrawal_date: null,
              summer_withdraw_date: null,
              not_enrolling_date: null,
              assigned_school: School A,
            }
          - {
              finalsite_enrollment_id: c_ret,
              _dagster_partition_key: 2026-06-15,
              enrolled_date: 2025-08-15,
              mid_year_withdrawal_date: null,
              summer_withdraw_date: null,
              not_enrolling_date: null,
              assigned_school: School A,
            }
          - {
              finalsite_enrollment_id: c_xfer,
              _dagster_partition_key: 2026-06-10,
              enrolled_date: 2025-08-15,
              mid_year_withdrawal_date: null,
              summer_withdraw_date: null,
              not_enrolling_date: null,
              assigned_school: School A,
            }
          - {
              finalsite_enrollment_id: c_xfer,
              _dagster_partition_key: 2026-06-15,
              enrolled_date: 2025-08-15,
              mid_year_withdrawal_date: 2026-01-10,
              summer_withdraw_date: null,
              not_enrolling_date: null,
              assigned_school: School A,
            }
          - {
              finalsite_enrollment_id: c_notenroll,
              _dagster_partition_key: 2026-06-15,
              enrolled_date: null,
              mid_year_withdrawal_date: null,
              summer_withdraw_date: null,
              not_enrolling_date: 2025-07-01,
              assigned_school: null,
            }
    expect:
      rows:
        - {
            finalsite_enrollment_id: c_new,
            finalsite_status: enrolled,
            enrollment_type: new,
            school_year_start: 2025,
            grade_canonical_name: KF,
            assigned_school: School A,
            enrollment_start_date: 2025-08-15,
            enrollment_end_date: null,
            withdrawal_reason: null,
            lifecycle_action: create,
          }
        - {
            finalsite_enrollment_id: c_ret,
            finalsite_status: enrolled,
            enrollment_type: returning,
            school_year_start: 2025,
            grade_canonical_name: 01,
            assigned_school: School A,
            enrollment_start_date: 2025-08-15,
            enrollment_end_date: null,
            withdrawal_reason: null,
            lifecycle_action: re_enroll,
          }
        - {
            finalsite_enrollment_id: c_xfer,
            finalsite_status: enrolled,
            enrollment_type: returning,
            school_year_start: 2025,
            grade_canonical_name: 02,
            assigned_school: School A,
            enrollment_start_date: 2025-08-15,
            enrollment_end_date: 2026-01-10,
            withdrawal_reason: mid_year_withdrawal,
            lifecycle_action: transfer_out,
          }
```

Note the `expect` has 3 rows: `c_old` (2024) is dropped by the year filter,
`c_denied` by the status filter, and `c_notenroll` by both gates (never
enrolled, inactive status). `c_xfer` has two Status Report partitions —
`2026-06-15` wins, supplying the withdrawal date.

- [ ] **Step 3: Run the unit test and verify it FAILS**

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt \
  uv run dbt test --select int_finalsite__enrollment_lifecycle --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping/src/dbt/kippmiami
```

Expected: FAIL — the stub emits `lifecycle_action = create` for `c_ret`
(expected `re_enroll`) and `c_xfer` (expected `transfer_out`), and null
`enrollment_end_date` / `withdrawal_reason` for `c_xfer`. Do NOT commit yet.

---

## Task 3: Implement the classification logic

**Files:**

- Modify:
  `src/dbt/kippmiami/models/finalsite/intermediate/int_finalsite__enrollment_lifecycle.sql`
- Modify: `src/dbt/kippmiami/dbt_project.yml`

- [ ] **Step 1: Replace the stub model with the full logic**

Overwrite the SQL file with the real classification. `enrollment_end_date` uses
the NULL-skipping `min over unnest` pattern (not `least`, which nulls out if any
arg is null). The final `SELECT` reads from a single CTE, so columns are
unprefixed and follow ST06 ordering (plain refs, then constants, then case).

```sql
with
    status_report_latest as (
        {{
            dbt_utils.deduplicate(
                relation=ref("finalsite", "stg_finalsite__status_report"),
                partition_by="finalsite_enrollment_id",
                order_by="_dagster_partition_key desc",
            )
        }}
    ),

    contacts as (
        select
            finalsite_enrollment_id,
            status as finalsite_status,
            enrollment_type,
            school_year_start,
            grade_canonical_name,
        from {{ ref("finalsite", "stg_finalsite__contacts") }}
        where school_year_start >= {{ var("current_academic_year") }}
    ),

    joined as (
        select
            c.finalsite_enrollment_id,
            c.finalsite_status,
            c.enrollment_type,
            c.school_year_start,
            c.grade_canonical_name,

            sr.assigned_school,
            sr.enrolled_date as enrollment_start_date,

            (
                select min(d)
                from
                    unnest(
                        [
                            sr.mid_year_withdrawal_date,
                            sr.summer_withdraw_date,
                            sr.not_enrolling_date
                        ]
                    ) as d
            ) as enrollment_end_date,

            case
                when sr.mid_year_withdrawal_date is not null
                then 'mid_year_withdrawal'
                when sr.summer_withdraw_date is not null
                then 'summer_withdraw'
                when sr.not_enrolling_date is not null
                then 'not_enrolling'
            end as withdrawal_reason,
        from contacts as c
        left join status_report_latest as sr
            on c.finalsite_enrollment_id = sr.finalsite_enrollment_id
    )

select
    finalsite_enrollment_id,
    finalsite_status,
    enrollment_type,
    school_year_start,
    grade_canonical_name,
    assigned_school,
    enrollment_start_date,

    if(
        enrollment_start_date is not null and enrollment_end_date is not null,
        enrollment_end_date,
        cast(null as date)
    ) as enrollment_end_date,

    if(
        enrollment_start_date is not null and enrollment_end_date is not null,
        withdrawal_reason,
        cast(null as string)
    ) as withdrawal_reason,

    case
        when enrollment_start_date is not null and enrollment_end_date is not null
        then 'transfer_out'
        when enrollment_type = 'returning'
        then 're_enroll'
        else 'create'
    end as lifecycle_action,
from joined
where
    finalsite_status in (
        'accepted',
        'enrollment_in_progress',
        'assigned_school',
        'enrolled',
        'retained'
    )
    or (enrollment_start_date is not null and enrollment_end_date is not null)
```

- [ ] **Step 2: Add the kippmiami `finalsite` model config block**

In `src/dbt/kippmiami/dbt_project.yml`, under `models:` → `kippmiami:`, add a
`finalsite:` block (mirrors the existing `fldoe:` block — schema + table
materialization so the model's tests refresh when it rebuilds):

```yaml
finalsite:
  +schema: finalsite
  intermediate:
    +materialized: table
```

- [ ] **Step 3: Run the unit test and verify it PASSES**

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt \
  uv run dbt test --select int_finalsite__enrollment_lifecycle --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping/src/dbt/kippmiami
```

Expected: PASS — `c_new`→`create`, `c_ret`→`re_enroll`, `c_xfer`→`transfer_out`
with `enrollment_end_date = 2026-01-10` and
`withdrawal_reason = mid_year_withdrawal`.

---

## Task 4: Add descriptions and generic tests

**Files:**

- Modify:
  `src/dbt/kippmiami/models/finalsite/intermediate/properties/int_finalsite__enrollment_lifecycle.yml`

- [ ] **Step 1: Prepend the model block (description, tests) above the unit
      test**

Per-column single tests sit on the column; the grain note and accepted-values
live in the model `description` / column. Intermediate models require a
uniqueness test (no contract). Insert this `models:` block ABOVE the existing
`unit_tests:` block in the same file:

```yaml
models:
  - name: int_finalsite__enrollment_lifecycle
    description:
      One row per Finalsite contact that is in scope to push to Focus (KIPP
      Miami), with the intended Focus enrollment action. Built from
      `stg_finalsite__contacts` joined to the latest-partition snapshot of
      `stg_finalsite__status_report` on `finalsite_enrollment_id`. In scope = an
      active accepted-to-enrolled status (`accepted`, `enrollment_in_progress`,
      `assigned_school`, `enrolled`, `retained`) in the current or a forward
      school year, OR a previously-enrolled student who now has a withdrawal
      date (so Focus can be end-dated). `lifecycle_action` reflects the
      Finalsite-side intent only — whether a `create` is actually an update of
      an existing Focus student is resolved downstream by the identity
      crosswalk.
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description: Finalsite contact UUID; the grain of this model.
        data_tests:
          - unique
          - not_null
      - name: lifecycle_action
        data_type: string
        description:
          Intended Focus enrollment action — `create` (new enrollee),
          `re_enroll` (returning student, new enrollment row), or `transfer_out`
          (previously enrolled, now withdrawn — end-date the Focus enrollment).
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values: [create, re_enroll, transfer_out]
      - name: finalsite_status
        data_type: string
        description: Current Finalsite enrollment-workflow status.
      - name: enrollment_type
        data_type: string
        description: Finalsite enrollment type — `new` or `returning`.
      - name: school_year_start
        data_type: int64
        description: Start year of the contact's Finalsite school year.
      - name: grade_canonical_name
        data_type: string
        description: Finalsite canonical grade name for the enrollment.
      - name: assigned_school
        data_type: string
        description:
          School assigned in the Status Report; the Focus enrollment school
          before crosswalk mapping.
      - name: enrollment_start_date
        data_type: date
        description:
          Enrolled date from the Status Report (= Focus `START_DATE`); null
          until the student reaches the enrolled status.
      - name: enrollment_end_date
        data_type: date
        description:
          Earliest withdrawal date (mid-year, summer, or not-enrolling) for a
          previously-enrolled student; null unless this is a transfer-out.
      - name: withdrawal_reason
        data_type: string
        description:
          Which withdrawal date drove `enrollment_end_date`
          (`mid_year_withdrawal`, `summer_withdraw`, or `not_enrolling`); null
          unless this is a transfer-out.
```

- [ ] **Step 2: Run the full test suite for the model**

```bash
DBT_PROFILES_DIR=/workspaces/teamster/.dbt \
  uv run dbt build --select int_finalsite__enrollment_lifecycle --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping/src/dbt/kippmiami
```

Expected: the model builds as a table and `unique`, `not_null` (×2),
`accepted_values`, and the unit test all PASS. If `accepted_values` fails, an
unexpected `enrollment_type` value reached the `else` branch — re-check Task 1
Step 2 casing.

- [ ] **Step 3: Sanity-check the built output against real data**

```sql
select lifecycle_action, count(*) as n
from `teamster-332318`.`kippmiami_finalsite`.`int_finalsite__enrollment_lifecycle`
group by lifecycle_action
order by n desc
```

Expected: all three actions plausibly present; `transfer_out` rows all have a
non-null `enrollment_end_date`; `create` rows are `enrollment_type = new`.
Confirm with:

```sql
select
  lifecycle_action,
  countif(enrollment_end_date is null) as n_no_end,
  countif(enrollment_start_date is null) as n_no_start
from `teamster-332318`.`kippmiami_finalsite`.`int_finalsite__enrollment_lifecycle`
group by lifecycle_action
```

Expected: `transfer_out` → `n_no_end = 0`; `create` / `re_enroll` →
`n_no_end = <their count>` (no end date).

- [ ] **Step 4: Lint the changed files**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping && \
  /workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kippmiami/models/finalsite/intermediate/int_finalsite__enrollment_lifecycle.sql \
  src/dbt/kippmiami/models/finalsite/intermediate/properties/int_finalsite__enrollment_lifecycle.yml \
  src/dbt/kippmiami/dbt_project.yml
```

Expected: no issues (sqlfluff BigQuery, yamllint). Run from inside the worktree.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping \
  add src/dbt/kippmiami/models/finalsite/
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-lifecycle-mapping commit -m "$(cat <<'EOF'
feat(dbt): add finalsite enrollment lifecycle state mapping (kippmiami)

Classifies in-scope Finalsite contacts into create / re_enroll / transfer_out
for the Focus push, sourcing enrollment start/end dates from the Status Report.
Refs #4073.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

If the commit message is blocked by the secrets hook, fall back to
`.claude/scratch/commit-msg.txt` + `git commit -F` per the repo conventions.

---

## Self-Review

**1. Spec coverage (Component 2):** ✅ eligibility filter (active statuses +
target school year) → Task 3 `where`; ✅ Focus-operation classification (create
/ update / transfer-out / re-enroll) → `lifecycle_action`, with the _update_
distinction explicitly deferred to the crosswalk (Component 3) and documented;
✅ start/withdrawal dates sourced from `stg_finalsite__status_report` →
`enrollment_start_date` / `enrollment_end_date`; ✅ configurable/documented
status mapping → inlined, commented, and described in the model YAML (a
seed-driven Focus-code map is Component 4, out of scope).

**2. Placeholder scan:** No `TBD` / `handle edge cases` / "similar to Task N" —
every code step shows complete SQL/YAML and a runnable command with expected
output.

**3. Type consistency:** Column names and types are identical across the stub
(Task 2), the implementation (Task 3), and the properties YAML (Task 4):
`finalsite_enrollment_id` (string), `lifecycle_action` (string),
`enrollment_start_date` / `enrollment_end_date` (date), `school_year_start`
(int64). The unit test's `given`/`expect` columns match the model's inputs and
outputs.
