# PowerSchool Section Teachers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the PowerSchool section-teacher join out of two kipptaf models
into one shared package model, and restore the Miami archive rows PR #5259
dropped from `bridge_course_section_teachers`.

**Architecture:** A new package intermediate,
`int_powerschool__section_teachers`, carries every join internal to PowerSchool
— sections to `sectionteacher` to `int_powerschool__teachers` to `roledef` — and
stops at `teachernumber`. A kipptaf `union_relations` wrapper unions the
regions. `bridge_course_section_teachers` and `rpt_clever__sections` each read
the wrapper instead of rebuilding the join. The wrapper unions the 3 NJ regions
in PR 1 and gains Miami in PR 2, because `union_relations` resolves its column
list at compile time and cannot name a relation the archive has not built yet.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, `uv` for every dbt invocation,
trunk for lint.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-09-11-powerschool-section-teachers-design.md`.
  Read it before Task 1.
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers`.
  Every path in this plan is relative to it. Every `git` call is
  `git -C <worktree>`.
- Never run bare `python`, `dbt`, or `dagster`. Always `uv run`.
- dbt from a worktree:
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/<project>`. Never
  `uv --directory <worktree> run dbt` — that sets cwd to the worktree root,
  where no `dbt_project.yml` exists.
- The `powerschool` project is never run standalone. Parse and build it through
  a consuming district (`kippnewark`, `kippcamden`, `kipppaterson`, and
  `kippmiami` only while the package is re-included).
- Open every file under `src/dbt/` with Read/Edit/Write, never `cat` — the
  path-scoped rule files load on a Read match and not on a Bash string.
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- `role` is a BigQuery reserved word. It takes backticks in SQL and
  `quote: true` in the properties yml.
- No `contains_pii` tag on any column of the new model. It is staff reference
  data with no student row, and no `teachernumber` column anywhere in the repo
  carries the tag.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- If a `git commit -m` is hook-blocked, write the message to
  `.claude/scratch/commit-msg.txt` and use `git commit -F`.

## File Structure

### PR 1 files

| File                                                                                               | Responsibility                                                      |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql`                | Create. The PowerSchool-internal join, stopping at `teachernumber`. |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__section_teachers.yml`     | Create. Column types plus the uniqueness test.                      |
| `src/dbt/kippmiami/packages.yml`                                                                   | Modify. Re-include `../powerschool`.                                |
| `src/dbt/kippmiami/dbt_project.yml`                                                                | Modify. Restore the archive `powerschool:` model and source blocks. |
| `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`            | Create. `union_relations` over the 3 NJ regions.                    |
| `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__section_teachers.yml` | Create. Wrapper column types.                                       |
| `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`                                        | Modify. Add the table entry.                                        |
| `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`                                        | Modify. Add the table entry.                                        |
| `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`                                      | Modify. Add the table entry.                                        |
| `src/dbt/kipptaf/models/marts/bridges/bridge_course_section_teachers.sql`                          | Modify. PowerSchool branch reads the wrapper.                       |
| `src/dbt/kipptaf/models/marts/bridges/properties/bridge_course_section_teachers.yml`               | Modify. Repoint 3 `source_model` values.                            |
| `src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql`                                  | Modify. `teachers_long` reads the wrapper.                          |

### PR 2 files

| File                                                                                    | Responsibility                                          |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `src/dbt/kippmiami/packages.yml`                                                        | Modify. Remove `../powerschool` again.                  |
| `src/dbt/kippmiami/dbt_project.yml`                                                     | Modify. Remove the archive `powerschool:` blocks again. |
| `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql` | Modify. Add Miami as the 4th relation.                  |
| `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`                              | Modify. Add the table entry, update the 11→12 prose.    |

---

## PR 1: package model, NJ wrapper, both consumers

### Task 1: The package model

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__section_teachers.yml`

**Interfaces:**

- Consumes: `base_powerschool__sections` (`sections_id`, `sections_dcid`,
  `sections_schoolid`), `stg_powerschool__sectionteacher` (`id`, `sectionid`,
  `teacherid`, `roleid`, `start_date`, `end_date`), `int_powerschool__teachers`
  (`id`, `schoolid`, `teachernumber`), `stg_powerschool__roledef` (`id`, `name`,
  `sortorder`).
