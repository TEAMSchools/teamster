# Strip stale `#3633` references in dbt marts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove three stale `#3633` references from kipptaf dbt files (one
no-op SQL workaround, one comment refresh, one CLAUDE.md parenthetical), closing
#3901.

**Architecture:** Three independent, small file edits on branch
`cbini/chore/claude-strip-stale-3633-refs` (linked to #3901). Worktree at
`.worktrees/cbini-chore-claude-strip-stale-3633-refs/`. Task 1 deletes a
verified no-op `dbt_utils.deduplicate` CTE (BQ-verified 0 fan-out / 784,568 cc
rows). Task 2 rewrites a SQL comment to drop `#3633` and point at #4020 (the new
tracking issue for the load-bearing multi-stint dedup). Task 3 strips a
`(#3633)` parenthetical from `src/dbt/kipptaf/CLAUDE.md`. No tests are added —
the existing uniqueness test on `dim_student_section_enrollments` proves the
Task 1 change is safe.

**Tech Stack:** dbt 1.11+ / BigQuery / git worktree

---

## File Structure

All edits land in the existing worktree. No new files created.

- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
  (Task 1)
- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql`
  (Task 2)
- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/CLAUDE.md`
  (Task 3)

---

## Task 1: Remove no-op `dbt_utils.deduplicate` from `dim_student_section_enrollments`

**Files:**

- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql:16-67`

**Context:**

`course_enrollments_joined` is referenced only as a string by
`dbt_utils.deduplicate(relation="course_enrollments_joined")`. Once that call is
removed, the `# trunk-ignore(sqlfluff/ST03)` directive on line 16 is no longer
needed — `course_enrollments_joined` will be referenced directly by name in the
final `from` clause. BQ verification (2026-05-23): 0 fan-out across 784,568 cc
rows; the half-open interval join (`>= entrydate AND < exitdate`) already
prevents the overlap.

The `dbt_utils.deduplicate` macro and its surrounding TODO comment (lines 57-67)
collapse to a single-line `from course_enrollments_joined` reference. The final
`SELECT` (line 69 onwards) currently reads `from course_enrollments_deduped`;
that becomes `from course_enrollments_joined`.

- [ ] **Step 1: Read current file state**

Run via the Read tool:
`.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
(lines 14-114).

Expected current shape (lines 14-67):

```sql
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    course_enrollments_joined as (
        select
            cc._dbt_source_relation,
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.is_dropped_section,
            cc.is_dropped_course,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.name as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        left join
            student_enrollments as enr
            on cc.cc_studentid = enr.studentid
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_yearid = enr.yearid
            and cc.cc_dateenrolled >= enr.entrydate
            and cc.cc_dateenrolled < enr.exitdate
            and cc._dbt_source_project = enr._dbt_source_project
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on cc.cc_abs_termid = rt.powerschool_term_id
            and cc.sections_schoolid = rt.school_id
            and cc.region = rt.region
            and rt.`type` = 'RT'
    ),

    -- TODO: overlapping enrollment records at same school cause join
    -- fan-out; deduplicate picks latest entrydate (#3633)
    course_enrollments_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="course_enrollments_joined",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="enr_entrydate desc",
            )
        }}
    )

select
```

- [ ] **Step 2: Remove the `trunk-ignore` directive on line 16**

Use the Edit tool. The CTE will be referenced directly by name after this
change, so the ST03 suppression is dead.

`old_string`:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    course_enrollments_joined as (
```

`new_string`:

```sql
    course_enrollments_joined as (
```

- [ ] **Step 3: Remove the `course_enrollments_deduped` CTE and its TODO
      comment**

Use the Edit tool. Replace the closing `),` of `course_enrollments_joined` +
blank line + TODO + CTE block with just a closing `)` (no trailing comma — it's
now the last CTE) and a single blank line.

`old_string`:

```sql
    ),

    -- TODO: overlapping enrollment records at same school cause join
    -- fan-out; deduplicate picks latest entrydate (#3633)
    course_enrollments_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="course_enrollments_joined",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="enr_entrydate desc",
            )
        }}
    )

select
```

`new_string`:

```sql
    )

select
```

- [ ] **Step 4: Switch the final `from` reference**

Use the Edit tool.

