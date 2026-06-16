# Assessment-scores dbt dim enrichments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three DDI-parity dimension columns that are clean passthroughs of
values already present upstream: `is_foundations` on `dim_courses`, and `is_504`

- `year_in_network` on `dim_student_enrollments`.

**Architecture:** Additive-only dbt mart changes in `kipptaf`. Each column
already exists on a model the target dim already reads (or already joins), so
these are projections — no new joins, no surrogate-key hash changes.

**Tech Stack:** dbt (BigQuery), `src/dbt/kipptaf`. Work in the worktree
`/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube`.

**Prerequisite:** Plan 1 (`2026-06-11-assessment-scores-dbt-foundation.md`)
applied on this branch. Run Task 0 of Plan 1 (dbt deps) if not already done.

**Scope guardrails:**

- Additive only. No `generate_surrogate_key(...)` input changes, no new joins.
- Follow `src/dbt/kipptaf/models/marts/CLAUDE.md` (R1–R10, ST06, reserved
  words).
- `git -C <worktree>` for git; name exact files in `git add` (never
  `-u`/`-A`/`.`).
- `--project-dir <worktree>/src/dbt/kipptaf` for dbt;
  `--target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.

**Deferred (NOT in this plan — need sourcing work, tracked separately):**

- `head_of_school` — `dim_locations` is a single-sheet passthrough; adding it
  needs a leadership-crosswalk join, and the obvious column
  (`head_of_school_preferred_name_lastfirst`) is NULL on 18/19 schools, so the
  real HoS-name source must be found first.
- `is_self_contained` — no clean dim/intermediate derivation (every occurrence
  is a `false`/`null` literal or a finalsite-roster passthrough).
- `is_sipps` — derived flag (enrolled in course `SEM01099G1`), not a
  passthrough.

---

## Task 1: Add `is_foundations` to `dim_courses`

`dim_courses` already left-joins
`stg_google_sheets__assessments__course_subject_crosswalk as csc` on
`c.course_number = csc.powerschool_course_number` (it reads
`csc.discipline as academic_subject`). `is_foundations` is on that same
crosswalk — add one projection.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml`

- [ ] **Step 1: Confirm the crosswalk key is unique (no fan-out)**

The join already exists, but confirm `dim_courses` will not fan out:

```bash
uv run dbt show --inline "select powerschool_course_number, count(*) as n from {{ ref('stg_google_sheets__assessments__course_subject_crosswalk') }} group by 1 having count(*) > 1" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

Expected: zero rows. (If any row returns, STOP — the existing join would already
be fanning; raise it, do not dedupe.)

- [ ] **Step 2: Add the column to `dim_courses.sql`**

Add `csc.is_foundations,` to the SELECT, grouped with the other `csc.` column
(`csc.discipline as academic_subject`) so ST06 keeps the `csc` enumerations
together. Resulting SELECT body:

```sql
    c.course_number as course_code,
    c.course_name as course_title,
    c.credittype as credit_type,
    c.credit_hours as credits,

    csc.discipline as academic_subject,
    csc.is_foundations,
```

(Reorder `credits` above the `csc` group if needed so the `c.` and `csc.`
enumerations are not interleaved — run trunk check in Task 3 to confirm ST06.)

- [ ] **Step 3: Add the column to the contract YAML**

In `properties/dim_courses.yml`, add (read the file first, match formatting):

```yaml
- name: is_foundations
  data_type: boolean
  description: >-
    TRUE if this course is a Foundations (intervention) course, per the
    course-subject crosswalk.
```

- [ ] **Step 4: Build and verify row count unchanged**

```bash
uv run dbt build --select dim_courses --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS including the PK uniqueness test (row count unchanged — the join
already existed and Step 1 confirmed it is 1:1).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube add src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube commit -m "feat(dbt): add is_foundations to dim_courses

Refs #4163"
```

---

## Task 2: Add `is_504` and `year_in_network` to `dim_student_enrollments`

`dim_student_enrollments` reads
`int_powerschool__student_enrollment_union as enr`. That union carries `is_504`
(passed through its `select * except(...)`, originally
`base_powerschool__student_enrollments.is_504`) and `year_in_network` (re-added
at the union's final select). Both are plain projections.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml`

- [ ] **Step 1: Confirm both columns resolve on the union**

```bash
uv run dbt show --inline "select is_504, year_in_network from {{ ref('int_powerschool__student_enrollment_union') }}" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

(No trailing `limit` — dbt 1.11/BigQuery rejects it on `--inline`.) Expected:
the columns resolve. If either errors, STOP and report.

- [ ] **Step 2: Add the columns to `dim_student_enrollments.sql`**

Add to the `enr.` enumeration group (with `enr.is_retained_year`, etc.):

```sql
    enr.is_504,
    enr.year_in_network,
```

- [ ] **Step 3: Add the columns to the contract YAML**

In `properties/dim_student_enrollments.yml` (read first, match formatting):

```yaml
- name: is_504
  data_type: boolean
  description: >-
    TRUE if the student has an active 504 plan for this enrollment.

- name: year_in_network
  data_type: int64
  description: >-
    Count of years the student has been enrolled in the network. Populated on
    the student's primary enrollment stint per academic year; null on additional
    same-year stints (multi-stint students).
```

- [ ] **Step 4: Build, verify row count unchanged, and check `year_in_network`
      population**

```bash
uv run dbt build --select dim_student_enrollments --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS (row count unchanged — pure projection). Then check the
`year_in_network` null share (expected: some nulls on multi-stint rows, but the
majority populated):

```bash
uv run dbt show --inline "select countif(year_in_network is null) as n_null, count(*) as n_total from {{ ref('dim_student_enrollments') }}" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

If `n_null` is a large majority (e.g. >60% of rows), STOP and report — the
`rn_year = 1` nulling in the union may make this column too sparse to expose,
and we should source it differently instead.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube add src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube commit -m "feat(dbt): add is_504 and year_in_network to dim_student_enrollments

Refs #4163"
```

---

## Task 3: Trunk-check and push

**Files:** none (validation).

- [ ] **Step 1: Trunk-check the four changed files**

Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml
```

Expected: `No issues`. Fix any ST06 ordering and rebuild before pushing.

- [ ] **Step 2: Push (confirm dbt Cloud CI is idle first)**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube push origin cristinabaldor/feat/claude-assessment-scores-cube
```

- [ ] **Step 3: After CI passes, pull warnings**

`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. Expect only
the pre-existing/known warns (#4173 college-Practice, #4174 bridge orphans) plus
stale-dev drift — triage anything new per `marts/CLAUDE.md`.

---

## Self-review notes

- **Spec coverage:** `is_foundations`, `is_504`, `year_in_network` — Tasks 1–2.
  `head_of_school`, `is_self_contained`, `is_sipps` are explicitly deferred (see
  header).
- **No hash changes, no new joins** — every column is a projection of a value
  already on a model the dim reads/joins.
- **Fan-out guards:** Task 1 Step 1 (crosswalk uniqueness) and Step 4 / Task 2
  Step 4 (row-count unchanged) protect grain; Task 2 Step 4 also gates on
  `year_in_network` not being too sparse.