- Produces: a relation with columns `sections_dcid INT64`, `sections_id INT64`,
  `sections_schoolid INT64`, `sectionteacher_id INT64`, `teacherid INT64`,
  `teachernumber STRING`, `role STRING`, `role_sortorder INT64`,
  `effective_start_date DATE`, `effective_end_date DATE`. Grain is one row per
  `sectionteacher` row. Tasks 3, 4 and 5 depend on these exact names.

- [ ] **Step 1: Write the model SQL**

Write
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql`:

```sql
select
    sec.sections_dcid,
    sec.sections_id,
    sec.sections_schoolid,

    st.id as sectionteacher_id,
    st.teacherid,

    t.teachernumber,

    r.name as `role`,
    r.sortorder as role_sortorder,

    cast(st.start_date as date) as effective_start_date,
    cast(st.end_date as date) as effective_end_date,
from {{ ref("base_powerschool__sections") }} as sec
inner join
    {{ ref("stg_powerschool__sectionteacher") }} as st
    on sec.sections_id = st.sectionid
inner join
    {{ ref("int_powerschool__teachers") }} as t
    on st.teacherid = t.id
    and sec.sections_schoolid = t.schoolid
inner join {{ ref("stg_powerschool__roledef") }} as r on st.roleid = r.id
```

Column order follows sqlfluff ST06: plain column refs grouped by table in join
order with a blank line between groups, then the two `cast()` calls last. Do not
reorder.

Sections come from `base_powerschool__sections`, not
`stg_powerschool__sections`. Both consumers already reach sections that way —
the bridge directly, and `rpt_clever__sections` through
`int_students__course_sections` to `int_powerschool__sections_union`.
`base_powerschool__sections` inner-joins courses, terms and schools, so it is
narrower: sourcing from staging instead adds 595 Newark rows on 506 sections
whose `course_number` has no row in `stg_powerschool__courses`. Those are AY2004
through AY2015 sections carrying retired mixed-case course numbers (`Span300`,
`Sci200`, `Tec101`, `AGRI`), absent from `dim_course_sections` for the same
reason, so including them would emit 595 orphan `course_section_key` values.
`base_powerschool__sections` uses `dbt_utils.star()`, which resolves columns at
run time, so the 3 columns read from it are enumerated explicitly rather than
starred.

- [ ] **Step 2: Write the properties yml**

Write
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__section_teachers.yml`:

```yaml
models:
  - name: int_powerschool__section_teachers
    description: >-
      One row per PowerSchool sectionteacher record that resolves to a section,
      a teacher and a role, expressing the many-to-many relationship between
      course sections and the staff assigned to them. Each row carries the role
      the teacher holds on that section and the dates the assignment was in
      effect. Distinct from the single primary teacher the sections table names
      directly, which base_powerschool__sections already resolves.


      Rows drop where any of the three does not resolve. Sections come from
      base_powerschool__sections, so a section whose course, term or school is
      missing is excluded, as is an assignment whose teacher has no schoolstaff
      record at that school. Both exclusions match what the consuming bridge and
      Clever feed already produced before this model existed.
    columns:
      - name: sectionteacher_id
        data_type: int64
        description: >-
          Primary key of the PowerSchool sectionteacher record, and the grain of
          this model. Unique only within a region.
        data_tests:
          - unique:
              config:
                severity: error
      - name: sections_dcid
        data_type: int64
        description: Durable key of the section the teacher is assigned to.
      - name: sections_id
        data_type: int64
        description:
          Section identifier used by sectionteacher and gradebook joins.
      - name: sections_schoolid
        data_type: int64
        description: School the section belongs to.
      - name: teacherid
        data_type: int64
        description: PowerSchool identifier of the assigned staff member.
      - name: teachernumber
        data_type: string
        description: >-
          Staff number carried through from the schoolstaff record, and the
          value consumers resolve against the staff roster.
      - name: role
        quote: true
        data_type: string
        description: >-
          Name of the role the teacher holds on the section, such as Lead
          Teacher, Co-teacher, Gradebook Access or Blended Learning.
      - name: role_sortorder
        data_type: int64
        description: >-
          Display order PowerSchool assigns the role, used to rank multiple
          teachers on one section.
      - name: effective_start_date
        data_type: date
        description: Date the teacher's assignment to the section began.
      - name: effective_end_date
        data_type: date
        description: Date the teacher's assignment to the section ended.
```

