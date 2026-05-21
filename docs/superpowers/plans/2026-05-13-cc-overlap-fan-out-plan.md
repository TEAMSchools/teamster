# Collapse CC Overlap Fan-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop the misleading `#3633` `qualify` tiebreakers across three mart
facts, replace the underlying fan-out cause with a semantic filter, and surface
the residual PS source anomaly with an upstream warn test.

**Architecture:** No new models. Edit one upstream staging YAML to add a
warn-level uniqueness test, edit three mart SQL files to remove `qualify` blocks
(with a `where not is_dropped_section` filter added to
`fct_grades_assignments`), downgrade the mart PK test severity, and update
CLAUDE.md guidance. Driver of the fan-out (PowerSchool double-writing `cc` rows)
is tracked separately for Ops cleanup as `#3915`.

**Tech Stack:** dbt 1.11+ (BigQuery), trunk (sqlfluff + yamllint), dbt_utils.

**Worktree:**
`/workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out`

**Branch:** `cbini/fix/claude-collapse-cc-overlap-fan-out`

**Reference spec:**
[docs/superpowers/specs/2026-05-13-cc-overlap-fan-out-design.md](../specs/2026-05-13-cc-overlap-fan-out-design.md)

---

## File Map

**Create:** none.

**Modify:**

- `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml` —
  add warn test.
- `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql` — add
  dropped-section filter, drop `qualify`.
- `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql` — drop
  `qualify`.
- `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql` — drop
  `qualify`.
- `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml` —
  downgrade PK test severity.
- `src/dbt/CLAUDE.md` — rewrite "Enrollment join fan-out" section (requires user
  approval before edit).

All paths below are relative to the worktree root. Run every dbt command with
`--project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out/src/dbt/<project>`
and every git command with
`git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out`.
Bare `git` from the main repo silently commits to `main`.

---

## Task 1: Discover the existing uniqueness test on `stg_powerschool__cc`

The new warn test must coexist with whatever PK uniqueness test already exists.
The spec hypothesized it's on `id` or `dcid` — verify before editing.

**Files:**

- Read:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml`

- [ ] **Step 1: Read the existing properties YAML**

```bash
sed -n '1,60p' /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out/src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml
```

Expected: a `models:` entry for `stg_powerschool__cc` with `data_tests:` and/or
`columns:` blocks. Note where the PK uniqueness test lives (model-level
`dbt_utils.unique_combination_of_columns` vs. per-column `unique`). Record:

- Model-level `data_tests:` block exists? (Y/N — if N, the new test creates
  one.)
- Existing PK column(s).
- Indentation style (spaces, list dashes).

No file changes in this task — discovery only.

---

## Task 2: Add upstream warn test on `stg_powerschool__cc`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml`

- [ ] **Step 1: Add the warn-level uniqueness test**

If a model-level `data_tests:` block already exists, append the new test entry
below the existing items. If it does not, create one above `columns:`.

Add this entry (preserve the file's existing indentation; below uses 4-space
nesting under `- name:`):

```yaml
- dbt_utils.unique_combination_of_columns:
    arguments:
      combination_of_columns:
        - studentid
        - sectionid
        - dateleft
    config:
      severity: warn
```

Constraints from `src/dbt/CLAUDE.md`:

- Generic tests in dbt 1.11+ require `arguments:` nesting (the flat form
  triggers a deprecation warning).
- Staging tests must set `config: severity: error` per project rule **unless**
  the spec explicitly downgrades. This is the documented exception — keep
  `severity: warn`.
- Multi-column tests go at model-level in `data_tests:` ABOVE `columns:`.

- [ ] **Step 2: Parse to confirm syntax**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt parse --project-dir src/dbt/kipptaf --no-partial-parse
```

Expected: `Encountered no errors`. If a YAML parse error fires, fix indentation
and re-run.

- [ ] **Step 3: Run the new test to confirm count**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt test --project-dir src/dbt/kipptaf \
    --select 'stg_powerschool__cc,test_type:dbt_utils.unique_combination_of_columns'
```

Expected: 1 test result, status `warn`, message reporting ~24 failing rows. If
`error`, the severity override didn't apply — re-check Step 1 indentation.

- [ ] **Step 4: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
test(powerschool): add warn-level cc dup test on (studentid, sectionid, dateleft)

Surfaces 24 historical PS double-write groups. Refs #3900, refs #3915.