`old_string`:

```sql
from course_enrollments_deduped
```

`new_string`:

```sql
from course_enrollments_joined
```

- [ ] **Step 5: Parse the project to confirm no syntax errors**

Run:

```bash
uv --directory /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf
```

Expected: `Update freshness…` / `Found N models…` summary with no errors.

- [ ] **Step 6: Build the model and run its uniqueness test against dev**

Run:

```bash
uv --directory /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs run dbt build --select dim_student_section_enrollments --project-dir /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf --defer --state src/dbt/kipptaf/target/prod
```

Expected: 1 view created (`dim_student_section_enrollments`), uniqueness test on
`student_section_enrollment_key` passes (`PASS`).

If the prod manifest is stale ("Could not find manifest" or column-missing
errors), regenerate first:

```bash
uv --directory /workspaces/teamster run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod
```

…then re-run Step 6.

- [ ] **Step 7: Compare row count against prod**

Run via `mcp__bigquery__execute_sql`:

```sql
select
  (select count(*) from `teamster-332318.kipptaf_dbt_dev_<user>.dim_student_section_enrollments`) as dev_n,
  (select count(*) from `teamster-332318.kipptaf_analytics.dim_student_section_enrollments`) as prod_n
```

Replace `<user>` with the dev schema suffix (check
`<repo-root>/.dbt/profiles.yml` if unsure). Expected: `dev_n == prod_n`. Any
delta invalidates the no-op claim — stop and report.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs add -u
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs commit -m "refactor(dbt): drop no-op dedup from dim_student_section_enrollments

The dbt_utils.deduplicate on (cc_dcid, _dbt_source_project) is a no-op:
0 fan-out across 784,568 cc rows (verified prod 2026-05-23). The
half-open interval join already prevents the overlap that the dedup
was meant to absorb. Drop the CTE and the now-dead trunk-ignore
suppression. Refs #3901."
```

---

## Task 2: Refresh TODO comment in `rpt_gsheets__school_metrics_extract`

**Files:**

- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql:442-447`

**Context:**

The `select distinct` in `section_school_context` is load-bearing (50 collapsed
rows / 9,335 raw, verified 2026-05-23) but the **cause** is multi-stint
enrollments at the same school, not the date-range overlap that #3633 originally
described. Drop `#3633`; point at the new tracking issue #4020.

- [ ] **Step 1: Rewrite the TODO comment**

Use the Edit tool.

`old_string`:

```sql
    -- TODO: #3633 — SELECT DISTINCT needed because
    -- base_powerschool__student_enrollments has genuinely overlapping date
    -- ranges for some students, producing duplicate (studentid, schoolid) rows.
    -- enroll_status filter intentionally omitted: a wider net is needed here so
    -- that transferred students' section records still resolve to a school/region
    -- even if their latest enrollment row has enroll_status != 0.
```

`new_string`:

```sql
    -- TODO: #4020 — int_extracts__student_enrollments carries one row per
    -- enrollment stint, so a student with a transfer-out + transfer-back at
    -- the same school produces duplicate (studentid, schoolid) rows. SELECT
    -- DISTINCT collapses them for the downstream join. enroll_status filter
    -- intentionally omitted: a wider net is needed so transferred students'
    -- section records still resolve to a school/region even when their latest
    -- enrollment row has enroll_status != 0.
```

- [ ] **Step 2: Parse the project**

Run:

```bash
uv --directory /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf
```

Expected: no errors. (Comment-only change; parse exists to catch fence
accidents.)

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs add -u
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs commit -m "docs(dbt): refresh stale #3633 TODO in rpt_gsheets__school_metrics_extract