- [ ] **Step 3: Verify it parses**

Run:

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kippnewark
```

Expected: `Performance info` and no error. A `Compilation Error` naming
`int_powerschool__section_teachers` means a `ref()` typo.

- [ ] **Step 4: Verify it compiles to valid SQL**

Run:

```bash
uv run dbt compile --select int_powerschool__section_teachers --target dev \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kippnewark
```

Expected: `Compiled node 'int_powerschool__section_teachers'`. Read the compiled
SQL and confirm all 4 relations resolved to `kippnewark_powerschool`.

- [ ] **Step 5: Lint**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__section_teachers.yml </dev/null
```

Expected: `No issues`. An ST06 failure means Step 1's column order was changed.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__section_teachers.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers commit -m "feat(powerschool): add int_powerschool__section_teachers

Carries the sections to sectionteacher to teachers to roledef join that
bridge_course_section_teachers and rpt_clever__sections each rebuild in
kipptaf. Stops at teachernumber; the staff roster join stays in kipptaf.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Re-include the powerschool package in kippmiami

This exists so the archive can build the new model between PR 1 and PR 2. It is
reverted in PR 2.

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`

**Interfaces:**

- Consumes: nothing from Task 1 at parse time; the package model built in Task 1
  becomes buildable in `kippmiami` as a result of this task.
- Produces: a `kippmiami` project that resolves `ref("int_powerschool__*")`.

- [ ] **Step 1: Restore the exact block from the third rebuild**

Commit `238649793b` ("re-include the powerschool package with the 16 archive
hooks for the third rebuild") holds the exact block, 180 lines across both
files. Restore it verbatim rather than retyping:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
git show 238649793b -- src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml | git apply
```

Expected: no output. A conflict means `dbt_project.yml` changed since; in that
case apply with `git apply -3` and resolve.

- [ ] **Step 2: Confirm the new model is not disabled**

The restored block disables many staging models and 3 intermediates
(`int_powerschool__s_nj_stu_x_unpivot`, `int_powerschool__gpnode`,
`int_powerschool__gpprogress_grades`). Confirm the new model and all 4 of its
inputs are absent from every disable list:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
grep -nE 'section_teachers|stg_powerschool__sections:|sectionteacher|roledef|__teachers:|schoolstaff|stg_powerschool__users:' \
  src/dbt/kippmiami/dbt_project.yml || echo "NONE DISABLED — correct"
```

Expected: `NONE DISABLED — correct`. Any hit means that input is disabled in the
archive and the model cannot build there — stop and report it.

- [ ] **Step 3: Verify kippmiami parses with the package**

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kippmiami
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kippmiami
```

Expected: both succeed. `dbt deps` rewrites `package-lock.yml` — include it in
the commit.

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml </dev/null
```

Expected: `No issues`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add \
  src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/package-lock.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers commit -m "chore(kippmiami): re-include the powerschool package for the fourth archive rebuild

Restores the block from the third rebuild verbatim so the archive can build
int_powerschool__section_teachers. Removed again in the follow-up PR.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The kipptaf wrapper and its NJ sources

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__section_teachers.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`

**Interfaces:**

- Consumes: Task 1's package model, materialized per district.
- Produces: `int_powerschool__section_teachers` in kipptaf, carrying every Task
  1 column plus `_dbt_source_project STRING`. Tasks 4 and 5 join on
  `sections_id` or hash `sections_dcid`, both with `_dbt_source_project`.

- [ ] **Step 1: Write the wrapper**

