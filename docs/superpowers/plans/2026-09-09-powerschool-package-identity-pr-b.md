# PowerSchool Package Identity, PR B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** kipptaf reads student identity and school attributes from the
PowerSchool package facts instead of joining `stg_powerschool__students`,
`stg_powerschool__schools`, and `stg_powerschool__terms`; then
`stg_powerschool__students` and 14 more unions drop the `kippmiami` relation,
and kippmiami drops the `powerschool` package again.

**Architecture:** PR A (#5231, merged) put `students_student_number` and the
school columns on the package facts and the user rebuilt the Miami archive with
them. This PR is kipptaf-side: 1 new union wrapper, 10 reader edits that delete
a dimension or students join, 15 unions that lose their Miami relation, 6 dead
literals, and the kippmiami package removal. Every edit is verified as
row-identical to prod per region and year before the unions change.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, trunk.

Spec:
`docs/superpowers/specs/2026-09-09-powerschool-package-identity-design.md`,
sections "kipptaf changes (PR B)", "Delivery", "Verification", "Effect on
#5193". Issue: #5228. PR A: #5231.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b`.
  Every file path is under it. Every git call is
  `git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b`.
  Type the path out in commands; never use an uppercase shell variable (a hook
  denies them).
- Never run bare `dbt`; always
  `uv run dbt ... --project-dir <abs worktree path>/src/dbt/kipptaf`. From a
  worktree, `--state` must be the absolute main-checkout path
  `/workspaces/teamster/src/dbt/kipptaf/target/prod`. Run `uv run dbt deps` once
  per project before the first build in the worktree.
- Task 1 is a gate: no kipptaf edit starts until the prod Miami archive carries
  the PR A columns. `union_relations` fills a column one relation lacks with
  null, so `int_students__gpa` would lose Miami identity if this landed early.
- Identity column on every package fact is `students_student_number`; school
  columns are `school_name`, `school_abbreviation`, `school_level`;
  `int_powerschool__calendar_day` also carries `yearid`, `academic_year`,
  `schoolcity`; `base_powerschool__student_enrollments` carries
  `entry_school_abbreviation`.
- Parity: every touched kipptaf model must be row-identical to prod per
  `_dbt_source_project` per `academic_year` (or per `_dbt_source_project` where
  the model has no year). Dev tables land in `zz_cbini_kipptaf_<schema>`; prod
  is `kipptaf_<schema>`. Find `<schema>` with
  `uv run dbt ls --project-dir <abs worktree>/src/dbt/kipptaf --select <model> --output json --output-keys name,schema`.
- A union drop is executed only after Task 7 shows every direct reader's row
  count unchanged. A wrong drop fails silently.
- `contains_pii` does not travel through `source()`. A kipptaf wrapper over a
  PII-tagged package model re-declares it at model level:
  `config: meta: contains_pii: true` under the model entry.
- Counts only in commits, PR body, issue text. Never paste student rows.
- Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Do not write the bare token `env` in commit messages, PR bodies, or issue
  text; write "environment".
- Commit messages end with `Refs #5228` and the literal line
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Write the message
  to `/workspaces/teamster/.claude/scratch/commit-msg.txt` and commit with `-F`.
- YAML snippets in this plan may be shown unindented by the formatter. Indent
  each pasted block to match the surrounding list.

## File structure

kippmiami, `src/dbt/kippmiami/`:

- `packages.yml`, `dbt_project.yml`, `package-lock.yml`: restored to their
  content at `50419aa644` (the commit before PR A), which is the post-#5196
  state with no `powerschool` package.
- `CLAUDE.md`: PowerSchool paragraph moves to past tense for the second rebuild.

kipptaf, `src/dbt/kipptaf/models/`:

- `powerschool/intermediate/int_powerschool__calendar_day.sql` and
  `powerschool/intermediate/properties/int_powerschool__calendar_day.yml`: new
  4-region union wrapper.
- `powerschool/sources-kipp{newark,camden,miami,paterson}.yml`: one new table
  entry each for `int_powerschool__calendar_day`; `sources-kippmiami.yml` also
  loses 15 table entries.
- Identity readers: `students/intermediate/int_students__gpa.sql`,
  `students/intermediate/int_students__final_grades.sql`,
  `extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`.
- Wrapper PII tags:
  `powerschool/intermediate/properties/int_powerschool__gpa_term.yml`,
  `int_powerschool__gpa_cumulative.yml`,
  `int_powerschool__gpa_cumulative_year.yml`,
  `powerschool/base/properties/base_powerschool__final_grades.yml`.
- Dimension readers: `students/intermediate/int_students__calendar_day.sql`,
  `google/sheets/intermediate/int_google_sheets__dibels_pm_expectations.sql`,
  `kippadb/intermediate/int_kippadb__roster.sql`,
  `students/intermediate/int_extracts__course_schedule_by_term.sql`,
  `powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`,
  `extracts/littlesis/rpt_littlesis__enrollments.sql`,
  `extracts/tableau/rpt_tableau__state_assessments_dashboard.sql`.
- Union drops (15):
  `powerschool/staging/stg_powerschool__{students,attendance,attendance_code,cc,pgfinalgrades,studentcorefields,terms,u_studentsuserfields}.sql`
  and
  `powerschool/intermediate/int_powerschool__{category_grades_pivot,final_grades_pivot,gpa_cumulative_year,gpa_term_pivot,gradescaleitem_lookup,section_grade_config,terms}.sql`.
- Dead literals (6 sites): `students/intermediate/int_students__students.sql`,
  `int_students__student_core_fields.sql`,
  `int_students__student_user_fields.sql`,
  `extracts/tableau/intermediate/int_tableau__fresh_enrollment_scaffold.sql`
  (2), `people/staging/stg_people__student_logins.sql`.

`rpt_gsheets__kippmiami_payout_roster` is not touched: it already reads
`int_students__students`, not the archive.

---

### Task 1: Gate on the prod archive

**Files:** none. Verification only.

**Interfaces:**

- Consumes: the prod `kippmiami_powerschool` dataset after the user's
  materialization.
- Produces: go/no-go for every later task, and the Miami baseline counts.

- [ ] **Step 1: Identity and parity on the rebuilt archive**

Via the BigQuery MCP (`mcp__bigquery__execute_sql`):

```sql
select 'gpa_term' as t, countif(students_student_number < 8400000000) as bare, countif(students_student_number is null) as null_sn, count(*) as n
from `teamster-332318.kippmiami_powerschool.int_powerschool__gpa_term`
union all select 'gpa_cumulative', countif(students_student_number < 8400000000), countif(students_student_number is null), count(*)
from `teamster-332318.kippmiami_powerschool.int_powerschool__gpa_cumulative`
union all select 'gpa_cumulative_year', countif(students_student_number < 8400000000), countif(students_student_number is null), count(*)
from `teamster-332318.kippmiami_powerschool.int_powerschool__gpa_cumulative_year`
union all select 'calendar_day', null, countif(yearid is null), count(*)
from `teamster-332318.kippmiami_powerschool.int_powerschool__calendar_day`
union all select 'student_enrollments', null, countif(entry_schoolid is not null and entry_school_abbreviation is null), count(*)
from `teamster-332318.kippmiami_powerschool.base_powerschool__student_enrollments`
```

Expected: `bare` 0 and `null_sn` 0 on the 3 GPA tables; `n` 16,512 / 3,053 /
5,975 (the PR A dev dry-run values); `calendar_day` `n` 13,133; the
`student_enrollments` unmapped count 0. A column-not-found error means the
rebuild has not run or ran on the old code: stop and report.

- [ ] **Step 2: Confirm the untouched archive tables did not move**

```sql
select 'students' as t, count(*) as n from `teamster-332318.kippmiami_powerschool.stg_powerschool__students`
union all select 'cc', count(*) from `teamster-332318.kippmiami_powerschool.stg_powerschool__cc`
union all select 'storedgrades', count(*) from `teamster-332318.kippmiami_powerschool.stg_powerschool__storedgrades`
union all select 'ada', count(*) from `teamster-332318.kippmiami_powerschool.int_powerschool__ada`
```

Expected: 3,946 / 98,865 / (the PR A dry-run value for storedgrades) / 7,930.
Record every number in `/workspaces/teamster/.claude/scratch/pr-b-parity.md`
under `## Task 1 archive gate`.

- [ ] **Step 3: Baseline the readers of the 15 unions before any edit**

Run, once per model in this list, and record the result under
`## Task 1 reader baselines` in the same scratch file:

```sql
select count(*) as n
from `teamster-332318.kipptaf_<schema>.<model>`
```

Models (schema in parentheses, confirm each with `dbt ls` per Global
Constraints): `rpt_clever__enrollments`, `rpt_tableau__student_info_audit`,
`int_students__calendar_day`, `int_students__terms`,
`int_students__student_enrollments`, `int_students__student_user_fields`,
`rpt_tableau__academic_goals_rollup`, `int_students__student_core_fields`,
`rpt_tableau__gradebook_dashboard`, `rpt_deanslist__final_grades`,
`rpt_tableau__student_course_grades`, `rpt_deanslist__transcript_gpas`,
`rpt_tableau__gpa_cumulative_year`, `int_students__athletic_eligibility`,
`rpt_gsheets__school_metrics_extract`, `rpt_tableau__gradebook_assignments`,
`int_students__students`, `int_tableau__fresh_enrollment_scaffold`,
`stg_people__student_logins`, `rpt_deanslist__family_contacts`,
`rpt_powerschool__autocomm_students`, `rpt_deanslist__hs_transcript_programs`,
`rpt_deanslist__state_test_scores`, `rpt_deanslist__transcript_grades`,
`rpt_tableau__college_assessment_dashboard_de`,
`rpt_tableau__student_attrition_over_time_v1`,
`rpt_branchingminds__course_performance`.

For the 3 current-year Clever and autocomm models, also record
`count(*) where _dbt_source_project = 'kippmiami'` (expected 0 already). These
baselines are what Task 7 compares against. Prod tables refresh through the day,
so record the timestamp and treat a difference within the day's churn on a
current-year extract as drift, not a defect.

---

### Task 2: Remove the `powerschool` package from kippmiami

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`, `src/dbt/kippmiami/dbt_project.yml`,
  `src/dbt/kippmiami/package-lock.yml`
- Modify: `src/dbt/kippmiami/CLAUDE.md`

**Interfaces:**

- Consumes: the file contents at `50419aa644`.
- Produces: kippmiami with zero PowerSchool models; the archive tables stay.

- [ ] **Step 1: Restore the 3 files from the commit before PR A**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b checkout 50419aa644 -- src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/package-lock.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b diff --stat HEAD -- src/dbt/kippmiami/
```

Expected: `packages.yml` loses `- local: ../powerschool`; `dbt_project.yml`
loses the `powerschool:` block under `models:` and the whole top-level
`sources:` block (about 173 lines); `package-lock.yml` loses the `powerschool`
entry and keeps `dbt_external_tables` at `0.12.3`. Nothing else changes.

- [ ] **Step 2: Prune the package and parse**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kippmiami
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kippmiami --target dev
uv run dbt ls --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kippmiami --target dev --resource-type model --output name | grep -c powerschool
```

Expected: parse succeeds; the count is 0. `dbt deps` removes the stale
`dbt_packages/powerschool` directory; if `parse` still lists powerschool models,
delete `<worktree>/src/dbt/kippmiami/dbt_packages/powerschool` and parse again.

- [ ] **Step 3: CLAUDE.md to past tense**

In `src/dbt/kippmiami/CLAUDE.md`, replace the sentence "A second rebuild, after
#5228 merges, adds identity and school columns to the GPA, final grades,
calendar day, and student enrollment models." with "It was rebuilt again after
#5231 merged, adding identity and school columns to the GPA, final grades,
calendar day, and student enrollment models." Keep every other sentence.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/CLAUDE.md </dev/null
```

Commit message:

```text
chore(kippmiami): drop the powerschool package after the second archive rebuild

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b add src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/package-lock.yml src/dbt/kippmiami/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 3: kipptaf wrapper for `int_powerschool__calendar_day`

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__calendar_day.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__calendar_day.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kippmiami.yml`, `sources-kipppaterson.yml`

**Interfaces:**

- Consumes: `<region>_powerschool.int_powerschool__calendar_day` in all 4
  regions (package model from PR A; Miami's from the rebuild).
- Produces: kipptaf `int_powerschool__calendar_day` with every package column
  plus `_dbt_source_relation` and `_dbt_source_project`. Task 5 reads
  `schoolid`, `date_value`, `insession`, `membershipvalue`, `week_start_date`,
  `week_end_date`, `yearid`, `academic_year`, `schoolcity`.

- [ ] **Step 1: Write the wrapper**

`int_powerschool__calendar_day.sql`, the same shape as
`int_powerschool__calendar_rollup.sql` next to it:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__calendar_day"),
                    source("kippcamden_powerschool", "int_powerschool__calendar_day"),
                    source("kippmiami_powerschool", "int_powerschool__calendar_day"),
                    source("kipppaterson_powerschool", "int_powerschool__calendar_day"),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
```

- [ ] **Step 2: Properties file**

`properties/int_powerschool__calendar_day.yml`:

```yaml
models:
  - name: int_powerschool__calendar_day
    description: >-
      Union of each region's int_powerschool__calendar_day: one row per
      PowerSchool calendar day with the covering year term and the school's
      name, abbreviation, level, and city attached. Column docs live on the
      package model.
    config:
      materialized: table
    columns:
      - name: _dbt_source_relation
        data_type: string
      - name: _dbt_source_project
        data_type: string
      - name: id
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: date_value
        data_type: date
      - name: insession
        data_type: int64
      - name: membershipvalue
        data_type: float64
      - name: week_start_date
        data_type: date
      - name: week_end_date
        data_type: date
      - name: yearid
        data_type: int64
      - name: academic_year
        data_type: int64
      - name: school_name
        data_type: string
      - name: school_abbreviation
        data_type: string
      - name: school_level
        data_type: string
      - name: schoolcity
        data_type: string
```

The wrapper emits every package column; the YAML lists the ones consumers read.
That matches `int_powerschool__calendar_rollup.yml`, which does not enumerate
every union column either.

- [ ] **Step 3: Source entries**

In each of the 4 `sources-kipp*.yml`, directly after the
`- name: int_powerschool__calendar_rollup` table block, add (with `<region>`
replaced by `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`
respectively):

```yaml
- name: int_powerschool__calendar_day
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - <region>
          - powerschool
          - int_powerschool__calendar_day
```

- [ ] **Step 4: Build in dev and check the count**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select int_powerschool__calendar_day
```

Then:

```sql
select _dbt_source_project, count(*) as n, countif(yearid is null) as null_year
from `teamster-332318.zz_cbini_kipptaf_powerschool.int_powerschool__calendar_day`
group by 1 order by 1
```

Expected: 4 rows; per-region `n` equals `count(*)` on each
`<region>_powerschool.int_powerschool__calendar_day` (Miami 13,133).

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__calendar_day.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__calendar_day.yml src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml </dev/null
```

Commit message:

```text
feat(kipptaf): add the int_powerschool__calendar_day union wrapper

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

Stage the 6 files by path and commit with `-F`.

---

### Task 4: Identity readers take `students_student_number` from the fact

**Files:**

- Modify: `src/dbt/kipptaf/models/students/intermediate/int_students__gpa.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__final_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term.yml`,
  `int_powerschool__gpa_cumulative.yml`,
  `int_powerschool__gpa_cumulative_year.yml`,
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__final_grades.yml`

**Interfaces:**

- Consumes: `students_student_number` on the kipptaf wrappers
  `int_powerschool__gpa_term`, `int_powerschool__gpa_cumulative`,
  `base_powerschool__final_grades`; `student_number`, `schoolid`,
  `academic_year`, `rn_year` on `base_powerschool__student_enrollments`.
- Produces: the same output columns as today. `student_number` on the
  PowerSchool branch of `int_students__gpa` and `int_students__final_grades` now
  comes from the fact. The KIPP Forward roster no longer refs
  `stg_powerschool__students`.

- [ ] **Step 1: `int_students__gpa`**

Delete the `powerschool_students` CTE (the first CTE, with its 2 comment lines).
In `powerschool_conformed`, replace the line `ps.student_number,` with
`gt.students_student_number as student_number,` and delete the whole second
`left join` (the 4 comment lines beginning "-- left, not inner" and the 3 join
lines to `powerschool_students as ps`). The `gc` join stays.

- [ ] **Step 2: `int_students__final_grades`**

Same edit: delete the `powerschool_students` CTE; in `powerschool_conformed`
replace `ps.student_number,` with
`fg.students_student_number as student_number,` and delete the comment lines
plus the `left join powerschool_students as ps` block. `powerschool_conformed`
then reads from `base_powerschool__final_grades` alone.

Both models' descriptions mention the `dcid >= 1` placeholder filter as the
reason `student_number` is the join key. Update each YAML description sentence
to say the package fact carries `students_student_number` directly; open the
properties file, find the sentence that names `dcid >= 1`, and reword it in
place.

- [ ] **Step 3: KIPP Forward Miami roster**

Replace the `ps_xwalk` CTE (the comment block beginning "/* The archive was
rebuilt with student_number 8400-prefixed" through the CTE's closing `),`) with:

```sql
    /* gpa_cumulative is one row per student per school, and 323 Miami students
       have more than one row. The student's primary school in the archive's
       last year picks the row, the same school the retired students table
       carried as the student's current school. student_number is the archive's
       8400-prefixed value, so the Focus roster joins it directly. */
    ps_xwalk as (
        select
            se.student_number as ps_student_number,
            se.schoolid,

            ply.academic_year as ps_last_academic_year,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        cross join ps_last_academic_year as ply
        where
            se._dbt_source_project = 'kippmiami'
            and se.academic_year = ply.academic_year
            and se.rn_year = 1
    ),
```

Then change the `int_powerschool__gpa_cumulative` join predicate from
`on px.ps_studentid = pgc.studentid` to
`on px.ps_student_number = pgc.students_student_number`. The other 3 predicates
on that join stay. The `pada` join already keys on `px.ps_student_number` and
stays.

The roster's `ps_studentid` column disappears. Confirm nothing else in the file
reads `px.ps_studentid`:

```bash
grep -n "ps_studentid" /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql
```

Expected: 0 lines.

- [ ] **Step 4: Wrapper PII tags**

In each of the 4 wrapper properties files, add under the model entry (after
`- name: <model>` and any existing `description:`):

```yaml
config:
  meta:
    contains_pii: true
```

`int_powerschool__gpa_cumulative.yml` may already have a `config:` block with
`materialized: table`; add `meta: contains_pii: true` inside that block rather
than a second `config:` key. Check each file before editing.

- [ ] **Step 5: Build and compare**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select int_students__gpa int_students__final_grades rpt_gsheets__kippfwd_miami_roster
```

Expected: 3 models and their tests pass. Then, for `int_students__gpa` and
`int_students__final_grades`:

```sql
select
    _dbt_source_project,
    academic_year,
    count(*) as n,
    countif(student_number is null) as null_sn,
from `teamster-332318.zz_cbini_kipptaf_students.<model>`
group by 1, 2
```

against the same query on `teamster-332318.kipptaf_students.<model>`. Expected:
identical rows, `n` and `null_sn` equal per group. A `null_sn` difference means
a `studentid` the old `dcid >= 1` filter excluded now resolves, or the reverse;
report the group and count.

For the roster (`zz_cbini_kipptaf_extracts` vs `kipptaf_extracts`, confirm the
schema):

```sql
select
    academic_year,
    count(*) as n,
    countif(previous_year_gpa is not null) as n_prev_gpa,
    countif(ps_id is not null) as n_ps_id,
from `teamster-332318.<dataset>.rpt_gsheets__kippfwd_miami_roster`
group by 1
```

Expected: identical on both sides (prod on 2026-09-09: 365 / 388 rows, 660 of
754 `ps_id` non-null). If `n_prev_gpa` differs, the school pick changed for some
student; query the differing `student_number`s on both sides (counts only in the
report) and stop for a decision.

- [ ] **Step 6: Lint and commit**

Lint the 7 files. Commit message:

```text
refactor(kipptaf): read PowerSchool student identity from the package facts

int_students__gpa, int_students__final_grades, and the KIPP Forward Miami roster take students_student_number from gpa_term, gpa_cumulative, and final_grades instead of joining stg_powerschool__students. The 4 wrappers over PII-tagged package models re-declare contains_pii.

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

Stage the 7 files by path and commit with `-F`.

---

### Task 5: Dimension readers take school and term columns from the fact

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__dibels_pm_expectations.sql`
- Modify: `src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__roster.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__course_schedule_by_term.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/littlesis/rpt_littlesis__enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__state_assessments_dashboard.sql`

**Interfaces:**

- Consumes: Task 3's wrapper; `school_level`, `school_name`,
  `school_abbreviation` on `base_powerschool__course_enrollments` and
  `base_powerschool__sections`; `entry_school_abbreviation` on
  `base_powerschool__student_enrollments`.
- Produces: the same output columns and rows as today for all 7 models.

- [ ] **Step 1: `int_students__calendar_day`**

In the `powerschool_dated` CTE, change the `from` to
`{{ ref("int_powerschool__calendar_day") }} as cd`, change `t.yearid,` to
`cd.yearid,`, and delete the
`left join {{ ref("stg_powerschool__terms") }} as t` block (5 lines). Keep the
`where cd.date_value is not null` and its comment. Replace the comment block
beginning "-- LEFT JOIN: `stg_powerschool__terms` carries only" with:

```sql
    -- yearid comes from the package's int_powerschool__calendar_day, a left
    -- join to the isyearrec = 1 term window. Some real calendar days fall
    -- outside every window (August pre-service dates, a 15-day Paterson gap);
    -- their yearid and academic_year are null, and nothing downstream requires
    -- either to be non-null.
```

- [ ] **Step 2: `int_google_sheets__dibels_pm_expectations`**

Rewrite the `pm_rounds` CTE so calendar days drive it:

```sql
    pm_rounds as (
        select
            c.schoolcity as region,

            t.academic_year,
            t.name as term_name,

            safe_cast(right(t.code, 1) as int) as round_number,

            count(distinct c.date_value) as pm_round_days,

        from {{ ref("int_powerschool__calendar_day") }} as c
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on c.schoolcity = t.region
            and c.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name in ('BOY->MOY', 'MOY->EOY')
        where c.insession = 1
        group by c.schoolcity, t.academic_year, t.name, round_number
    ),
```

The old CTE also filtered `s.state_excludefromreporting = 0`. The wrapper does
not carry that flag. Step 8's parity check on this model decides whether the
filter mattered: the measure is `count(distinct date_value)` per region, so an
excluded school changes it only if it had an in-session date no reporting school
in the same city had. If the model is row-identical to prod, the filter is gone
for good. If not, restore the `stg_powerschool__schools` join for that one
predicate, keep `schoolcity` from the wrapper, and record why in the PR body.

- [ ] **Step 3: `int_kippadb__roster`**

In `es_grad`: replace `s.abbreviation as entry_school,` with
`co.entry_school_abbreviation as entry_school,`; delete the
`inner join {{ ref("stg_powerschool__schools") }} as s` block (4 lines); in the
`group by`, replace `s.abbreviation` with `co.entry_school_abbreviation`.

The old join was an inner join on `entry_schoolid`, so rows whose
`entry_schoolid` was null or unmatched dropped out. `entry_school_abbreviation`
is null for those rows. Add
`where co.rn_year = 1 and co.entry_school_abbreviation is not null` to keep the
population identical. Step 8 verifies.

- [ ] **Step 4: `int_extracts__course_schedule_by_term`**

In `section_quarters`: replace `d.school_level,` with `s.school_level,`; inside
the `school_level_alt` `if(...)`, replace `d.school_level` with
`s.school_level`; delete the
`inner join {{ ref("stg_powerschool__schools") }} as d` block (4 lines).
`base_powerschool__sections` carries `school_level` from its own inner join to
schools, so the population is unchanged.

- [ ] **Step 5: `int_powerschool__gradebook_assignments_scores`**

Replace `d.school_level` inside the `school_level_alt` `if(...)` with
`e.school_level`; delete the
`left join {{ ref("stg_powerschool__schools") }} as d` block (4 lines).
`base_powerschool__course_enrollments` stars every `base_powerschool__sections`
column, including `school_level`.

- [ ] **Step 6: `rpt_littlesis__enrollments`**

Replace `sch.name as school_name,` with `sec.school_name,`; delete the
`inner join {{ ref("stg_powerschool__schools") }} as sch` block (4 lines). Do
not touch the later Focus branch, which uses its own `sch` alias for a Focus
schedule relation.

- [ ] **Step 7: `rpt_tableau__state_assessments_dashboard`**

In `schedules_current`: replace `s.abbreviation as school,` with
`c.school_abbreviation as school,`; delete the
`left join {{ ref("stg_powerschool__schools") }} as s` block (3 lines).

- [ ] **Step 8: Build and compare**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select int_students__calendar_day int_google_sheets__dibels_pm_expectations int_kippadb__roster int_extracts__course_schedule_by_term int_powerschool__gradebook_assignments_scores rpt_littlesis__enrollments rpt_tableau__state_assessments_dashboard
```

Expected: 7 models and their tests pass.
`int_powerschool__gradebook_assignments_scores` and
`int_extracts__course_schedule_by_term` are large; allow 10 minutes.

Then, per model, dev vs prod:

```sql
select _dbt_source_project, <year column>, count(*) as n
from `teamster-332318.<dataset>.<model>`
group by 1, 2 order by 1, 2
```

Year column per model: `int_students__calendar_day` `academic_year`;
`int_google_sheets__dibels_pm_expectations` has no source project, group by
`region, academic_year, term_name, round_number` and compare `pm_round_days` and
`pm_days` too; `int_kippadb__roster` has no year, group by `_dbt_source_project`
and also compare `countif(entry_school is null)`;
`int_extracts__course_schedule_by_term` `academic_year`;
`int_powerschool__gradebook_assignments_scores` `cc_academic_year`;
`rpt_littlesis__enrollments` has neither, compare `count(*)` and
`count(distinct school_name)`; `rpt_tableau__state_assessments_dashboard`
`academic_year`, and also `count(distinct school)`.

Expected: identical on every row. Current-year models
(`gradebook_assignments_scores`, `littlesis`, `state_assessments_dashboard`)
churn during the day; re-run both sides within the same minute before treating a
difference as a defect. Record every pair in the scratch parity file under
`## Task 5`.

- [ ] **Step 9: Lint and commit**

Lint the 7 files. Commit message:

```text
refactor(kipptaf): read school and term attributes from the PowerSchool facts

Seven models stop joining stg_powerschool__schools or stg_powerschool__terms and read the column the fact already carries: calendar day year and school city from int_powerschool__calendar_day, entry school from base_powerschool__student_enrollments, school level, name, and abbreviation from course enrollments and sections.

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

Stage the 7 files by path and commit with `-F`.

---

### Task 6: Drop Miami from `students` and 14 more unions; delete the dead literals

**Files:**

- Modify: the 15 union models listed in "File structure".
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`
- Modify: the 5 files with 6 dead literals listed in "File structure".

**Interfaces:**

- Consumes: Task 1's reader baselines; Tasks 4 and 5 (no kipptaf model joins
  `stg_powerschool__students` for Miami identity any more).