The select distinct is load-bearing (50 collapsed rows verified prod
2026-05-23) but the cause is multi-stint enrollments at the same
school, not the date-range overlap #3633 described. Point at #4020,
which tracks migrating this consumer off select distinct. Refs #3901."
```

---

## Task 3: Strip `(#3633)` parenthetical from `src/dbt/kipptaf/CLAUDE.md`

**Files:**

- Modify:
  `.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt/kipptaf/CLAUDE.md:121`

**Context:**

The line currently reads
`Canonical-grain consumers (1 row per logical school) should use stg_google_sheets__people__locations instead (#3633).`
The surrounding paragraph already documents the canonical-grain guidance on its
own merits. The `(#3633)` parenthetical points at a closed issue
(`int_people__location_crosswalk` deduplication, completed 2026-04-22) and adds
no behavioral signal.

- [ ] **Step 1: Strip the `(#3633)` parenthetical**

Use the Edit tool.

`old_string`:

```text
Canonical-grain consumers (1 row per logical school) should use
`stg_google_sheets__people__locations` instead (#3633).
```

`new_string`:

```text
Canonical-grain consumers (1 row per logical school) should use
`stg_google_sheets__people__locations` instead.
```

- [ ] **Step 2: Confirm no other `#3633` refs remain in the worktree**

Run:

```bash
grep -rnE '#3633\b' /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs/src/dbt
```

Expected: no output (exit 1).

If grep returns any line, stop and report — it indicates a missed reference.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs add -u
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs commit -m "docs(claude-md): strip closed #3633 ref from kipptaf CLAUDE.md

#3633 (int_people__location_crosswalk dedup) closed completed
2026-04-22. The surrounding paragraph documents the canonical-grain
guidance without the issue ref. Refs #3901."
```

---

## Task 4: Push branch and open PR

**Files:**

- No file changes — this task only pushes and opens the PR via
  `mcp__github__create_pull_request`.

**Context:**

PR body follows `.github/pull_request_template.md`. Closes #3901; refs #4020 for
the spawned follow-up. Includes the BQ verification numbers from the spec so
reviewers can confirm the no-op claim without re-running the queries.

- [ ] **Step 1: Read the PR template**

Read
`.worktrees/cbini-chore-claude-strip-stale-3633-refs/.github/pull_request_template.md`
via the Read tool.

- [ ] **Step 2: Push the branch**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-chore-claude-strip-stale-3633-refs push
```

Expected: trunk pre-push hook runs sqlfluff/yamllint/markdownlint; push
succeeds.

If pre-push reports any issue, stop, fix, re-stage, create a new commit (do not
amend), and re-push.

- [ ] **Step 3: Open the PR**

Use `mcp__github__create_pull_request` with:

- owner: `TEAMSchools`
- repo: `teamster`
- base: `main`
- head: `cbini/chore/claude-strip-stale-3633-refs`
- title: `chore(dbt): strip stale #3633 refs from kipptaf marts + CLAUDE.md`
- body: (use the `.github/pull_request_template.md` shape, filling in)
  - Summary & Motivation: three bullets, one per task. Cite the no-op
    verification (0 fan-out / 784,568 cc rows) for Task 1 and the load-bearing
    finding (50 collapsed rows / 9,335 raw) for Task 2.
  - AI Assistance: spec authoring, plan writing, implementation AI-assisted
    (Claude Code); BQ verification SQL human-directed.
  - Row count impact: `dim_student_section_enrollments` unchanged vs. prod (the
    dedup it removes is a no-op). `rpt_gsheets__school_metrics_extract`
    comment-only diff. `src/dbt/kipptaf/CLAUDE.md` doc-only diff.
  - Self-review boxes checked: no new models, no exposure changes, no breaking
    changes, no external source changes, CLAUDE.md updated.
  - Issue links: `Closes #3901`, `Refs #4020`.
  - CI checks: Trunk passes (pre-push enforced), dbt Cloud expected green.

- [ ] **Step 4: Confirm PR creation**

Verify the returned PR URL and check that the body matches intent (no `env`
leaks, issue refs render). Surface the PR URL to the user.

---

## Self-Review Checklist

- **Spec coverage:**
  - Change 1 (`dim_student_section_enrollments` no-op dedup removal) → Task 1.
  - Change 2 (`rpt_gsheets__school_metrics_extract` comment refresh) → Task 2.
  - Change 3 (`src/dbt/kipptaf/CLAUDE.md` `(#3633)` strip) → Task 3.
  - PR/verification → Task 4 + Task 1 Step 5-7.

- **Placeholder scan:** None. Every step has exact paths, exact commands, exact
  strings to replace.

- **Type consistency:** N/A — no new types introduced. CTE name change
  (`course_enrollments_deduped` → `course_enrollments_joined`) flows
  consistently from Task 1 Step 3 → Step 4.