Write
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kipppaterson_powerschool", model.name),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
```

This matches `stg_powerschool__sectionteacher.sql` in the same project, which is
the sibling to copy. Miami is deliberately absent — PR 2 adds it.

- [ ] **Step 2: Write the wrapper properties yml**

Write
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__section_teachers.yml`:

```yaml
models:
  - name: int_powerschool__section_teachers
    description: >-
      Union of the per-region PowerSchool section-teacher models. One row per
      sectionteacher record, carrying the role the teacher holds on the section
      and the dates the assignment was in effect.
    columns:
      - name: sectionteacher_id
        data_type: int64
        description: >-
          Primary key of the PowerSchool sectionteacher record. Unique only
          within a region, so it is not the grain of this union.
      - name: sections_dcid
        data_type: int64
        description: Durable key of the section the teacher is assigned to.
      - name: sections_id
        data_type: int64
        description:
          Section identifier used by sectionteacher and gradebook joins.
      - name: sections_schoolid
        data_type: int64
        description: School the section belongs to.
      - name: teacherid
        data_type: int64
        description: PowerSchool identifier of the assigned staff member.
      - name: teachernumber
        data_type: string
        description: >-
          Staff number consumers resolve against int_people__staff_roster.
      - name: role
        quote: true
        data_type: string
        description: >-
          Name of the role the teacher holds on the section, such as Lead
          Teacher, Co-teacher, Gradebook Access or Blended Learning.
      - name: role_sortorder
        data_type: int64
        description: >-
          Display order PowerSchool assigns the role, used to rank multiple
          teachers on one section.
      - name: effective_start_date
        data_type: date
        description: Date the teacher's assignment to the section began.
      - name: effective_end_date
        data_type: date
        description: Date the teacher's assignment to the section ended.
      - name: _dbt_source_project
        data_type: string
        description: District code location derived from _dbt_source_relation.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - sectionteacher_id
              - _dbt_source_project
```

`sectionteacher_id` is unique per region but collides across them, so the
uniqueness test is the composite, not a bare `unique`.

- [ ] **Step 3: Add the source entry to all 3 NJ source files**

In each of `sources-kippnewark.yml`, `sources-kippcamden.yml`, and
`sources-kipppaterson.yml`, add this block under `tables:`, keeping the file's
existing alphabetical ordering (it sorts just before
`int_powerschool__section_grade_config`). Substitute the district name on the
`asset_key` line — `kippnewark`, `kippcamden`, `kipppaterson`:

```yaml
- name: int_powerschool__section_teachers
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippnewark
          - powerschool
          - int_powerschool__section_teachers
```

- [ ] **Step 4: Verify kipptaf parses**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Expected: success.
`Compilation Error ... depends on a source named ... which was not found` means
a source entry is missing or misnamed.

- [ ] **Step 5: Confirm the wrapper's column list resolves**

A dev-target compile expands to nothing because no `zz_<user>_*` copy exists.
Compile against staging, which reads the same `zz_stg_*` relations dbt Cloud CI
does. This is a read, not a warehouse write, so it needs no authorization.

```bash
uv run dbt compile --select int_powerschool__section_teachers --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Expected before Task 6's seed: an EMPTY expansion, which still compiles clean.
That is why Task 6 exists. Re-run this step after Task 6 and confirm all 10
columns are listed.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__section_teachers.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml \
  src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add -u src/dbt/kipptaf
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__section_teachers.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers commit -m "feat(kipptaf): union the NJ section-teacher package models

Miami joins the union in the follow-up PR, once the archive has built the
package model.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Swap `bridge_course_section_teachers`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_course_section_teachers.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_course_section_teachers.yml`

**Interfaces:**

- Consumes: Task 3's wrapper — `sections_dcid`, `teachernumber`, `role`,
  `effective_start_date`, `effective_end_date`, `_dbt_source_project`.
- Produces: no change to the bridge's output columns or to any
  `course_section_key` value.

- [ ] **Step 1: Replace the `powerschool_teachers` CTE**

In `bridge_course_section_teachers.sql`, replace the whole
`powerschool_teachers` CTE (currently lines 35 to 67) with:

```sql
    powerschool_teachers as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["pst.sections_dcid", "pst._dbt_source_project"]
                )
            }} as course_section_key,

            {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }} as staff_key,

            pst.`role`,
            pst.effective_start_date,
            pst.effective_end_date,

        from {{ ref("int_powerschool__section_teachers") }} as pst
        inner join
            {{ ref("int_people__staff_roster") }} as sr
            on pst.teachernumber = sr.powerschool_teacher_number
    ),
```

The `cast(... as date)` calls are gone because the package model already casts.
Hash inputs are unchanged in composition and order, so `course_section_key` does
not churn.

- [ ] **Step 2: Leave the Focus branch and the final union untouched**

`focus_academic_year_boundary`, `focus_teachers`, and the two-branch `union all`
at the foot of the file are unchanged. Confirm with:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
git diff src/dbt/kipptaf/models/marts/bridges/bridge_course_section_teachers.sql | grep -c '^[-+].*focus'
```

Expected: `0`.

- [ ] **Step 3: Repoint the 3 `source_model` values in the properties yml**

In `properties/bridge_course_section_teachers.yml`, change
`source_model: stg_powerschool__roledef` on the `role` column and
`source_model: stg_powerschool__sectionteacher` on both `effective_start_date`
and `effective_end_date` to `source_model: int_powerschool__section_teachers`.
Leave `source_column` and every `description` as they are — the Miami text is
correct again once PR 2 lands.

- [ ] **Step 4: Verify it parses and compiles**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
uv run dbt compile --select bridge_course_section_teachers --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Expected: both succeed.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/bridges/bridge_course_section_teachers.sql \
  src/dbt/kipptaf/models/marts/bridges/properties/bridge_course_section_teachers.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add -u src/dbt/kipptaf/models/marts
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers commit -m "refactor(marts): read the section-teacher package model in the bridge

Replaces 4 joins with 1. Hash inputs and the Focus branch are unchanged.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Swap `rpt_clever__sections`

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql`

**Interfaces:**

- Consumes: Task 3's wrapper — `sections_id`, `teachernumber`, `role_sortorder`,
  `_dbt_source_project`.
- Produces: no change to the extract's output columns.

- [ ] **Step 1: Replace the 3 teacher joins in `teachers_long`**

In the first branch of the `teachers_long` CTE, replace the 3 joins to
`stg_powerschool__sectionteacher`, `stg_powerschool__roledef`, and
`int_powerschool__teachers` (currently lines 94 to 106) with:

```sql
        inner join
            {{ ref("int_powerschool__section_teachers") }} as pst
            on sec.sections_id = pst.sections_id
            and sec._dbt_source_project = pst._dbt_source_project
```

The dropped `sec.sections_schoolid = t.schoolid` predicate now lives inside the
package model as `sec.schoolid = t.schoolid`.

- [ ] **Step 2: Repoint the 2 columns the dropped joins supplied**

In the same select list, change `r.sortorder,` to
`pst.role_sortorder as sortorder,` and `t.teachernumber,` to
`pst.teachernumber,`. Keep both in their current positions in the select list so
sqlfluff ST06 still passes.

- [ ] **Step 3: Leave the Miami filter and the ENR branch untouched**

The `and sec._dbt_source_project != 'kippmiami'` filter stays — Clever does not
serve Miami. The second `union all` branch, built from `dsos` and `schools`, is
unchanged.

- [ ] **Step 4: Verify it parses and compiles**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
uv run dbt compile --select rpt_clever__sections --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Expected: both succeed.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/clever/rpt_clever__sections.sql </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers add -u src/dbt/kipptaf/models/extracts
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers commit -m "refactor(clever): read the section-teacher package model in the sections feed

Replaces 3 joins with 1. Output columns and the Miami filter are unchanged.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Seed staging, verify, and open PR 1

**Files:** none modified. This task runs builds and comparisons.

**Interfaces:**

- Consumes: Tasks 1 through 5.
- Produces: `zz_stg_<district>_powerschool.int_powerschool__section_teachers` in
  the 3 NJ districts, so dbt Cloud CI can resolve the new source.

- [ ] **Step 1: Get authorization for the staging seed**