EOF
)"
```

---

## Task 3: Filter dropped sections + drop `qualify` in `fct_grades_assignments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`

- [ ] **Step 1: Add the dropped-section filter to the `course_enrollments` CTE**

Read the current file:

```bash
sed -n '1,20p' /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out/src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql
```

The current CTE (lines 2–17) ends with
`from {{ ref("base_powerschool__course_enrollments") }}` and has no `where`
clause. Add a `where not is_dropped_section` line after the `from` line. Result:

```sql
course_enrollments as (
    select
        _dbt_source_relation,
        _dbt_source_project,
        cc_studentid,
        cc_academic_year,
        cc_schoolid,
        cc_dcid,
        cc_dateenrolled,
        cc_dateleft,
        sections_dcid,
        students_dcid,
        students_student_number,
        region,
    from {{ ref("base_powerschool__course_enrollments") }}
    where not is_dropped_section
),
```

- [ ] **Step 2: Remove the `qualify` block at lines 127–134**

Delete these lines:

```sql

-- TODO: overlapping CC records at same section cause join fan-out;
-- qualify picks latest cc_dateenrolled and entrydate (#3633)
qualify
    row_number() over (
        partition by asg.assignmentsectionid, asg._dbt_source_relation, ce.students_dcid
        order by ce.cc_dateenrolled desc, enr.entrydate desc
    )
    = 1
```

The file should end after the `left join reporting_terms ...` clause and its
`on` conditions. No new comment in place of the removed block — the upstream
warn test is the new home for that context.

- [ ] **Step 3: Compile to confirm syntax**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt compile --project-dir src/dbt/kipptaf \
    --select fct_grades_assignments
```

Expected: `Encountered no errors`. Compiled SQL appears at
`src/dbt/kipptaf/target/compiled/.../fct_grades_assignments.sql` — skim it to
confirm the `where not is_dropped_section` lands inside the CTE and the
`qualify` is gone.

- [ ] **Step 4: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
fix(dbt): filter dropped sections + drop qualify in fct_grades_assignments

Semantic fix: assignments shouldn't anchor on dropped enrollments.
Drops 6,523 of 6,594 fan-out rows. Residual ~71 from historical PS
source duplicates flagged by upstream warn test. Refs #3900, refs #3890.

EOF
)"
```

---

## Task 4: Drop `qualify` in `fct_student_attendance_daily`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`

- [ ] **Step 1: Remove the `qualify` block at lines 99–106**

Read the tail of the file:

```bash
sed -n '90,107p' /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out/src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql
```

Delete this block (and the trailing blank line that precedes it):

```sql

-- TODO: overlapping enrollment records at same school cause join
-- fan-out; qualify picks latest entrydate (#3633)
qualify
    row_number() over (
        partition by ada.student_number, ada._dbt_source_relation, ada.calendardate
        order by enr.entrydate desc
    )
    = 1
```

The file should end after the
`left join terms as t ... and ada.academic_year = t.academic_year` clause.

- [ ] **Step 2: Compile to confirm syntax**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt compile --project-dir src/dbt/kipptaf \
    --select fct_student_attendance_daily
```

Expected: `Encountered no errors`.

- [ ] **Step 3: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
fix(dbt): drop no-op qualify from fct_student_attendance_daily

Verified 0 fan-out at the enrollment join site. Refs #3900, refs #3890.

EOF
)"
```

---

## Task 5: Drop `qualify` in `fct_student_attendance_streaks`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql`

- [ ] **Step 1: Remove the `qualify` block at lines 44–46 (approximate; confirm
      by reading)**

Read the relevant lines:

```bash
sed -n '35,55p' /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out/src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql
```

Delete the `qualify` block and its `-- TODO ... (#3633)` comment lines,
mirroring Task 4's pattern.

- [ ] **Step 2: Compile to confirm syntax**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt compile --project-dir src/dbt/kipptaf \
    --select fct_student_attendance_streaks
```

Expected: `Encountered no errors`.

- [ ] **Step 3: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
fix(dbt): drop no-op qualify from fct_student_attendance_streaks

Verified 0 fan-out at the enrollment join site. Refs #3900, refs #3890.

EOF
)"
```

---

## Task 6: Downgrade `fct_grades_assignments` PK uniqueness test to warn

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml`

The existing test sits at lines 20–22 of the YAML:

```yaml
data_tests:
  - unique
  - not_null
