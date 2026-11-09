# PowerSchool Stored Grades Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the personal saved query behind the quarterly PowerSchool
stored grades import with a contract-enforced kipptaf view plus thin wrappers in
`kippnewark`, `kippcamden`, and `kipppaterson`.

**Architecture:** Two upstream column adds (`comment_value` on
`int_students__final_grades`, `courses_gradescale_name` from the powerschool
package through `int_students__course_enrollments`), then one kipptaf `rpt_`
view joining those two domain `int_` models, then one wrapper per NJ district
filtered on `code_location`. Ships as one PR (#5705) using the single-PR
cross-project pattern for the package column.

**Tech Stack:** dbt (BigQuery), dbt unit tests, dbt Cloud CI, trunk.

**Spec:**
`docs/superpowers/specs/2026-10-05-powerschool-stored-grades-extract-design.md`.
Where the original design and its _Revision 2026-10-28_ section disagree, the
revision wins.

**Worktree:**
`/workspaces/teamster/.claude/worktrees/baribradley/docs/claude-stored-grades-extract-spec`
(branch `baribradley/docs/claude-stored-grades-extract-spec`, PR #5705). Every
path below is relative to it. Run dbt as
`uv run dbt <cmd> --project-dir src/dbt/<project>`.

## Global Constraints

- Import column names are fixed. The contract YAML spells `PotentialCrHrs`,
  `EarnedCrHrs`, and `Comment` in exactly that case.
- Every join between the two `int_` models uses `cc_dcid` and
  `_dbt_source_project` (A10). Never `_dbt_source_relation`.
- No dedupe in the `rpt_` (A5). No `select *` in its final select (A9).
- Baked-in filters, all four: `term_percent_grade_adjusted is not null`,
  `not is_homeroom`, `potential_credit_hours != 0` (with a SQL comment that this
  is the rule to revisit if 0-credit courses ever need storing),
  `school_level in ('MS', 'HS')`.
- `percent` is `least(term_percent_grade_adjusted, 100)`. `PotentialCrHrs` and
  `EarnedCrHrs` are constant `0`. `Comment` is
  `if(school_level = 'HS', comment_value, null)`.
- District wrappers: contract columns only, no tests, no descriptions; select
  every kipptaf column except `code_location`; filter
  `where code_location = '{{ project_name }}'`.
- Exposure per NJ project in `models/exposures/powerschool.yml`: name
  `powerschool_stored_grades`, label `PowerSchool Stored Grades Import`, type
  `application`, `owner.name: Data Team`,
  `depends_on: ref("rpt_powerschool__stored_grades")`,
  `config.meta.dagster.kinds: [powerschool]`. No exposure in kipptaf.
- `--target staging` builds and clones are shared writes
  (`.claude/rules/dbt-yaml.md` → _Shared staging writes_): run only with the
  user's authorization in the turn right before, each in its own Bash call.
- No student values in commits, PR text, or comments. Report parity as row
  counts only.

## Review Focus

1. A course whose `courses_gradescaleid` has no `gradescaleitem` row: the row
   must still export with a null `gradescale_name` (left join), not drop out.
   Pinned in Task 1, Step 4.
2. An ES section that passes every other filter (Camden has these): excluded.
   Pinned by the Task 4 unit test.
3. A course number that starts with `HR` but is not `HR` (for example `HR2`):
   `is_homeroom` excludes it where the old query kept it. Pinned by the parity
   check in Task 6, which must show zero such graded rows.
4. A percent above 100 (extra credit): exported as `100`, while `grade` and
   `gpa_points` stay as stored. Pinned by the Task 4 unit test.
5. Miami (Focus) rows: drop out at the null adjusted-percent filter, so no
   `kippmiami` `code_location` ever appears. Pinned in Task 4, Step 5.

---

### Task 1: `courses_gradescale_name` in the powerschool package

**Files:**

- Modify: `src/dbt/powerschool/models/sis/base/base_powerschool__sections.sql`
- Modify:
  `src/dbt/powerschool/models/sis/base/properties/base_powerschool__sections.yml`

**Interfaces:**

- Produces: `courses_gradescale_name` (string, nullable) on package
  `base_powerschool__sections`, and through its `dbt_utils.star` on
  `base_powerschool__course_enrollments` and `base_powerschool__final_grades`.

- [ ] **Step 1: Add the join and column.** In `base_powerschool__sections.sql`,
      `left join {{ ref("stg_powerschool__gradescaleitem") }} as gsi on cou.gradescaleid = gsi.id`
      after the teachers join, and select `gsi.name as courses_gradescale_name`
      with the other plain columns (S6: after `t.teacher_lastfirst`, in join
      order). No dedupe: `stg_powerschool__gradescaleitem.id` carries an
      error-level `unique` test.
- [ ] **Step 2: Add the column to the properties file**, with
      `data_type: string` if the model enforces a contract, and a description:
      "Name of the course's grade scale (the scale's own `gradescaleitem` row)."
- [ ] **Step 3: Build in dev through Newark.**
      `uv run dbt build --select base_powerschool__sections+1 --project-dir src/dbt/kippnewark 2>&1 | tail -n 30`
      Expected: PASS, including existing uniqueness tests.
- [ ] **Step 4: Check the join neither fans out nor drops rows.** Through the
      BigQuery MCP, compare `count(*)` of the dev `base_powerschool__sections`
      against prod `kippnewark_powerschool.base_powerschool__sections` (equal),
      and count rows where
      `courses_gradescaleid is not null and     courses_gradescale_name is null`
      (report the number; non-zero is allowed but list the distinct gradescale
      ids in the terminal for the user).
- [ ] **Step 5: Commit.**
      `git -C <worktree> add -u && git -C <worktree> commit -m "feat(powerschool): add course grade scale name to sections"`

### Task 2: `comment_value` on `int_students__final_grades`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__final_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__final_grades.yml`

**Interfaces:**

- Produces: `comment_value` (string) on `int_students__final_grades`; null on
  every Focus row.

- [ ] **Step 1: Add the column to both branches.** `powerschool_conformed`
      selects `fg.comment_value`; `focus_conformed` selects
      `cast(null as string) as comment_value`.
- [ ] **Step 2: Replace `full union all corresponding` (banned, S1).** The final
      statement becomes
      `select <cols>, from powerschool_conformed union all     select <cols>, from focus_conformed`,
      both lists enumerated in `powerschool_conformed`'s current column order
      with `comment_value` last, so the output column order is unchanged apart
      from the new column (S17).
- [ ] **Step 3: Document the column** in the properties file: "Teacher comment
      on the final grade, from PowerSchool `pgfinalgrades`. Null for Focus."
- [ ] **Step 4: Build.**
      `uv run dbt build --select int_students__final_grades --project-dir src/dbt/kipptaf 2>&1 | tail -n 30`
      Expected: PASS, the `cc_dcid` + `storecode` + `_dbt_source_project`
      uniqueness test included.
- [ ] **Step 5: Prove the union rewrite changed nothing else.** BigQuery MCP:
      `select * except (comment_value)` from the dev table `except distinct`
      prod `kipptaf_students.int_students__final_grades` returns 0 rows, both
      directions. (A difference that traces only to data loaded since the prod
      build is drift; re-run after a fresh dev build before calling it a bug.)
- [ ] **Step 6: Commit.**
      `feat(students): add final grade comment to int_students__final_grades`

### Task 3: `courses_gradescale_name` on `int_students__course_enrollments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml`

**Interfaces:**

- Consumes: `courses_gradescale_name` on the package
  `base_powerschool__course_enrollments` (Task 1), reaching kipptaf through the
  `int_powerschool__course_enrollments_union` `union_relations` view.
- Produces: `courses_gradescale_name` (string) on
  `int_students__course_enrollments`; null on Focus rows.

- [ ] **Step 1: Enumerate the column.** `powerschool_conformed` already passes
      it through `a.*`. In `unioned`, add `courses_gradescale_name` after
      `courses_gradescaleid_unweighted` in the PowerSchool branch and
      `cast(null as string) as courses_gradescale_name` at the same position in
      the Focus branch. Add it at the same position in the final select.
- [ ] **Step 2: Document the column** in the properties file (same wording as
      Task 1, plus "Null for Focus.").
- [ ] **Step 3: Seed the staging copies (shared write — ask first).** The
      kipptaf CI build reads `zz_stg_<district>_powerschool`, which lacks the
      new column. Per `src/dbt/kipptaf/CLAUDE.md` → _Single-PR cross-project
      workflow_ and `.claude/rules/dbt-models.md` → _Value-only vs column
      change_, for each of `kippnewark`, `kippcamden`, `kipppaterson`, one Bash
      call each, after the user authorizes:
      `uv run dbt build --select base_powerschool__sections+1 --project-dir src/dbt/<district> --target staging`
      Kippmiami no longer builds the package; `union_relations` null-fills its
      column.
- [ ] **Step 4: Force the kipptaf union wrapper modified** so CI rebuilds it
      instead of deferring: add a one-line SQL comment to
      `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__course_enrollments_union.sql`
      (`-- Refs #5704: rebuilt in CI to pick up courses_gradescale_name`).
- [ ] **Step 5: Compile against staging** (not a write):
      `uv run dbt compile --select int_powerschool__course_enrollments_union --project-dir src/dbt/kipptaf --target staging 2>&1 | tail -n 5`,
      then `grep -c courses_gradescale_name` on the compiled SQL. Expected: 4 or
      more.
- [ ] **Step 6: Build in dev with the staged upstream.**
      `uv run dbt build --select int_powerschool__course_enrollments_union int_students__course_enrollments --project-dir src/dbt/kipptaf 2>&1 | tail -n 30`
      (see `dbt-local-dev` for `--defer` traps first). Expected: PASS, the
      `cc_dcid` + `_dbt_source_project` uniqueness test included.
- [ ] **Step 7: Commit.**
      `feat(students): add course grade scale name to int_students__course_enrollments`

### Task 4: kipptaf `rpt_powerschool__stored_grades`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/powerschool/rpt_powerschool__stored_grades.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/powerschool/properties/rpt_powerschool__stored_grades.yml`

**Interfaces:**

- Consumes: Task 2 `comment_value`; Task 3 `courses_gradescale_name`.
- Produces: view `kipptaf_extracts.rpt_powerschool__stored_grades` with columns,
  in this order: `student_number`, `grade_level`, `schoolid`, `gpa_points`,
  `percent`, `grade`, `storecode`, `credit_type`, `course_number`,
  `course_name`, `teacher_name`, `sectionid`, `PotentialCrHrs`, `EarnedCrHrs`,
  `gradescale_name`, `schoolname`, `termid`, `Comment`, `code_location`,
  `school_level`.

| Column            | Source                                               |
| ----------------- | ---------------------------------------------------- |
| `student_number`  | `fg.student_number`                                  |
| `grade_level`     | `ce.students_grade_level`                            |
| `schoolid`        | `fg.schoolid`                                        |
| `gpa_points`      | `fg.term_grade_points`                               |
| `percent`         | `least(fg.term_percent_grade_adjusted, 100)`         |
| `grade`           | `fg.term_letter_grade_adjusted`                      |
| `storecode`       | `fg.storecode`                                       |
| `credit_type`     | `ce.courses_credittype`                              |
| `course_number`   | `ce.cc_course_number`                                |
| `course_name`     | `ce.courses_course_name`                             |
| `teacher_name`    | `ce.teacher_lastfirst`                               |
| `sectionid`       | `ce.cc_sectionid`                                    |
| `PotentialCrHrs`  | `0`                                                  |
| `EarnedCrHrs`     | `0`                                                  |
| `gradescale_name` | `ce.courses_gradescale_name`                         |
| `schoolname`      | `ce.school_name`                                     |
| `termid`          | `ce.sections_termid`                                 |
| `Comment`         | `if(ce.school_level = 'HS', fg.comment_value, null)` |
| `code_location`   | `fg._dbt_source_project`                             |
| `school_level`    | `ce.school_level`                                    |

- [ ] **Step 1: Write the unit test first** in the properties file, named
      `test_rpt_powerschool__stored_grades_filters`. Mock
      `int_students__final_grades` and `int_students__course_enrollments` (only
      the columns above plus `cc_dcid`, `is_homeroom`, `potential_credit_hours`,
      `_dbt_source_project`), one region, these rows keyed by `cc_dcid`: 1 — MS,
      graded 92.5, credit 1, comment `c1` → kept, `Comment` null; 2 — HS, graded
      104, credit 1, comment `c2` → kept, `percent = 100`, `Comment = 'c2'`; 3 —
      ES, graded 88, credit 1 → dropped; 4 — HS, `is_homeroom = true` → dropped;
      5 — MS, credit 0 → dropped; 6 — HS, adjusted percent null → dropped; 7 —
      enrollment row with no final-grade row → absent. Expected output: exactly
      rows 1 and 2, with `PotentialCrHrs = 0` and `EarnedCrHrs = 0`. Use made-up
      student numbers (`1001`, `1002`).
- [ ] **Step 2: Write the model** to the table above:
      `from     {{ ref("int_students__final_grades") }} as fg inner join     {{ ref("int_students__course_enrollments") }} as ce on fg.cc_dcid =     ce.cc_dcid and fg._dbt_source_project = ce._dbt_source_project`,
      the four baked-in filters in `where` (Global Constraints). If S10 flags
      `school_level in ('MS', 'HS')`, keep it: it is one comparison on one
      column.
- [ ] **Step 3: Write the properties file.** Contract columns with `data_type`
      (verify against `INFORMATION_SCHEMA.COLUMNS` after the first build);
      `config.meta.contains_pii: true` on the model;
      `dbt_utils.unique_combination_of_columns` on `code_location`,
      `student_number`, `sectionid`, `storecode`; `not_null` on
      `student_number`, `schoolid`, `storecode`, `course_number`, `sectionid`,
      `percent`, `grade`, `termid`. Model description: what the file is for,
      that `code_location` and `school_level` are filter columns not imported,
      and the quarterly runbook from the spec's _Quarterly runbook (kipptaf
      model description)_. No `#` issue refs in the description.
- [ ] **Step 4: Build.**
      `uv run dbt build --select rpt_powerschool__stored_grades --project-dir src/dbt/kipptaf 2>&1 | tail -n 30`
      Expected: unit test, contract, and data tests PASS. If the uniqueness test
      fails on `pgfinalgrades` duplicates, stop and report: the spec sends that
      fix upstream under #5221, not into this model.
- [ ] **Step 5: Region check.** BigQuery MCP on the dev view:
      `select code_location, school_level, count(*) ... group by     code_location, school_level`.
      Expected: only `kippnewark`, `kippcamden`, `kipppaterson`; only `MS`/`HS`;
      Paterson MS only.
- [ ] **Step 6: Commit.** `feat(extracts): add rpt_powerschool__stored_grades`

### Task 5: District wrappers and exposures

**Files (for each `<d>` in `kippnewark`, `kippcamden`, `kipppaterson`):**

- Create:
  `src/dbt/<d>/models/extracts/powerschool/rpt_powerschool__stored_grades.sql`
- Create:
  `src/dbt/<d>/models/extracts/powerschool/properties/rpt_powerschool__stored_grades.yml`
- Modify: `src/dbt/<d>/models/extracts/sources.yml`
- Modify: `src/dbt/<d>/models/exposures/powerschool.yml`

**Interfaces:**

- Consumes: Task 4's view and column list.
- Produces: `<d>_extracts.rpt_powerschool__stored_grades`, every Task 4 column
  except `code_location`.

- [ ] **Step 1: Wrapper SQL**, shaped like
      `rpt_powerschool__autocomm_teachers.sql` in the same folder: enumerate the
      19 columns (backtick none; `Comment` is not reserved),
      `from {{ source("kipptaf_extracts", "rpt_powerschool__stored_grades") }}`,
      `where code_location = '{{ project_name }}'`.
- [ ] **Step 2: Properties file**: the 19 columns with the same `data_type`s as
      Task 4, nothing else.
- [ ] **Step 3: Source entry** in `sources.yml`, copying the
      `rpt_powerschool__autocomm_teachers` entry with the name and asset key
      swapped.
- [ ] **Step 4: Exposure** `powerschool_stored_grades` per Global Constraints,
      appended to `powerschool.yml`.
- [ ] **Step 5: Parse and compile each district.**
      `uv run dbt compile --select rpt_powerschool__stored_grades --project-dir src/dbt/<d> 2>&1 | tail -n 10`
      Expected: compiles; compiled SQL names
      `kipptaf_extracts.rpt_powerschool__stored_grades` and the district name in
      the filter.
- [ ] **Step 6: Commit.**
      `feat(extracts): add district stored grades wrappers and exposures`

### Task 6: Parity, lint, and PR

**Files:**

- Modify: PR #5705 title and body only.

- [ ] **Step 1: Get the saved query.** Ask the user for the current saved
      query's SQL (the one in the spec's _Current state_). Save it to the
      session scratchpad, never the repo.