This writes shared `zz_stg_*` tables other developers and CI read. Ask the user
in plain text for explicit go-ahead in the immediately-preceding turn, and do
not proceed without it.

- [ ] **Step 2: Seed the 3 NJ districts**

Run serially, not in parallel — parallel runs across projects exhaust BigQuery's
`INFORMATION_SCHEMA.simple_rate.user` quota:

```bash
for d in kippnewark kippcamden kipppaterson; do
  uv run dbt build --select int_powerschool__section_teachers --target staging \
    --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/${d}
done
```

Expected: 3 successful builds, each with its `unique` test passing.

- [ ] **Step 3: Re-run Task 3 Step 5 and confirm the columns resolve**

```bash
uv run dbt compile --select int_powerschool__section_teachers --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Expected: the compiled SQL now lists all 10 columns across 3 union branches. An
empty expansion means Step 2 did not land.

- [ ] **Step 4: Build both consumers into dev and compare to prod**

```bash
uv run dbt build --select rpt_clever__sections bridge_course_section_teachers \
  --target dev --defer \
  --state /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers/src/dbt/kipptaf
```

Then compare counts against prod via BigQuery MCP, substituting your dev schema
prefix for `zz_<user>`:

```sql
select
    'dev' as side,
    count(*) as n_rows,
    count(distinct format('%T|%T', course_section_key, staff_key)) as n_keys,
from `teamster-332318`.zz_<user>_kipptaf_marts.bridge_course_section_teachers

union all

select
    'prod' as side,
    count(*) as n_rows,
    count(distinct format('%T|%T', course_section_key, staff_key)) as n_keys,
from `teamster-332318`.kipptaf_marts.bridge_course_section_teachers
```

Expected: identical on both columns. The bridge is NJ-only in prod today, and PR
1 keeps it NJ-only, so any delta is a defect in Tasks 1 through 5 — stop and
diagnose rather than proceeding.

Run the same shape for `rpt_clever__sections` against
`kipptaf_extracts.rpt_clever__sections`, keying on `section_id`. PR #5259
verified that feed byte-for-byte against prod, so any delta is this change.

- [ ] **Step 5: Confirm no new orphan course section keys**

The bridge's `course_section_key` has a `relationships` test to
`dim_course_sections`. Confirm the swap introduced no orphan:

```sql
select count(*) as n_orphans
from `teamster-332318`.zz_<user>_kipptaf_marts.bridge_course_section_teachers as b
left join
    `teamster-332318`.kipptaf_marts.dim_course_sections as d
    on b.course_section_key = d.course_section_key
where d.course_section_key is null
```

Expected: `0`. `dim_course_sections` is unmodified by this PR, so prod is the
right side to join — PR #5259 verified it at 33,815 rows with 0 orphan course
keys.

- [ ] **Step 6: Push and open PR 1**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-section-teachers push -u origin cbini/refactor/claude-powerschool-section-teachers
```

Open the PR with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, `Refs #5260` in the body. Record in Reviewer
Notes: the row-identical results from Step 4, the staging seed that was run, and
that the archive materialization plus PR 2 follow.

- [ ] **Step 7: Hand off the archive materialization**

After PR 1 merges, the user materializes the package model into the archive:

```bash
uv run dbt build --select int_powerschool__section_teachers --target prod \
  --project-dir /workspaces/teamster/src/dbt/kippmiami
```

`--target prod` builds are classifier-blocked for Claude, so this is the user's
to run. Confirm it landed before starting PR 2:

```sql
select count(*) as n_rows, count(distinct sectionteacher_id) as n_keys
from `teamster-332318`.kippmiami_powerschool.int_powerschool__section_teachers
```

Expected: 19,529 rows and 19,529 distinct keys.

---

## PR 2: restore Miami

Start only after Task 6 Step 7 confirms the archive relation exists.