- Produces: `stg_powerschool__students` and 14 unions with 3 relations; 15 fewer
  `kippmiami_powerschool` source tables; 6 predicates gone.

- [ ] **Step 1: Remove the Miami relation from 15 unions**

In each of these files, delete the one line (or 3-line wrapped form) that reads
`source("kippmiami_powerschool", ...)` inside
`union_relations(relations=[...])`:

`stg_powerschool__students`, `stg_powerschool__attendance`,
`stg_powerschool__attendance_code`, `stg_powerschool__cc`,
`stg_powerschool__pgfinalgrades`, `stg_powerschool__studentcorefields`,
`stg_powerschool__terms`, `stg_powerschool__u_studentsuserfields`,
`int_powerschool__category_grades_pivot`, `int_powerschool__final_grades_pivot`,
`int_powerschool__gpa_cumulative_year`, `int_powerschool__gpa_term_pivot`,
`int_powerschool__gradescaleitem_lookup`,
`int_powerschool__section_grade_config`, `int_powerschool__terms`.

Two files (`attendance_code`, `studentcorefields`, `u_studentsuserfields`,
`category_grades_pivot`) wrap the `source(...)` call over 3 lines; delete all 3.
Afterward:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf/models/powerschool
grep -c kippmiami_powerschool staging/stg_powerschool__students.sql staging/stg_powerschool__attendance.sql staging/stg_powerschool__attendance_code.sql staging/stg_powerschool__cc.sql staging/stg_powerschool__pgfinalgrades.sql staging/stg_powerschool__studentcorefields.sql staging/stg_powerschool__terms.sql staging/stg_powerschool__u_studentsuserfields.sql intermediate/int_powerschool__category_grades_pivot.sql intermediate/int_powerschool__final_grades_pivot.sql intermediate/int_powerschool__gpa_cumulative_year.sql intermediate/int_powerschool__gpa_term_pivot.sql intermediate/int_powerschool__gradescaleitem_lookup.sql intermediate/int_powerschool__section_grade_config.sql intermediate/int_powerschool__terms.sql | grep -v ":0$" | wc -l
grep -l kippmiami_powerschool staging/*.sql base/*.sql intermediate/*.sql | wc -l
```

Expected: 0, then 20 (35 before minus 15).

- [ ] **Step 2: Remove the 15 table entries from `sources-kippmiami.yml`**

Delete the `- name: <table>` block (name plus its `config: meta: dagster:`
sub-block, 9 lines each) for each of the 15 names above. Then:

```bash
grep -c "name: stg_powerschool__\|name: int_powerschool__\|name: base_powerschool__" /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
```

Expected: 61 (75 before, plus 1 from Task 3, minus 15).

- [ ] **Step 3: Delete the 6 dead literals**

- `int_students__students.sql`: the `powerschool_filtered` CTE becomes a plain
  read. Replace the CTE body's `where p._dbt_source_project != 'kippmiami'` line
  by deleting it, so the CTE is
  `select p.*, from stg_powerschool__students as p`.
- `int_students__student_core_fields.sql` and
  `int_students__student_user_fields.sql`: delete the line
  `where s._dbt_source_project != 'kippmiami'`.
- `int_tableau__fresh_enrollment_scaffold.sql`: on line 16, the predicate
  becomes `where state_excludefromreporting = 0`; on line 45 it becomes
  `where enroll_status = 0`. The line-16 site reads `stg_powerschool__schools`,
  which keeps Miami: leave that one in place. Only the students-side literal
  (line 45) is dead. Edit line 45 only.
- `stg_people__student_logins.sql`: delete the line
  `and _dbt_source_project != 'kippmiami'` inside `union_source`.

So 5 literals go, not 6: the spec counted the scaffold's schools-side literal,
which stays because `schools` keeps Miami. Say so in the commit body.

- [ ] **Step 4: Parse and the column gate**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev
uv run dbt build --empty --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select state:modified+
```

Expected: parse succeeds. The `--empty` build reports PASS for every model this
branch touches; errors in untouched models (missing personal dev copies,
pre-existing `main` errors such as `stg_overgrad__universities`) are not this
branch's. List every ERROR node in the report and say which are in touched files
(expected: none).

- [ ] **Step 5: Lint and commit**

Lint the 15 union files, `sources-kippmiami.yml`, and the 5 literal files.
Commit message:

```text
refactor(kipptaf): drop the kippmiami relation from students and 14 more unions

No kipptaf model reads Miami rows from these 15 unions any more: identity now comes from the package facts, and every other reader excludes Miami or is current-year only. Five Miami literals on students readers are dead and go with them; the schools-side literal in int_tableau__fresh_enrollment_scaffold stays because schools keeps Miami.

Refs #5228
Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

Stage the 21 files by path and commit with `-F`.

---

### Task 7: Verify the drops against the Task 1 baselines

**Files:** none. Verification only.

**Interfaces:**

- Consumes: Task 1 baselines; every model changed in Tasks 3 to 6.
- Produces: the evidence tables for the PR body.

- [ ] **Step 1: Build every reader of a dropped union in dev**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select stg_powerschool__students stg_powerschool__cc stg_powerschool__terms int_powerschool__terms stg_powerschool__u_studentsuserfields stg_powerschool__studentcorefields stg_powerschool__pgfinalgrades int_powerschool__gradescaleitem_lookup int_powerschool__gpa_cumulative_year int_powerschool__gpa_term_pivot int_powerschool__category_grades_pivot int_powerschool__final_grades_pivot int_powerschool__section_grade_config rpt_clever__enrollments rpt_clever__students rpt_tableau__student_info_audit int_students__terms int_students__student_enrollments int_students__student_user_fields int_students__student_core_fields int_students__students rpt_tableau__academic_goals_rollup rpt_tableau__gradebook_dashboard rpt_deanslist__final_grades rpt_tableau__student_course_grades rpt_deanslist__transcript_gpas rpt_tableau__gpa_cumulative_year int_students__athletic_eligibility rpt_gsheets__school_metrics_extract rpt_tableau__gradebook_assignments int_tableau__fresh_enrollment_scaffold stg_people__student_logins rpt_deanslist__family_contacts rpt_powerschool__autocomm_students rpt_deanslist__hs_transcript_programs rpt_deanslist__state_test_scores rpt_deanslist__transcript_grades rpt_tableau__college_assessment_dashboard_de rpt_tableau__student_attrition_over_time_v1 rpt_branchingminds__course_performance
```

This is a long build (some readers are wide Tableau extracts); allow 30 minutes
and run in the foreground. `stg_people__student_logins` reads `{{ this }}`; a
first dev build of it needs the deferred prod relation, which `--defer`
supplies. Expected: every model passes. A test failure on a reader that was
already warning on prod is not this branch's; record it.

- [ ] **Step 2: Compare each reader to its Task 1 baseline**

For every model built in Step 1 that has a Task 1 baseline, run
`select count(*) from zz_cbini_kipptaf_<schema>.<model>` and compare with the
recorded prod count. Expected: equal, or within same-day churn for the
current-year extracts (re-run the prod side and compare again). Any reader whose
count fell by a Miami-sized number means a drop verdict was wrong: restore that
relation in the union model, rebuild, and record the reader in the PR body under
"Verdicts overturned". Do not proceed to Task 8 with an unexplained difference.

Two direct checks:

```sql
select countif(_dbt_source_project = 'kippmiami') as miami_rows, count(*) as n
from `teamster-332318.zz_cbini_kipptaf_powerschool.stg_powerschool__students`
```

Expected: `miami_rows` 0 and `n` equals prod minus 3,946.

```sql
select countif(student_number >= 8400000000) as miami_rows, count(*) as n
from `teamster-332318.zz_cbini_kipptaf_tableau.rpt_tableau__college_assessment_dashboard_de`
```

Expected: 0 and 1,658 (prod on 2026-09-09).

- [ ] **Step 3: Miami history intact on the retained readers**

For `int_students__gpa`, `int_students__final_grades`,
`int_students__calendar_day`, and `int_students__category_grades`:

```sql
select academic_year, count(*) as n
from `teamster-332318.zz_cbini_kipptaf_students.<model>`
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Expected: identical to the same query on prod for every year through AY2025.

- [ ] **Step 4: Record**

Append every table to `/workspaces/teamster/.claude/scratch/pr-b-parity.md`
under `## Task 7`. Counts only.

---

### Task 8: Push and open the PR

**Files:**

- Create: `/workspaces/teamster/.claude/scratch/pr-b-body.md` (gitignored)

- [ ] **Step 1: Lint the branch and push**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity-pr-b
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git -C . diff --name-only origin/main..HEAD | grep -E '\.(sql|yml|md)$') </dev/null
git -C . push
```

The branch tracks `origin`. Before pushing, confirm no other PR's dbt Cloud CI
run is in progress on this branch (none exists yet).

- [ ] **Step 2: Write the PR body from the template**

Copy `.github/pull_request_template.md` to
`/workspaces/teamster/.claude/scratch/pr-b-body.md`. Keep every template line
and heading. One line per paragraph, no hard wraps. Summary:

> When merged, this pull request will make kipptaf read PowerSchool student
> identity and school attributes from the package facts instead of joining
> `stg_powerschool__students`, `stg_powerschool__schools`, and
> `stg_powerschool__terms`, drop the `kippmiami` relation from
> `stg_powerschool__students` and 14 more unions that no reader keeps Miami rows
> from, delete 5 dead Miami literals, and remove the `powerschool` package from
> kippmiami again after the second archive rebuild. Closes the PR B half of
> #5228.

Reviewer Notes, one line each: every touched model is row-identical to prod per
region and year (tables in the fold-out); the 15 union drops were verified
reader by reader against pre-edit baselines; the KIPP Forward roster now picks a
student's `gpa_cumulative` row through their AY2025 primary school instead of
the archive students table, with identical `previous_year_gpa` counts; the
DIBELS expectations model dropped the `state_excludefromreporting` filter (or
kept the schools join, whichever Task 5 decided) and is row-identical; the
scaffold's schools-side Miami literal stays because `schools` keeps Miami; dbt
Cloud CI builds `state:modified+` and will rebuild every reader of the 15
unions, so expect a long CI run.

Effect on #5193, one paragraph: the exit-marking DML is no longer needed, the 2
`exclude_frozen` calls on `rpt_clever__enrollments` and the one on
`rpt_clever__students` are dead, and `schools` plus the 5 staff gates remain.

"For Claude": paste the count tables from
`/workspaces/teamster/.claude/scratch/pr-b-parity.md`, the `--empty` gate result
with any untouched-file errors named, and any test warnings. Spec and plan
paths. Executed with subagent-driven development, one reviewer per task.

End with `Refs #5228`, `Refs #5012`, `Refs #5193`, and the line
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 3: Open the PR**

`mcp__github__create_pull_request` with `owner: TEAMSchools`, `repo: teamster`,
`head: cbini/refactor/claude-powerschool-package-identity-pr-b`, `base: main`,
title
`refactor(kipptaf): read PowerSchool identity from the package facts and drop Miami from students and 14 more unions (PR B)`,
body from Step 2. Read the PR back and confirm the title and first Summary
sentence.

- [ ] **Step 4: Watch CI and review**

Invoke `pr-ci-review`. Expected: Trunk passes; dbt Cloud CI builds every
`state:modified+` kipptaf model, which is large here, and passes; after it
passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id, warning_only=true)` and compare against
`main`. No Dagster branch deployment fires for a `src/dbt/**`-only PR. When
`claude-review` posts, invoke `superpowers:receiving-code-review` before acting
on it.

---

## After merge (user-run, not part of this plan's commits)

1. Confirm the kipptaf prod deploy ran (`gh run list --branch main`) and the
   first scheduled kipptaf build after it rebuilt `stg_powerschool__students`
   with 3 relations.
2. #5193 picks up from the "Effect on #5193" paragraph.

## Self-review notes

- Spec coverage: "kipptaf changes (PR B)" wrapper is Task 3; the reader table is
  Tasks 4 and 5 (the payout roster row is dropped: it already reads
  `int_students__students`); the union table and dead literals are Task 6; the
  kippmiami removal is Task 2; "Verification" is Tasks 1 and 7; "Delivery" step
  3 is Task 8.
- Spec corrections folded in: 5 dead literals, not 6 (the scaffold's
  schools-side literal stays); the payout roster needs no edit.
- Type consistency: `students_student_number`, `school_level`, `school_name`,
  `school_abbreviation`, `entry_school_abbreviation`, `schoolcity` appear with
  the same names in Tasks 3 to 6 and in the spec.
- Open judgment call, resolved by data in Task 5 Step 8: the DIBELS
  `state_excludefromreporting` filter.
