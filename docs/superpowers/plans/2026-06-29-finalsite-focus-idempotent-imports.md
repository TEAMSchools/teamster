# Finalsite to Focus idempotent imports — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the five Finalsite-to-Focus SFTP extracts idempotent (diff
against current Focus state, import-once where required), resolve the #4208
enrollment and withdraw codes, and apply the Florida 8400 student-id prefix.

**Architecture:** `kipptaf` `rpt_focus__*` stay the desired-state build and gain
the 8400 prefix (req 5) and grade-based enrollment code (req 4). The `kippmiami`
`rpt_focus__*` pass-throughs become the reconciliation layer — they join current
Focus state (the `focus` package, available only in `kippmiami`), decode the
withdraw code, and apply the diff / import-once filters. New `stg_focus__*`
staging models expose the Focus linkage tables req 1 needs.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Dagster dlt (Focus replication).

Spec:
`docs/superpowers/specs/2026-06-29-finalsite-focus-idempotent-imports-design.md`.
Issue: [#4279](https://github.com/TEAMSchools/teamster/issues/4279).

## Global Constraints

- Read `src/dbt/CLAUDE.md`, `src/dbt/kipptaf/CLAUDE.md`,
  `src/dbt/kippmiami/CLAUDE.md`, `src/dbt/focus/CLAUDE.md`, and
  `src/dbt/finalsite/CLAUDE.md` before editing those projects. Invoke `Skill`
  with skill `dbt:using-dbt-for-analytics-engineering` before any dbt work.
- The `rpt_focus__*` output column **names and left-to-right order must not
  change** — the Dagster `header_replacements` in
  `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml` map them to
  the Focus headers positionally. (Exception: `kipptaf`
  `rpt_focus__student_enrollment` renames `drop_code` to a carrier column;
  `kippmiami` re-emits `drop_code` in the same position.)
- All `rpt_`/staging models are contract-enforced; update the `properties/*.yml`
  `data_type` list whenever a column is added, removed, or renamed.
- Match key (export to Focus):
  `concat('8400', focus_student_id) = students.student_id`.
- Enrollment match grain: `(student_id, start_date)` only.
- Diff rule: a populated export column triggers re-send when it differs —
  `export_col is not null and export_col is distinct from focus_norm`. Unmatched
  students/enrollments are always kept.
- Import-once codes: emit `enrollment_code`/`drop_code` only when the matched
  Focus enrollment's value is null.
- dbt CLI locally (build source-package models through the consuming district):
  `DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt <cmd> --project-dir <abs worktree>/src/dbt/<project> --defer --state <abs worktree>/src/dbt/<project>/target/prod --target dev`.
  A fresh worktree needs
  `uv run dbt deps --project-dir <abs worktree>/src/dbt/<project>` first.
- `--target prod` builds are classifier-blocked — hand prod runs to the user.
- Worktree: prefix every git call with
  `git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-idempotent-imports`
  and every dbt call with the worktree `--project-dir`. Trunk-check changed
  files from inside the worktree with
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>`.

---

## Phase 1 — kipptaf desired state (reqs 4 and 5)

No Focus dependency; validated entirely by dbt unit tests.

### Task 1: 8400 prefix on all five kipptaf extracts

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql`
- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`
- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__linked_students.sql`
- Modify: the matching `properties/*.yml` unit-test `expect` rows.

**Interfaces:**

- Produces: every emitted student id is `concat('8400', focus_student_id)`
  (10-char string, or `NULL` when `focus_student_id` is null).

- [ ] **Step 1: Update the demographics unit test.** In
      `properties/rpt_focus__demographics.yml`, change the `unit_tests` `expect`
      `stdt_id` from the raw id to the prefixed value (e.g. `305000` becomes
      `'8400305000'`; quote leading-zero-safe). Add a `given` `focus_student_id`
      of `305000` if not already present.

- [ ] **Step 2: Run it to confirm it fails.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
    --select rpt_focus__demographics \
    --project-dir <worktree>/src/dbt/kipptaf --target dev
  ```

  Expected: FAIL (model still emits the raw id).

- [ ] **Step 3: Apply the prefix in each model.** Replace the id projection.
      Demographics:

  ```sql
  concat('8400', ida.focus_student_id) as stdt_id,
  ```

  `addresses`, `contacts`, `student_enrollment`:
  `concat('8400', ida.focus_student_id) as student_id,`. `linked_students` —
  prefix both sides before `least`/`greatest`:

  ```sql
  least(
      concat('8400', ida_a.focus_student_id),
      concat('8400', ida_b.focus_student_id)
  ) as primary_student_id,
  greatest(
      concat('8400', ida_a.focus_student_id),
      concat('8400', ida_b.focus_student_id)
  ) as secondary_student_id,
  ```

- [ ] **Step 4: Update the other four unit tests** the same way (prefix the
      expected id values in each `properties/*.yml` `expect` block).

- [ ] **Step 5: Run all five unit tests to pass.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
    --select "rpt_focus__demographics rpt_focus__addresses rpt_focus__contacts rpt_focus__student_enrollment rpt_focus__linked_students" \
    --project-dir <worktree>/src/dbt/kipptaf --target dev
  ```

  Expected: PASS.

- [ ] **Step 6: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): apply 8400 focus student-id prefix (#4279)"
  ```

### Task 2: enrollment code (E05/E01) and withdraw-label carrier

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Produces: `enrollment_code` (`E05` for `grade_canonical_name = 'k'`, else
  `E01`, `NULL` on `transfer_out`); a new carrier column `state_withdraw_label`
  (raw `cca.fl_state_withdraw_codes_ss`) replacing the old `drop_code` crosswalk
  output. Column position of `state_withdraw_label` is the same slot `drop_code`
  occupied.

- [ ] **Step 1: Update the unit test.** In the `properties` `unit_tests`:
  - For a `create`/KG row assert `enrollment_code: E05`; add a non-KG `create`
    row asserting `enrollment_code: E01`.
  - Replace the `drop_code` assertion with `state_withdraw_label` equal to the
    mocked `fl_state_withdraw_codes_ss` (e.g. `(W02) In District Transfer`).
  - Remove the `enrollment_code_crosswalk` and `drop_code_crosswalk` mocked
    `given` inputs (no longer referenced).

- [ ] **Step 2: Run to confirm fail.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
    --select rpt_focus__student_enrollment \
    --project-dir <worktree>/src/dbt/kipptaf --target dev
  ```

  Expected: FAIL.

- [ ] **Step 3: Edit the model.** Replace the `enrollment_code` projection (drop
      the `ec` crosswalk join) with:

  ```sql
  case
      when l.lifecycle_action = 'transfer_out'
      then cast(null as string)
      when l.grade_canonical_name = 'k'
      then 'E05'
      else 'E01'
  end as enrollment_code,
  ```

  Replace the `dc.focus_drop_code as drop_code` projection (drop the `dc`
  crosswalk join) with the raw carrier in the same column slot:

  ```sql
  cca.fl_state_withdraw_codes_ss as state_withdraw_label,
  ```

  Delete the two `left join ... enrollment_code_crosswalk` /
  `... drop_code_crosswalk` blocks.

- [ ] **Step 4: Update the contract yml.** Rename the `drop_code` column entry
      to `state_withdraw_label` (keep `data_type: string`, same position);
      update its `description`. Keep all other columns/order unchanged.

- [ ] **Step 5: Run unit test to pass.** (command from Step 2.) Expected: PASS.

- [ ] **Step 6: Parse kipptaf to confirm no dangling crosswalk refs.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse \
    --project-dir <worktree>/src/dbt/kipptaf
  ```

  Expected: parses clean. (The two `stg_google_sheets__focus__*_crosswalk`
  models are now unused by this model; leave them in place — other refs or a
  later cleanup handle removal.)

- [ ] **Step 7: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): grade-based focus enrollment code + withdraw carrier (#4279)"
  ```

---

## Phase 2 — Focus linkage staging (req 1 prerequisite)

### Task 3: materialize the Focus linkage tables (dlt)

**Files:**

- Inspect: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`
- Inspect: `src/teamster/libraries/dlt/**` (the `sql_database` factory)

**Interfaces:**

- Produces: confirmation that `students_join_address`, `students_join_people`,
  `people`, and `students_join_students` either exist in
  `dagster_kippmiami_dlt_focus` or a documented reason they cannot, plus their
  column lists for Task 4.

- [ ] **Step 1: Confirm current absence.**

  ```sql
  select table_id, row_count
  from `teamster-332318`.dagster_kippmiami_dlt_focus.__TABLES__
  where table_id in (
    'students_join_address', 'students_join_people',
    'people', 'students_join_students'
  )
  ```

  Expected: 0 rows (tables absent today).

- [ ] **Step 2: Determine why.** Read the dlt `sql_database` resource/factory
      used by `kippmiami/dlt/focus` to see whether empty/absent source tables
      are skipped, errored, or filtered. Check the most recent
      `kippmiami/dlt/focus` run logs (`mcp__dagster__get_run_logs`) for
      per-table skip/error messages.

- [ ] **Step 3: Decide the fix and record it in the plan.** Likely one of: (a)
      the Focus source tables have rows but a config/selection bug drops them —
      fix the config; (b) the source tables are genuinely empty and dlt does not
      create empty relations — confirm the table will appear once Focus has its
      first row, and note that Task 4 staging + Task 7-9 filters stay
      **un-merged** until the relations exist (do not ship staging models on
      absent sources — they fail to build). If (b), STOP and surface to the
      user: req 1 cannot be validated end to end until Focus holds linkage data;
      reqs 2-5 proceed independently.

- [ ] **Step 4: If a config change was needed,** hand the prod re-pull to the
      user (dlt asset materialization is a prod deploy). Re-run Step 1 after to
      confirm the tables exist; capture their columns:

  ```sql
  select table_name, column_name, data_type
  from `teamster-332318`.dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS
  where table_name in (
    'students_join_address', 'students_join_people',
    'people', 'students_join_students'
  )
  and column_name not like '\\_dlt%'
  order by table_name, ordinal_position
  ```

- [ ] **Step 5: Commit** any dlt config change.

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "fix(dlt): materialize focus student linkage tables (#4279)"
  ```

### Task 4: Focus linkage staging models

**Files** (create, one `.sql` + one `properties/*.yml` each):

- `src/dbt/focus/models/staging/stg_focus__people.sql`
- `src/dbt/focus/models/staging/stg_focus__students_join_people.sql`
- `src/dbt/focus/models/staging/stg_focus__students_join_address.sql`
- `src/dbt/focus/models/staging/stg_focus__students_join_students.sql`
- Modify: `src/dbt/focus/models/staging/sources-bigquery.yml` (4 source tables).

**Interfaces:**

- Produces: `stg_focus__students_join_address` (keyed by `student_id` +
  `address_id`), `stg_focus__students_join_people` (`student_id` + `person_id`),
  `stg_focus__students_join_students` (`student_id` + linked `student_id`),
  `stg_focus__people`. Exact columns from Task 3 Step 4.

- [ ] **Step 1: Add the four source tables** to `sources-bigquery.yml` under the
      existing `focus` source `name`, mirroring an existing entry (e.g.
      `address`).

- [ ] **Step 2: Write each staging model** following the existing
      `stg_focus__address` pattern: read through a `source` CTE
      (`with source as (select *, from {{ source("focus", "<table>") }})`),
      select the real columns enumerated in Task 3 Step 4, drop `_dlt_*` and the
      audit quad, and apply `where deleted is null` only on tables that have a
      `deleted` column (per `src/dbt/focus/CLAUDE.md`: present on `address`;
      confirm per table).

  Example skeleton (`stg_focus__students_join_address`):

  ```sql
  with source as (select *, from {{ source("focus", "students_join_address") }})

  select
      student_id,
      address_id,
      -- ...remaining real columns from INFORMATION_SCHEMA...
  from source
  ```

- [ ] **Step 3: Write each `properties/*.yml`** with `data_type` per column and
      a uniqueness test: `unique` on the single PK where one exists, else
      `dbt_utils.unique_combination_of_columns` on the join pair, both at
      `severity: error`.

- [ ] **Step 4: Build the four models through kippmiami.**

  ```bash
  uv run dbt deps --project-dir <worktree>/src/dbt/kippmiami
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt build \
    --select "stg_focus__people stg_focus__students_join_people stg_focus__students_join_address stg_focus__students_join_students" \
    --project-dir <worktree>/src/dbt/kippmiami \
    --defer --state <worktree>/src/dbt/kippmiami/target/prod --target dev
  ```

  Expected: builds + contract + uniqueness pass. (Blocked until Task 3 makes the
  sources exist.)

- [ ] **Step 5: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(focus): stage student linkage tables for import-once (#4279)"
  ```

---

## Phase 3 — kippmiami reconciliation

Each kippmiami model keeps its current output columns and order; only the
`FROM`/filter changes. Add a `unit_tests` block to each `properties/*.yml`.

### Task 5: demographics diff (req 2)

**Files:**

- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__demographics.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__demographics.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__demographics")`
  (8400-prefixed `stdt_id`), `ref("stg_focus__students")`,
  `ref("int_focus__students__pivot")`.
- Produces: same demographics columns; rows only for unmatched or changed
  students.

- [ ] **Step 1: Write the unit test** in the `properties` yml with three
      `source('kipptaf_extracts', 'rpt_focus__demographics')` desired rows and
      mocked Focus state:
  - `8400000001` not in Focus -> kept.
  - `8400000002` matching Focus on every populated field -> dropped.
  - `8400000003` matching the Focus student but with a changed `first_name` ->
    kept.

  Mock `ref('stg_focus__students')` and `ref('int_focus__students__pivot')` with
  rows for `student_id` `8400000002`/`8400000003`. Assert the output `stdt_id`
  set is `{8400000001, 8400000003}`.

- [ ] **Step 2: Run to confirm fail** (model has no filter yet).

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
    --select rpt_focus__demographics \
    --project-dir <worktree>/src/dbt/kippmiami --target dev
  ```

- [ ] **Step 3: Rewrite the model** keeping the existing output column list:

  ```sql
  with
      desired as (
          select *
          from {{ source("kipptaf_extracts", "rpt_focus__demographics") }}
      ),

      focus_state as (
          select
              s.student_id,
              s.first_name,
              s.last_name,
              s.middle_name,
              s.student_e_mail_address,
              format_date('%Y%m%d', s.birthdate) as dt_birth_focus,
              regexp_extract(p.sex_label, r'\[(.+)\]') as gender_focus,
              p.language_label,
              case p.ethnicity_hispanic_or_latino_label
                  when 'Yes' then 'Y'
                  when 'No' then 'N'
              end as ethnic_hl_focus,
              case p.race_american_indian_or_alaska_native_label
                  when 'Yes' then 'Y'
              end as race_am_ind_ak_nat_focus,
              case p.race_asian_label when 'Yes' then 'Y' end as race_asian_focus,
              case p.race_black_or_african_american_label
                  when 'Yes' then 'Y'
              end as race_black_focus,
              case p.race_native_hawaiian_or_other_pacific_islander_label
                  when 'Yes' then 'Y'
              end as race_nat_haw_pac_isl_focus,
              case p.race_white_label when 'Yes' then 'Y' end as race_white_focus,
          from {{ ref("stg_focus__students") }} as s
          left join
              {{ ref("int_focus__students__pivot") }} as p
              on s.student_id = p.student_id
      ),

      diffed as (
          select d.*, f.student_id as focus_student_id,
          from desired as d
          left join focus_state as f on d.stdt_id = f.student_id
          where
              f.student_id is null
              or (d.first_name is not null and d.first_name is distinct from f.first_name)
              or (d.last_name is not null and d.last_name is distinct from f.last_name)
              or (d.middle_name is not null and d.middle_name is distinct from f.middle_name)
              or (d.stdt_email is not null and d.stdt_email is distinct from f.student_e_mail_address)
              or (d.dt_birth is not null and d.dt_birth is distinct from f.dt_birth_focus)
              or (d.gender is not null and d.gender is distinct from f.gender_focus)
              or (d.lang is not null and d.lang is distinct from f.language_label)
              or (d.ethnic_hl is not null and d.ethnic_hl is distinct from f.ethnic_hl_focus)
              or (d.race_am_ind_ak_nat is not null and d.race_am_ind_ak_nat is distinct from f.race_am_ind_ak_nat_focus)
              or (d.race_asian is not null and d.race_asian is distinct from f.race_asian_focus)
              or (d.race_black is not null and d.race_black is distinct from f.race_black_focus)
              or (d.race_nat_haw_pac_isl is not null and d.race_nat_haw_pac_isl is distinct from f.race_nat_haw_pac_isl_focus)
              or (d.race_white is not null and d.race_white is distinct from f.race_white_focus)
      )

  select
      stdt_id,
      last_name,
      first_name,
      -- ...the full existing demographics column list, in order...
      lcp_cont_stdt,
  from diffed
  ```

  Keep the **exact** existing column list in the final `select` (copy it from
  the current model). Long predicate lines exceed 88 chars — the SQL fluff line
  length applies; reformat each disjunct onto wrapped lines or extract the
  normalized comparison into the `desired`/`focus_state` CTEs so the `where`
  reads plain columns. Prefer pre-computing both sides in CTEs.

- [ ] **Step 4: Run unit test to pass** (command from Step 2). Expected: PASS.

- [ ] **Step 5: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): diff focus demographics against current state (#4279)"
  ```

### Task 6: enrollment diff + drop-code decode + code import-once (req 3 and 4)

**Files:**

- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__student_enrollment")` (has
  `state_withdraw_label`, no `drop_code`),
  `ref("stg_focus__student_enrollment")`,
  `ref("stg_focus__student_enrollment_codes")`.
- Produces: the existing enrollment column list with `drop_code` (decoded) in
  its original position; codes nulled when Focus already has them.

- [ ] **Step 1: Write the unit test** with mocked desired rows + a mocked
      `ref('stg_focus__student_enrollment')`:
  - new student/enrollment -> kept, `enrollment_code` (E05/E01) and decoded
    `drop_code` populated.
  - matched on `(student_id, start_date)`, no non-code change, Focus already has
    `enrollment_code` -> dropped (no row).
  - matched, `grade_id` changed, Focus has `enrollment_code` and null
    `drop_code` -> kept, `enrollment_code` nulled, `drop_code` decoded+emitted.
    Mock `ref('stg_focus__student_enrollment_codes')` with a `Drop` row whose
    `title` equals the mocked `state_withdraw_label` and `short_name` `W02`.

- [ ] **Step 2: Run to confirm fail** (command pattern from Task 5 Step 2,
      selecting `rpt_focus__student_enrollment`).

- [ ] **Step 3: Rewrite the model.**

  ```sql
  with
      desired as (
          select *
          from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }}
      ),

      decoded as (
          select
              d.*,
              dc.short_name as drop_code_decoded,
          from desired as d
          left join
              {{ ref("stg_focus__student_enrollment_codes") }} as dc
              on d.state_withdraw_label = dc.title
              and dc.type = 'Drop'
      ),

      matched as (
          select
              e.*,
              fe.start_date as focus_start_date,
              fe.enrollment_code as focus_enrollment_code,
              fe.drop_code as focus_drop_code,
              fe.grade_id as focus_grade_id,
              fe.syear as focus_syear,
              fe.school_id as focus_school_id,
              fe.end_date as focus_end_date,
          from decoded as e
          left join
              {{ ref("stg_focus__student_enrollment") }} as fe
              on e.student_id = fe.student_id
              and e.start_date = format_date('%Y%m%d', fe.start_date)
          where
              fe.start_date is null
              or (e.grade_id is not null and e.grade_id is distinct from fe.grade_id)
              or (e.syear is not null and e.syear is distinct from fe.syear)
              or (e.school_id is not null and e.school_id is distinct from fe.school_id)
              or (e.end_date is not null and e.end_date is distinct from format_date('%Y%m%d', fe.end_date))
      )

  select
      syear,
      school_id,
      student_id,
      grade_id,
      start_date,
      if(
          focus_enrollment_code is null, enrollment_code, cast(null as string)
      ) as enrollment_code,
      end_date,
      if(
          focus_drop_code is null, drop_code_decoded, cast(null as string)
      ) as drop_code,
      -- ...the rest of the existing enrollment column list, in order...
      fl_days_absent,
  from matched
  ```

  Compare `syear`/`school_id`/`grade_id` types carefully (cast both sides to a
  common type if the Focus columns are ints and the export emits strings). Keep
  the **exact** existing output column list/order. Reformat long `where`
  disjuncts to satisfy the 88-char limit (pre-compute normalized columns in CTEs
  if cleaner).

- [ ] **Step 4: Run unit test to pass.** Expected: PASS.

- [ ] **Step 5: Verify school-id domain alignment** (spec open question 2):

  ```sql
  select countif(e.school_id = cast(fe.school_id as string)) aligned, count(*) n
  from `teamster-332318`.kipptaf_extracts.rpt_focus__student_enrollment e
  join `teamster-332318`.kippmiami_focus.stg_focus__student_enrollment fe
    on concat('8400', e.student_id) = cast(fe.student_id as string)
    and e.start_date = format_date('%Y%m%d', fe.start_date)
  ```

  (Adjust for the prefix state of the prod table.) If `school_id` domains
  differ, drop `school_id` from the diff predicate and note it; do not let a
  domain mismatch force every matched row to re-send.

- [ ] **Step 6: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): diff focus enrollment + decode drop code + import-once codes (#4279)"
  ```

### Task 7: addresses import-once (req 1)

**Files:**

- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__addresses.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__addresses.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__addresses")`,
  `ref("stg_focus__students_join_address")`.
- Produces: address columns; rows only for students with no Focus address link.

- [ ] **Step 1: Write the unit test** — one desired student with a matching
      `stg_focus__students_join_address` row (dropped) and one without (kept).
      Assert only the unmatched `student_id` survives.

- [ ] **Step 2: Run to confirm fail.**

- [ ] **Step 3: Rewrite the model** as an anti-join, keeping the existing column
      list:

  ```sql
  with
      desired as (
          select * from {{ source("kipptaf_extracts", "rpt_focus__addresses") }}
      ),

      already_in_focus as (
          select distinct cast(student_id as string) as student_id,
          from {{ ref("stg_focus__students_join_address") }}
      )

  select
      d.student_id,
      d.address,
      -- ...existing addresses column list, in order...
      d.mail_state,
  from desired as d
  left join already_in_focus as f on d.student_id = f.student_id
  where f.student_id is null
  ```

- [ ] **Step 4: Run unit test to pass.**

- [ ] **Step 5: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): import focus addresses once (#4279)"
  ```

### Task 8: contacts import-once (req 1)

**Files:**

- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__contacts")`,
  `ref("stg_focus__students_join_people")`.
- Produces: contacts columns; rows only for students with no Focus people link.

- [ ] **Step 1: Write the unit test** — desired contact rows for two students,
      one with a `stg_focus__students_join_people` row (all that student's
      contact rows dropped) and one without (kept).

- [ ] **Step 2: Run to confirm fail.**

- [ ] **Step 3: Rewrite the model** as a per-student anti-join (same shape as
      Task 7 Step 3, sourcing `rpt_focus__contacts` and
      `stg_focus__students_join_people`, keeping the full contacts column
      list/order).

- [ ] **Step 4: Run unit test to pass.**

- [ ] **Step 5: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): import focus contacts once (#4279)"
  ```

### Task 9: linked students import-once (req 1)

**Files:**

- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__linked_students.sql`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_focus__linked_students")`,
  `ref("stg_focus__students_join_students")`.
- Produces: `(primary_student_id, secondary_student_id)` pairs not already
  linked in Focus.

- [ ] **Step 1: Write the unit test** — two desired pairs, one already present
      in `stg_focus__students_join_students` (dropped) and one not (kept). The
      existing pair-existence test must match regardless of pair direction
      (normalize both sides with `least`/`greatest` before comparing).

- [ ] **Step 2: Run to confirm fail.**

- [ ] **Step 3: Rewrite the model** as an anti-join on the normalized pair:

  ```sql
  with
      desired as (
          select *
          from {{ source("kipptaf_extracts", "rpt_focus__linked_students") }}
      ),

      focus_pairs as (
          select distinct
              least(cast(student_id as string), cast(linked_student_id as string))
                  as primary_student_id,
              greatest(cast(student_id as string), cast(linked_student_id as string))
                  as secondary_student_id,
          from {{ ref("stg_focus__students_join_students") }}
      )

  select d.primary_student_id, d.secondary_student_id,
  from desired as d
  left join
      focus_pairs as f
      on d.primary_student_id = f.primary_student_id
      and d.secondary_student_id = f.secondary_student_id
  where f.primary_student_id is null
  ```

  (Adjust `linked_student_id` to the real second-id column name from Task 3.)

- [ ] **Step 4: Run unit test to pass.**

- [ ] **Step 5: Commit.**

  ```bash
  git -C <worktree> add -u
  git -C <worktree> commit -m "feat(finalsite): import focus linked students once (#4279)"
  ```

---

## Phase 4 — validation and PR

### Task 10: full validation and pull request

**Files:** none (verification) unless a fix is needed.

- [ ] **Step 1: Parse both projects.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --project-dir <worktree>/src/dbt/kipptaf
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --project-dir <worktree>/src/dbt/kippmiami
  ```

- [ ] **Step 2: Run every focus unit test.**

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test \
    --select "rpt_focus__* stg_focus__students_join_*" \
    --project-dir <worktree>/src/dbt/kippmiami --target dev \
    --defer --state <worktree>/src/dbt/kippmiami/target/prod
  ```

  Also run the kipptaf unit tests
  (`--select rpt_focus__* --project-dir <worktree>/src/dbt/kipptaf`). Expected:
  all PASS.

- [ ] **Step 3: Build the kippmiami extracts end to end** (defer to prod):

  ```bash
  DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt build \
    --select "rpt_focus__*" \
    --project-dir <worktree>/src/dbt/kippmiami --target dev \
    --defer --state <worktree>/src/dbt/kippmiami/target/prod
  ```

  (Req 1 models build only once Task 3 made their sources exist; if deferred,
  build the other four and note req 1 pending.)

- [ ] **Step 4: Sanity-check row reduction** in BigQuery — confirm each extract
      now emits fewer rows than the desired-state count for already-matched
      students, and that unmatched students still appear.

- [ ] **Step 5: Trunk-check every changed file** from inside the worktree.

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force <changed .sql/.yml/.md>
  ```

- [ ] **Step 6: Push and open the PR.** Push the branch (hand `git push` to the
      user if the classifier blocks it), then open a PR with the
      `.github/pull_request_template.md` body and `Closes #4279` (which chains
      `Closes #4208`). Flag that the kipptaf source change (8400 prefix +
      `state_withdraw_label` rename) must materialize in prod before kippmiami
      CI can read it (two-PR / clone-seed consideration per
      `src/dbt/CLAUDE.md`).

---

## Self-review notes

- Spec coverage: req 1 (Tasks 3,4,7,8,9), req 2 (Task 5), req 3 (Task 6), req 4
  (Tasks 2,6), req 5 (Task 1). All covered.
- Cross-project ordering: Task 2 renames a kipptaf output column (`drop_code` ->
  `state_withdraw_label`) that kippmiami Task 6 consumes; kippmiami CI reads the
  `zz_stg`/prod kipptaf copy, so the kipptaf change must reach prod before
  kippmiami CI passes (Task 10 Step 6).
- Req 1 is gated on Task 3; if the Focus linkage tables cannot be materialized,
  Tasks 4/7/8/9 stay un-merged and reqs 2-5 ship independently.