### Task 7: Remove the package, add Miami to the union

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`

**Interfaces:**

- Consumes: the archive relation built at Task 6 Step 7.
- Produces: a 4-region wrapper. No column changes; the bridge gains
  approximately 19,517 rows.

- [ ] **Step 1: Branch from the merged main**

```bash
cd /workspaces/teamster && git fetch origin main
gh issue develop 5260 --name cbini/refactor/claude-section-teachers-miami
git worktree add /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami cbini/refactor/claude-section-teachers-miami
```

Every path below is relative to that new worktree.

- [ ] **Step 2: Revert Task 2**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami && \
sha=$(git log --format=%H --grep 'fourth archive rebuild' -1) && \
echo "reverting ${sha}" && git revert --no-commit "${sha}"
```

Use a lowercase shell variable — an uppercase one is hook-denied. Then confirm
`kippmiami` is back to its pre-PR-1 state:

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami \
  diff --cached --stat -- src/dbt/kippmiami
```

Expected: `packages.yml`, `dbt_project.yml`, and `package-lock.yml` shown with
deletions matching Task 2's insertions.

- [ ] **Step 3: Add Miami to the wrapper**

In
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`,
add the Miami relation so the list reads:

```sql
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                    source("kipppaterson_powerschool", model.name),
                ]
```

Miami sits third, matching the ordering in every other 4-region wrapper in the
directory.

- [ ] **Step 4: Add the source entry and update the prose**

In `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`, add:

```yaml
- name: int_powerschool__section_teachers
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippmiami
          - powerschool
          - int_powerschool__section_teachers
```

Then update the file's comment that describes the archive as 11 permanent tables
so it reads 12, and names section teachers alongside stored grades, attendance,
and course enrollments.

- [ ] **Step 5: Verify the union picks Miami up**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami/src/dbt/kipptaf
uv run dbt compile --select int_powerschool__section_teachers --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami/src/dbt/kipptaf
```

Expected: the compiled SQL now has 4 union branches, one naming
`zz_stg_kippmiami_powerschool`. If the Miami branch is missing, the archive
relation has not been cloned to staging — run
`uv run dbt clone --select int_powerschool__section_teachers --target staging --state src/dbt/kippmiami/target/prod --project-dir src/dbt/kippmiami`
after getting authorization, since it recreates a shared `zz_stg_*` relation.

- [ ] **Step 6: Verify the Miami rows land in the bridge**

Build the bridge into dev as in Task 6 Step 4, then:

```sql
select
    count(*) as n_miami_rows,
    count(distinct course_section_key) as n_miami_sections,
    count(distinct `role`) as n_roles,
from `teamster-332318`.zz_<user>_kipptaf_marts.bridge_course_section_teachers
where effective_start_date is not null
```

Cross-check the Miami slice specifically by counting the delta against prod:

```sql
select
    (select count(*) from `teamster-332318`.zz_<user>_kipptaf_marts.bridge_course_section_teachers)
    - (select count(*) from `teamster-332318`.kipptaf_marts.bridge_course_section_teachers)
    as n_added
```

Expected: `n_added` approximately 19,517, and 4 distinct roles on the Miami
slice — Lead Teacher, Co-teacher, Gradebook Access (edit), Blended Learning.

- [ ] **Step 7: Confirm no pre-existing key churned**

```sql
select count(*) as n_changed_keys
from `teamster-332318`.kipptaf_marts.bridge_course_section_teachers as p
left join
    `teamster-332318`.zz_<user>_kipptaf_marts.bridge_course_section_teachers as d
    on p.course_section_key = d.course_section_key
    and p.staff_key = d.staff_key
    and p.effective_start_date is not distinct from d.effective_start_date
where d.course_section_key is null
```

Expected: `0`. Any row here means a prod key stopped existing, which the hash
composition should make impossible — stop and diagnose.

- [ ] **Step 8: Lint, push, open PR 2**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql \
  src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami add -u
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami commit -m "feat(kipptaf): union Miami archive section teachers, drop the package again

Restores the 19,517 Miami archive rows PR #5259 dropped from the bridge,
across 3,433 sections and 4 roles, AY2018 through AY2025.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-section-teachers-miami push -u origin cbini/refactor/claude-section-teachers-miami
```

Open the PR with `Refs #5260`, recording the Step 6 and Step 7 numbers in
Reviewer Notes.
