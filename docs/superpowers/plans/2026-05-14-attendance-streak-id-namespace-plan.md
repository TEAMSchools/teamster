# Attendance Streak ID Namespace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate `streak_id` collisions in
`int_powerschool__attendance_streak` by namespacing the two surrogate-key UNION
branches, then restore the downstream mart uniqueness test to `severity: error`.

**Architecture:** Prepend a literal `'code'` / `'att'` discriminator to each of
the two `dbt_utils.generate_surrogate_key` calls in the gaps-and-islands SQL.
Add a `unique` test at the source-system intermediate layer; remove the
`severity: warn` override (added in #3916) from the kipptaf mart test.

**Tech Stack:** dbt (BigQuery), `dbt_utils.generate_surrogate_key`, sqlfluff,
trunk.

Worktree:
`/workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace`. All
paths below are repo-relative; prepend the worktree path for every command.

Spec:
[docs/superpowers/specs/2026-05-14-attendance-streak-id-namespace-design.md](../specs/2026-05-14-attendance-streak-id-namespace-design.md).
Issue: #3917. Follow-up to #3916.

---

## File Structure

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__attendance_streak.sql`
  — add `'code'` / `'att'` as the first input to each `generate_surrogate_key`
  call.
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__attendance_streak.yml`
  — add model `description`, missing column `description`s, and a `unique` test
  on `streak_id` at `severity: error`.
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_streaks.yml`
  — remove the `# TODO(#3917)` comment block and the `config: severity: warn`
  override on `student_attendance_streak_key.unique`.

No new files. No CLAUDE.md edits. No dbt model logic changes beyond the two
hash-input lists.

---

### Task 1: Pre-flight — confirm no other consumers hash on `streak_id`

**Files:**

- Read-only sweep of `src/dbt`.

- [ ] **Step 1: Search for downstream consumers of `streak_id` in
      `generate_surrogate_key`**

Run from the worktree root:

```bash
rg "generate_surrogate_key.*streak_id" src/dbt --type sql
```

Expected: exactly one match, in
`src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql`, of the
form `generate_surrogate_key(["st.streak_id", "st._dbt_source_relation"])`. If
any other match appears, STOP and surface to the user — those consumers will
hash-churn in lockstep and may have constraints the spec didn't account for.

- [ ] **Step 2: No commit (read-only)**

Proceed to Task 2.

---

### Task 2: Namespace the two surrogate-key branches

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__attendance_streak.sql:41-63`

- [ ] **Step 1: Edit the SQL — add `'code'` / `'att'` as the first hash input**

Replace the two `generate_surrogate_key` blocks in `streaks_long`. The full
target state of those two assignments is:

```sql
{{
    dbt_utils.generate_surrogate_key(
        [
            "'code'",
            "project_name",
            "studentid",
            "yearid",
            "att_code",
            "(membership_day_number - rn_student_year_code)",
        ]
    )
}} as code_streak_id,

{{
    dbt_utils.generate_surrogate_key(
        [
            "'att'",
            "project_name",
            "studentid",
            "yearid",
            "attendancevalue",
            "(membership_day_number - rn_student_year_attendancevalue)",
        ]
    )
}} as att_streak_id,
```

Use the Edit tool. Match the existing indentation and trailing-comma style of
the surrounding lines exactly. No other lines in this file change.

- [ ] **Step 2: Parse the powerschool source-system project to confirm no syntax
      regressions**

```bash
uv run dbt parse --project-dir src/dbt/kipppaterson
```

Expected: `Finished parse` with no errors. (We use a district project, not
`powerschool` standalone, because the source-system project is never run alone —
see `src/dbt/powerschool/CLAUDE.md`.)

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace add -u src/dbt/powerschool/models/sis/intermediate/int_powerschool__attendance_streak.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace commit -m "fix(dbt): namespace attendance_streak surrogate-key branches

Prepend 'code' / 'att' literal discriminators to the two
generate_surrogate_key calls in int_powerschool__attendance_streak so
the code branch and att branch never share hash space. Resolves
streak_id collisions surfaced by Paterson numeric att_code values.

Refs #3917."
```

---

### Task 3: Add intermediate `unique` test on `streak_id`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__attendance_streak.yml`

- [ ] **Step 1: Replace the properties yml in full**

The current file (read first to confirm) has only contract column declarations.
Replace with the following content, adding a model description, column
descriptions where missing, a per-column `unique` test on `streak_id`, and
`streak_id` moved to the top of the column list per the YAML convention "Columns
with per-column `data_tests:` should be sorted to the top of the `columns:`
list" (`src/dbt/CLAUDE.md`).

```yaml
models:
  - name: int_powerschool__attendance_streak
    description: >-
      One row per contiguous run of identical attendance per (studentid,
      yearid). Two streak types are unioned: by att_code and by attendancevalue.
      The surrogate key streak_id namespaces the two branches ('code' vs 'att')
      so they never collide.
    columns:
      - name: streak_id
        data_type: string
        description: >-
          Surrogate key for one contiguous streak. Namespaced by branch ('code'
          for att_code-grouped streaks, 'att' for attendancevalue-grouped
          streaks).
        data_tests:
          - unique:
              config:
                severity: error
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: yearid
        data_type: int64
        description:
          A number representing which year the term belongs to, such as 13 for
          2003-2004. The number is equal to the ID of the year term divided by
          100. Maintained in the Terms table. Required. Indexed.
      - name: att_code
        data_type: string
        description: >-
          For code-branch rows, the PowerSchool attendance code (e.g. 'A', 'T',
          'P'). For att-branch rows, the attendancevalue cast to string.
      - name: streak_start_date
        data_type: date
        description: First calendar date in the streak.
      - name: streak_end_date
        data_type: date
        description: Last calendar date in the streak.
      - name: streak_length_membership
        data_type: int64
        description:
          Number of membership days (membershipvalue = 1) in the streak.
      - name: streak_length_calendar
        data_type: int64
        description: >-
          Calendar-day span of the streak (end - start + 1), including any
          non-membership days within the run.
```

Use the Write tool (full overwrite is safer than multi-Edit for a small file).

- [ ] **Step 2: Parse to confirm the yml binds cleanly**

```bash
uv run dbt parse --project-dir src/dbt/kipppaterson --no-partial-parse
```

Expected: `Finished parse` with no errors and no deprecation warnings about the
new test syntax. `--no-partial-parse` ensures the new test definition is fully
bound (see `src/dbt/CLAUDE.md` "Singular-test description placement").

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace add -u src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__attendance_streak.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace commit -m "test(dbt): add streak_id unique test on int_powerschool__attendance_streak

Per src/dbt/CLAUDE.md intermediate-layer requirement (uniqueness test
required). Severity: error.

Refs #3917."
```

---

### Task 4: Restore mart test severity to `error`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_streaks.yml:18-25`

- [ ] **Step 1: Edit the mart properties yml**

Replace the existing `student_attendance_streak_key` `data_tests:` block.
Current state (lines 18–25):

```yaml
data_tests:
  # TODO(#3917): remove the warn override once int_powerschool__attendance_streak
  # streak_id collisions are fixed upstream. CI surfaces ~305 dup rows
  # (all Paterson, AY 2023-24). Restore to error when #3917 closes.
  - unique:
      config:
        severity: warn
  - not_null
```

Target state:

```yaml
data_tests:
  - unique
  - not_null
```

Use the Edit tool with the old_string covering the entire eight-line block above
and the new_string the three-line target. Do not touch other lines.

- [ ] **Step 2: Parse kipptaf to confirm the yml binds cleanly**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --no-partial-parse
```

Expected: `Finished parse` with no errors.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace add -u src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_streaks.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace commit -m "test(dbt): restore fct_student_attendance_streaks PK uniqueness to error

Removes the severity: warn override added in #3916 now that the upstream
streak_id collisions are fixed.

Closes #3917."
```

---

### Task 5: Verification build — Paterson (the failing district)

**Files:** none (build + test only).

- [ ] **Step 1: Build the intermediate model and its tests in Paterson**

```bash
uv run dbt build --project-dir src/dbt/kipppaterson --select int_powerschool__attendance_streak --target dev
```

Expected: model builds; `unique_int_powerschool__attendance_streak_streak_id`
test PASSES.

If the dev target is unavailable, fall back to
`--target defer --defer --state target/prod` per `src/dbt/CLAUDE.md` "Dev
`--defer` for unstaged externals". Refresh the prod manifest first if stale:

```bash
uv run dbt parse --project-dir src/dbt/kipppaterson --target prod --target-path target/prod
```

- [ ] **Step 2: If the test fails, STOP**

A failing uniqueness test means the namespace fix is incomplete — surface to the
user with the duplicate-group query from issue #3917 and do not proceed.

- [ ] **Step 3: No commit (verification only)**

---

### Task 6: Verification build — the other three districts

**Files:** none.

- [ ] **Step 1: Build the intermediate in Newark, Camden, Miami**

Run each in turn (serial, not parallel — concurrent dbt builds across districts
can exhaust BigQuery per-user quotas; see `src/dbt/CLAUDE.md`):

```bash
uv run dbt build --project-dir src/dbt/kippnewark --select int_powerschool__attendance_streak --target dev
uv run dbt build --project-dir src/dbt/kippcamden --select int_powerschool__attendance_streak --target dev
uv run dbt build --project-dir src/dbt/kippmiami --select int_powerschool__attendance_streak --target dev
```

Expected: all three model builds succeed and uniqueness test PASSES in each.

- [ ] **Step 2: No commit (verification only)**

---

### Task 7: Verification build — kipptaf mart

**Files:** none.

- [ ] **Step 1: Build the mart and run its tests**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --select fct_student_attendance_streaks --target dev
```

Expected: model builds;
`unique_fct_student_attendance_streaks_student_attendance_streak_key` test
PASSES at default severity (error). The `int_powerschool__attendance_streak`
union view in kipptaf will be rebuilt as a dependency of the mart's defer state;
this is intentional and free.

If kipptaf's source resolution fails on per-district prod relations (because we
built per-district to `dev`), pass `--defer --state target/prod` and let kipptaf
resolve from prod:

```bash
uv run dbt build --project-dir src/dbt/kipptaf --select fct_student_attendance_streaks --target defer --defer --state target/prod
```

- [ ] **Step 2: No commit (verification only)**

---

### Task 8: Push and open PR

**Files:** none (git only).

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-streak-id-namespace push -u origin cbini/fix/claude-streak-id-namespace
```

Pre-push trunk-check runs sqlfluff/yamllint on changed files. If it blocks, fix
the reported issue and re-push. Do not bypass `--no-verify`.

- [ ] **Step 2: Open the PR via `mcp__github__create_pull_request`**

Title: `fix(dbt): namespace attendance_streak surrogate-key branches`

Body: load `.github/pull_request_template.md` (Read tool) and fill in:

- Summary: 2 bullets — (1) what the bug was (cross-branch hash collision on
  numeric att_code), (2) the fix (namespace prefix in both
  `generate_surrogate_key` calls).
- Test plan checklist:
  - [ ] `uv run dbt build --select int_powerschool__attendance_streak` passes in
        each of the four district projects.
  - [ ] `uv run dbt build --select fct_student_attendance_streaks` passes in
        kipptaf with `unique` at `severity: error`.
  - [ ] dbt Cloud CI reports zero failing rows on both tests.
- Refs: `Closes #3917. Refs #3900, #3916.`

PR body must not contain PII (none of the values inspected during root-cause
analysis identify a specific student by anything beyond the internal numeric
`studentid`, which we will redact to `Student S` if cited at all).

- [ ] **Step 3: No commit (PR creation only)**

---

## Done when

- All four district `int_powerschool__attendance_streak` builds pass uniqueness
  at `severity: error`.
- `fct_student_attendance_streaks.student_attendance_streak_key.unique` passes
  at `severity: error` (no warn override).
- PR is open, CI is green, and the PR body closes #3917.