- [ ] **Step 2: Parity, Newark Q1 MS, current year.** BigQuery MCP: the dev
      kipptaf view filtered
      `code_location = 'kippnewark' and storecode = 'Q1'     and school_level = 'MS'`,
      projected `* except (code_location,     school_level, Comment)`, versus
      the saved query for the same scope. `except distinct` both directions.
      Expected: 0 rows each way. Repeat for Camden. Report counts only. Any
      difference: classify (homeroom `HR%` edge, grade-band vs `school_level`,
      upstream drift) and report to the user before going on.
- [ ] **Step 3: Paterson spot-check.** Row count of the view for `kipppaterson`
      Q1 MS equals the count of
      `kipppaterson_powerschool.base_powerschool__final_grades` rows passing the
      same four filters. Show five rows in the terminal only.
- [ ] **Step 4: Lint** every changed SQL, YAML, and markdown file:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
      with cwd inside the worktree. Fix findings.
- [ ] **Step 5: Push and update the PR.** `git -C <worktree> push`. Retitle
      #5705 `feat: PowerSchool stored grades extract`, and rewrite the body from
      `.github/pull_request_template.md`: spec, plan, build, the A2 `int_` edge
      with `Refs #6174` for the missing mart columns, the staging seeds run in
      Task 3, and parity results as counts. Keep `Refs #5704`.
- [ ] **Step 6: CI.** Watch Trunk and dbt Cloud CI, then process `claude-review`
      findings (`pr-ci-review`). If dbt Cloud CI fails with
      `Name courses_gradescale_name not found`, the staging seed or the Step 4
      wrapper comment in Task 3 did not take; read the error's compiled `from`
      clause to tell which.

## After merge (not part of this PR)

- Blank-comment test import: before the first live MS run, the user imports a
  small MS file with blank `Comment` into one region's PowerSchool and confirms
  rows load and existing comments stay. If not safe, the MS runbook goes back to
  `select * except (school_level, Comment)`.
- Move the extract onto the marts when #6174 lands.
- Drop the orphaned `kipptaf_powerschool` views (separate cleanup).