```

We want the `unique` test to emit warn (the bounded historical residual is
expected to violate it). The `not_null` test stays at default (error).

- [ ] **Step 1: Replace the bare `unique` entry with a configured form**

Change those three lines to:

```yaml
data_tests:
  # TODO(#3915): remove the warn override once PS source cleanup completes;
  # the residual ~71 dup rows are historical PS double-writes (frozen corpus,
  # AY ≤ 2023). When #3915 closes, drop this block and restore bare `- unique`.
  - unique:
      config:
        severity: warn
  - not_null
```

- [ ] **Step 2: Parse to confirm syntax**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt parse --project-dir src/dbt/kipptaf --no-partial-parse
```

Expected: `Encountered no errors`.

- [ ] **Step 3: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
test(dbt): warn grades_assignment_key uniqueness pending PS cleanup

Bounded historical residual from PS double-writes. TODO ties the override
to #3915; severity returns to error when source cleanup completes.

EOF
)"
```

---

## Task 7: Verify the dbt build outcomes

This task captures the expected test counts for the PR body.

**Files:** none modified — read-only verification.

- [ ] **Step 1: Build the four touched models with their tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt build --project-dir src/dbt/kipptaf \
    --select stg_powerschool__cc fct_grades_assignments fct_student_attendance_daily fct_student_attendance_streaks
```

Expected:

- All four model materializations: `PASS` (or `SKIP` for stg_powerschool\_\_cc
  if it's deferred — fine).
- `fct_grades_assignments.grades_assignment_key.unique`: `WARN` with ~71 failing
  rows. Record the exact count for the PR body.
- `fct_grades_assignments.grades_assignment_key.not_null`: `PASS`.
- `fct_student_attendance_daily.*` PK test: `PASS`.
- `fct_student_attendance_streaks.*` PK test: `PASS`.
- `stg_powerschool__cc.dbt_utils.unique_combination_of_columns`: `WARN` with ~24
  failing groups.

If `fct_grades_assignments.grades_assignment_key.unique` reports `PASS` (0
failing rows), the dropped-section filter combined with whatever else is
upstream eliminated all residuals — note this in the PR body and consider
whether the warn TODO should be reverted to bare `unique`. If it reports `ERROR`
(test ran at error severity), the YAML change in Task 6 didn't take — re-check.

- [ ] **Step 2: Capture exact row counts for PR**

Record:

- `fct_grades_assignments` unique test failure count: \_\_\_ rows.
- `stg_powerschool__cc` unique_combination_of_columns failure count: \_\_\_
  rows.

These go in the PR body.

- [ ] **Step 3: Row-count diff for the two attendance models**

The two attendance qualifies were verified as no-ops; this step confirms it
survives the actual build.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt show --project-dir src/dbt/kipptaf \
    --inline "select count(*) as n from {{ ref('fct_student_attendance_daily') }}"
```

Compare against prod row count via BigQuery MCP:

```sql
SELECT count(*) AS n FROM `teamster-332318.kipptaf.fct_student_attendance_daily`
```

Expected: equal. Repeat for `fct_student_attendance_streaks`. If unequal, the
qualify was not a no-op — file a regression issue and stop.

- [ ] **Step 4: Row-count delta for `fct_grades_assignments`**

The dropped-section filter is expected to drop a small number of rows (grade
rows whose due_date fell during a dropped-section window).

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  uv run dbt show --project-dir src/dbt/kipptaf \
    --inline "select count(*) as n from {{ ref('fct_grades_assignments') }}"
```

Compare against prod. Record the delta for the PR body.

No commit in this task — verification only.

---

## Task 8: Update `src/dbt/CLAUDE.md` — "Enrollment join fan-out" section

CLAUDE.md edits require **explicit user approval** before applying per the
project conventions. This task pauses.

**Files:**

- Modify: `src/dbt/CLAUDE.md`

- [ ] **Step 1: Present the proposed replacement to the user as a quote block**

Show this exact replacement, naming the target lines (currently 355–362):

> Replace the existing "Enrollment join fan-out (known upstream issue)" block in
> `src/dbt/CLAUDE.md` with:
>
> ```markdown
> ### Enrollment join fan-out (PowerSchool source-data anomaly)
>
> `base_powerschool__course_enrollments` carries a small frozen corpus of
> historical PowerSchool double-writes — multiple `cc` records for the same
> `(student, section, dateleft)`. Surfaced by the warn-level
> `dbt_utils.unique_combination_of_columns(studentid, sectionid, dateleft)` test
> on `stg_powerschool__cc`. Source cleanup tracked in
> [#3915](https://github.com/TEAMSchools/teamster/issues/3915); spec context in
> [#3900](https://github.com/TEAMSchools/teamster/issues/3900). No active-year
> incidents.
>
> When date-range joining `base_powerschool__course_enrollments`, filter
> `is_dropped_section` first — every observed overlap involves at least one
> dropped row. After that filter, residual fan-out is bounded (single-digit
> students, all AY ≤ 2023).
>
> Do not add defensive dedupes (`qualify row_number() = 1` or
> `dbt_utils.deduplicate()`) to mask residual source-data duplicates. Affected
> mart PK uniqueness tests may be downgraded to `severity: warn` with a TODO
> referencing `#3915` so the override comes off when source cleanup completes.
> Example: `fct_grades_assignments.grades_assignment_key`.
>
> `base_powerschool__student_enrollments` date-range joins do not currently need
> any tiebreaker — 0 overlapping ranges observed on 2026-05-13.
> ```

- [ ] **Step 2: PAUSE — wait for user approval before applying**

Do not edit the file before user says approved. If the user requests
adjustments, present revised quote block.

- [ ] **Step 3: Apply the approved replacement**

Use the Edit tool to replace lines 355–362 of `src/dbt/CLAUDE.md` (the existing
"Enrollment join fan-out (known upstream issue)" block) with the approved text
from Step 1.

- [ ] **Step 4: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out add -u && \
  git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out commit -m "$(cat <<'EOF'
docs(claude-md): rewrite enrollment join fan-out guidance for #3900

Replaces stale #3633 reference. Names the actual anomaly (PS double-write
of cc records) and the correct mitigation pattern (filter dropped sections;
warn-downgrade mart PK tests with TODO to #3915).

EOF
)"
```

---

## Task 9: Project board hygiene

This task pauses for user input on field values.

**Files:** none — GitHub project mutations.

- [ ] **Step 1: Check whether `#3900` is already on project board `#4`**

```bash
GITHUB_TOKEN= gh project item-list 4 --owner TEAMSchools --format json --limit 200 \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([i for i in d['items'] if i.get('content',{}).get('number') in (3900, 3915)])"
```

Expected: each entry shows whether the issue is on the board and current field
values.

- [ ] **Step 2: PAUSE — ask user for Tier / PR batch / Driver values**

For `#3915` (and `#3900` if not already set), ask the user what to use for:

- `Tier` (typical values: e.g., `Tier 1`, `Tier 2`, `Tier 3` — let the user
  enumerate)
- `PR batch` (free text or batch label)
- `Driver` (user / role)

- [ ] **Step 3: Add `#3915` to the board and set fields**

Per the root CLAUDE.md cheat sheet:

```bash
# Add to board
GITHUB_TOKEN= gh project item-add 4 --owner TEAMSchools \
  --url https://github.com/TEAMSchools/teamster/issues/3915
```

Then `gh project item-edit ...` once per field (`Tier`, `PR batch`, `Driver`)
using the IDs surfaced by `gh project field-list` (see root CLAUDE.md). Verify
each via `gh api graphql` since `item-edit` produces no output on success.

- [ ] **Step 4: If `#3900` isn't on the board, add it and set fields the same
      way**

- [ ] **Step 5: No commit — these are GitHub project mutations, not file
      changes.**

---

## Task 10: Push, marts pre-merge checklist, open PR

**Files:** none — git + GitHub workflow.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out push
```

- [ ] **Step 2: Trunk lint pre-push gate**

The push hook runs `trunk check`. If it fails on any of the touched files, fix
locally and re-push:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml \
  src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql \
  src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql \
  src/dbt/kipptaf/models/marts/facts/fct_student_attendance_streaks.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml \
  src/dbt/CLAUDE.md
```

- [ ] **Step 3: Marts pre-merge checklist**

Per
[src/dbt/kipptaf/models/marts/CLAUDE.md](../../src/dbt/kipptaf/models/marts/CLAUDE.md)
"Pre-merge checklist (marts PRs)":

1. **Diamond-path scan** on the three touched facts. Expected clean — this PR
   removes a `qualify`, adds a `where`, and adjusts a test severity. No new FKs.
2. **Column-naming rubric R1–R10 scan** on the three touched facts. Expected
   clean — no column renames or additions.
3. **CI-warning triage** via
   `mcp__dbt__get_job_run_error(run_id=<latest>, warning_only=True)` on the PR's
   CI run. For each warning:
   1. Identify the model and test.
   2. Search [project board #4](https://github.com/orgs/TEAMSchools/projects/4)
      by model name and FK target.
   3. **Match found:** comment on the existing issue with current count + change
      from prior observation.
   4. **No match:** file a new issue per the "Filing follow-up issues from marts
      work" procedure — bucket warning rows (by region / source / test type) in
      the body, then add to board #4 with `Tier` / `PR batch` / `Driver` set.
4. **Board scan for incidental resolutions** — re-check the list pulled in Task
   9 Step 1 to confirm `#3901`'s `#3633` portion remains the only
   partial-resolution item; this PR was already scanned during spec authoring.

- [ ] **Step 4: Open the PR**

````bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-collapse-cc-overlap-fan-out && \
  gh pr create --base main --head cbini/fix/claude-collapse-cc-overlap-fan-out \
    --title "fix(dbt): collapse cc overlap fan-out in marts (#3900)" \
    --body "$(cat <<'EOF'
## Summary

- Replaces three misleading `qualify`/`#3633` tiebreakers in `fct_grades_assignments`, `fct_student_attendance_daily`, `fct_student_attendance_streaks` with the semantic fix: filter `is_dropped_section` upstream of the join (gradebook assignments shouldn't anchor on dropped enrollments).
- Adds a warn-level `dbt_utils.unique_combination_of_columns(studentid, sectionid, dateleft)` test to `stg_powerschool__cc` surfacing the PowerSchool source anomaly (24 historical double-write groups, frozen corpus, AY ≤ 2023). Source cleanup tracked separately in #3915.
- Downgrades `fct_grades_assignments.grades_assignment_key.unique` to `severity: warn` with a `TODO(#3915)`; severity returns to error when Ops finishes source cleanup.
- Rewrites the "Enrollment join fan-out" section of `src/dbt/CLAUDE.md`.

## Expected CI test outcomes

- `stg_powerschool__cc` warn-level uniqueness test: WARN, ~24 failing groups (historical PS bookkeeping). Stable count.
- `fct_grades_assignments.grades_assignment_key.unique`: WARN, ~71 failing rows (historical residual surviving the dropped-section filter).
- All other touched tests: PASS.

## Verification

Run from this worktree:

```bash
uv run dbt build --select stg_powerschool__cc fct_grades_assignments fct_student_attendance_daily fct_student_attendance_streaks --project-dir src/dbt/kipptaf
```

Row counts (this branch vs. prod):

- `fct_student_attendance_daily`: unchanged.
- `fct_student_attendance_streaks`: unchanged.
- `fct_grades_assignments`: drops by N rows (grade rows whose due-date fell in a
  dropped-section window).

Detailed design rationale:
[docs/superpowers/specs/2026-05-13-cc-overlap-fan-out-design.md](docs/superpowers/specs/2026-05-13-cc-overlap-fan-out-design.md)

## Issue links

- Closes #3900
- Refs #3915 (PS source cleanup tracker filed for Ops)
- Refs #3890 (umbrella: marts off legacy denormalized intermediates — this PR
  removes 3 of N `qualify row_number()` workarounds)
- Refs #3901 (partial: the `#3633` portion is fully addressed here; `#3629` /
  `#3635` portions in survey-domain models remain open)

## Test plan

- [ ] dbt CI passes (with the expected warn-level test failures noted above)
- [ ] Row counts in `fct_student_attendance_daily` and
      `fct_student_attendance_streaks` are unchanged vs. prod
- [ ] No regression in downstream models that read the three touched facts

🤖 Generated with [Claude Code](https://claude.com/claude-code) EOF )"

````

Backfill the actual row count and delta values into the body before posting if
Task 7 captured them.

- [ ] **Step 5: Post a comment on `#3901` noting partial resolution**

```bash
gh issue comment 3901 --body "The #3633 portion of this issue is being addressed in #<PR-number> (https://github.com/TEAMSchools/teamster/pull/<PR-number>). The #3629 and #3635 portions in survey-domain models remain open."
```

Replace `<PR-number>` with the actual PR number from Step 4 output.

- [ ] **Step 6: Done — return the PR URL.**

---

## Self-Review Notes

- All spec changes 1–11 are covered by tasks 1–10 (changes 9 and 11 are PR-body
  work, in Task 10).
- No placeholders.
- File paths are absolute or worktree-relative.
- Test outcomes have specific expected counts.
- User-pause gates: Task 8 Step 2 (CLAUDE.md approval), Task 9 Step 2 (board
  field values).
