# Gradebook Audit AY 2026-2027 Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all AY 2026-2027 changes to the gradebook audit pipeline:
remove Miami, add Paterson, remove FYI and Summative 200 flags, add a 7-day
grading grace period, and remove the exceptions suppression mechanism entirely.

**Architecture:** Six sequential tasks on a single feature branch. Each task
produces a working, committable state. Step 5 (QTD cumulative assignment count)
is blocked on an open format question (issue #3908) and is explicitly excluded.
Step 6 (anchor-row / "in the clear" redesign) is a separate future effort.

**Tech Stack:** dbt (BigQuery dialect), Google Sheets external tables, BigQuery
MCP for spot-checks, `uv run dbt` CLI, branch
`grangel/docs/claude-gradebook-audit-data-model`.

---

## File map

| File                                                                   | Task(s)  | Change type         |
| ---------------------------------------------------------------------- | -------- | ------------------- |
| `stg_google_sheets__gradebook_flags` (Google Sheet, not repo)          | 1, 2     | Sheet edits         |
| `stg_google_sheets__gradebook_expectations_assignments` (Google Sheet) | 1        | Sheet edits         |
| `int_tableau__gradebook_audit_teacher_scaffold.sql`                    | 2, 4     | SQL                 |
| `int_tableau__gradebook_audit_student_scaffold.sql`                    | 2        | SQL                 |
| `int_tableau__gradebook_audit_assignments_teacher.sql`                 | 2, 4     | SQL                 |
| `int_tableau__gradebook_audit_assignments_student.sql`                 | 2        | SQL                 |
| `int_tableau__gradebook_audit_categories_teacher.sql`                  | 2, 3, 4  | SQL                 |
| `int_tableau__gradebook_audit_flags.sql`                               | 2, 4     | SQL                 |
| `rpt_tableau__gradebook_audit.sql`                                     | 2, 4     | SQL                 |
| `stg_google_sheets__gradebook_exceptions.sql`                          | 4        | Delete              |
| `stg_google_sheets__gradebook_exceptions.yml`                          | 4        | Delete              |
| `sources-external.yml`                                                 | 4        | Remove source entry |
| YAML properties for each modified model                                | per task | Column removals     |

**SQL paths:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/<model>.sql` **YAML
paths:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/<model>.yml`
and
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_audit.yml`

**Build command for all tasks (run after every meaningful SQL change):**

```bash
uv run dbt build \
  --select int_tableau__gradebook_audit_teacher_scaffold+ \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state src/dbt/kipptaf/target/prod
```

---

## Task 1: Remove Miami + add Paterson (Google Sheets config only)

No SQL changes. These are operational sheet edits. Verify with dbt build.

**Files:** Google Sheets only (external — not in git)

- [ ] **Step 1.1: Remove Miami rows from `stg_google_sheets__gradebook_flags`**

  Open the `stg_google_sheets__gradebook_flags` Google Sheet. Delete all rows
  where `region = 'Miami'` for `academic_year = 2027` (and 2026 if any Miami
  2026 rows exist).

- [ ] **Step 1.2: Add Paterson rows to `stg_google_sheets__gradebook_flags`**

  > ⚠️ **Blocked on T&L confirmation.** Do not add rows until Teaching &
  > Learning provides the list of which flags apply to Paterson MS and HS for
  > AY 2027. Once confirmed, add one row per
  > `region=Paterson / school_level / code / audit_flag_name` combination
  > (matching the column schema of existing Camden/Newark rows for AY 2027).

- [ ] **Step 1.3: Remove Miami rows from
      `stg_google_sheets__gradebook_expectations_assignments`**

  Open the sheet. Delete all rows where `region = 'Miami'` for
  `academic_year = 2027`.

- [ ] **Step 1.4: Add Paterson rows to
      `stg_google_sheets__gradebook_expectations_assignments`**

  > ⚠️ **Blocked on T&L confirmation** (or PS-native source migration). Once
  > confirmed, add rows for all
  > `Paterson / school_level / quarter / week_number / W,H,F,S` combinations
  > with the expected assignment counts per category/week.

- [ ] **Step 1.5: Stage the modified external tables**

  After sheet edits, refresh the BigQuery external table definitions:

  ```bash
  uv run dbt run-operation stage_external_sources \
    --args '{"select": "google_sheets.src_google_sheets__gradebook_flags"}' \
    --project-dir src/dbt/kipptaf

  uv run dbt run-operation stage_external_sources \
    --args '{"select": "google_sheets.src_google_sheets__gradebook_expectations_assignments"}' \
    --project-dir src/dbt/kipptaf
  ```

- [ ] **Step 1.6: Rebuild staging models**

  ```bash
  uv run dbt build \
    --select stg_google_sheets__gradebook_flags \
              stg_google_sheets__gradebook_expectations_assignments \
    --project-dir src/dbt/kipptaf
  ```

- [ ] **Step 1.7: Build full audit pipeline and verify no Miami output**

  Run the full build command from the file map header. Then verify via BigQuery
  MCP:

  ```sql
  SELECT DISTINCT region, academic_year
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  ORDER BY 1, 2
  ```

  Expected: `Miami` absent; `Camden`, `Newark` present for 2027; `Paterson` if
  configured.

- [ ] **Step 1.8: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): remove Miami, add Paterson config — gradebook audit AY 2026-2027"
  ```

  _(No SQL files changed — this is a config-only state checkpoint.)_

---

## Task 2: Flag removals and Miami dead code cleanup

Removes FYI flags, Summative 200 flags, and all Miami-only dead-code SQL
branches. After this task the `student_course_category` and
`eoq_items_conduct_code` CTEs in `flags.sql` become empty and are deleted
entirely; `rpt.sql` shrinks from 5 to 4 UNION branches.

### 2a: Remove FYI flag `w_grade_inflation`

- [ ] **Step 2a.1: Remove `w_grade_inflation` from `student_scaffold.sql`**

  File: `int_tableau__gradebook_audit_student_scaffold.sql`

  In the **`student_scaffold` branch** (first UNION branch), delete this line
  (line 249):

  ```sql
  null as w_grade_inflation,
  ```

  In the **`student_category_scaffold` branch** (second UNION branch), replace:

  ```sql
  if(
      ge.assignment_category_code = 'W'
      and s.school_level_alt != 'ES'
      and abs(
          round(cg.category_quarter_average_all_courses, 2)
          - round(cg.category_quarter_percent_grade, 2)
      )
      >= 30,
      true,
      false
  ) as w_grade_inflation,
  ```

  with nothing (delete it).

- [ ] **Step 2a.2: Remove `w_grade_inflation` from `flags.sql`
      (student_course_category CTE)**

  File: `int_tableau__gradebook_audit_flags.sql`

  In the `student_course_category` CTE UNPIVOT list, delete
  `w_grade_inflation,`.

  _(The CTE will be fully removed in step 2f once all 4 of its flags are gone.)_

- [ ] **Step 2a.3: Remove `w_grade_inflation` column from YAML**

  File:
  `intermediate/properties/int_tableau__gradebook_audit_student_scaffold.yml`

  Find and delete the `w_grade_inflation` column entry. Repeat for
  `intermediate/properties/int_tableau__gradebook_audit_flags.yml`.

### 2b: Remove FYI flags `assign_s_hs/ms_score_not_conversion_chart_options`

- [ ] **Step 2b.1: Remove the two conversion-chart flag columns from
      `assignments_student.sql`**

  File: `int_tableau__gradebook_audit_assignments_student.sql`

  Find and delete these two `if(...)` expressions (they are in the final
  `select`):

  ```sql
  if(
      s.assignment_category_code = 'S'
      and s.school_level = 'MS'
      and not s.is_exempt
      and s.score_entered is not null
      and s.score_entered not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
      true,
      false
  ) as assign_s_ms_score_not_conversion_chart_options,

  if(
      s.assignment_category_code = 'S'
      and s.school_level = 'HS'
      and not s.is_ap_course
      and not s.is_exempt
      and s.score_entered is not null
      and s.score_entered not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
      true,
      false
  ) as assign_s_hs_score_not_conversion_chart_options,
  ```

- [ ] **Step 2b.2: Remove the two flags from the `student_unpivot` UNPIVOT in
      `flags.sql`**

  File: `int_tableau__gradebook_audit_flags.sql`, `student_unpivot` CTE (lines
  6–24).

  Delete these two lines from the UNPIVOT list:

  ```sql
  assign_s_ms_score_not_conversion_chart_options,
  assign_s_hs_score_not_conversion_chart_options
  ```

- [ ] **Step 2b.3: Remove columns from YAMLs**
  - `intermediate/properties/int_tableau__gradebook_audit_assignments_student.yml`:
    delete `assign_s_ms_score_not_conversion_chart_options` and
    `assign_s_hs_score_not_conversion_chart_options` column entries.
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`: same two
    entries.

### 2c: Remove Summative 200 flags (`qt_teacher_s_total_greater/less_200`)

- [ ] **Step 2c.1: Remove the two S-total flags from `categories_teacher.sql`**

  File: `int_tableau__gradebook_audit_categories_teacher.sql`

  In the final `select ... from final as f`, delete these two `if(...)`
  expressions (lines 264–278):

  ```sql
  if(
      f.assignment_category_code = 'S'
      and f.region_school_level != 'MiamiES'
      and f.sum_totalpointvalue_section_quarter_category > 200,
      true,
      false
  ) as qt_teacher_s_total_greater_200,

  if(
      f.assignment_category_code = 'S'
      and f.region_school_level != 'MiamiES'
      and f.sum_totalpointvalue_section_quarter_category < 200,
      true,
      false
  ) as qt_teacher_s_total_less_200,
  ```

- [ ] **Step 2c.2: Remove them from the `teacher_unpivot_cc` UNPIVOT in
      `flags.sql`**

  File: `int_tableau__gradebook_audit_flags.sql`, `teacher_unpivot_cc` CTE
  (lines 121–135).

  Delete:

  ```sql
  qt_teacher_s_total_greater_200,
  qt_teacher_s_total_less_200,
  ```

- [ ] **Step 2c.3: Remove columns from YAMLs**
  - `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`:
    delete `qt_teacher_s_total_greater_200` and `qt_teacher_s_total_less_200`
    entries.
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`: same.

### 2d: Remove Miami dead-code flags from `categories_teacher.sql`

- [ ] **Step 2d.1: Remove `qt_teacher_s_total_greater/less_100` (MiamiES) from
      `categories_teacher.sql`**

  File: `int_tableau__gradebook_audit_categories_teacher.sql`

  Delete these two `if(...)` expressions (lines 281–294):

  ```sql
  if(
      f.assignment_category_code = 'S'
      and f.region_school_level = 'MiamiES'
      and f.sum_totalpointvalue_section_quarter_category > 100,
      true,
      false
  ) as qt_teacher_s_total_greater_100,

  if(
      f.assignment_category_code = 'S'
      and f.region_school_level = 'MiamiES'
      and f.sum_totalpointvalue_section_quarter_category < 100,
      true,
      false
  ) as qt_teacher_s_total_less_100,
  ```

- [ ] **Step 2d.2: Remove them from the `teacher_unpivot_cc` UNPIVOT in
      `flags.sql`**

  Delete from the UNPIVOT list:

  ```sql
  qt_teacher_s_total_greater_100,
  qt_teacher_s_total_less_100,
  ```

- [ ] **Step 2d.3: Remove `s_max_score_greater_100` (Miami) from
      `assignments_teacher.sql`**

  File: `int_tableau__gradebook_audit_assignments_teacher.sql`

  Delete lines 76–83:

  ```sql
  if(
      sec.region = 'Miami'
      and sec.assignment_category_code = 'S'
      and a.totalpointvalue > 100,
      true,
      false
  ) as s_max_score_greater_100,
  ```

- [ ] **Step 2d.4: Remove `s_max_score_greater_100` from the
      `teacher_unpivot_cca` UNPIVOT in `flags.sql`**

  Delete from the UNPIVOT list:

  ```sql
  s_max_score_greater_100
  ```

- [ ] **Step 2d.5: Remove dead-code columns from YAMLs**
  - `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`:
    delete `qt_teacher_s_total_greater_100` and `qt_teacher_s_total_less_100`.
  - `intermediate/properties/int_tableau__gradebook_audit_assignments_teacher.yml`:
    delete `s_max_score_greater_100`.
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`: delete all
    four S-total flags and `s_max_score_greater_100`.

### 2e: Remove Miami dead-code flags from `student_scaffold.sql`

The flags below are defined only for Miami students. Once Miami is gone from the
flags sheet they silently produce no rows, but the dead boolean columns remain.
Remove them.

Flags to remove from the **`student_scaffold` branch** (branch 1):
`qt_comment_missing`, `qt_g1_g8_conduct_code_missing`,
`qt_g1_g8_conduct_code_incorrect`, `qt_kg_conduct_code_missing`,
`qt_kg_conduct_code_incorrect`, `qt_kg_conduct_code_not_hr`.

Null placeholders to remove from the **`student_category_scaffold` branch**
(branch 2): `null as qt_comment_missing`,
`null as qt_g1_g8_conduct_code_missing`,
`null as qt_g1_g8_conduct_code_incorrect`, `null as qt_kg_conduct_code_missing`,
`null as qt_kg_conduct_code_incorrect`, `null as qt_kg_conduct_code_not_hr`.

Flags to remove from the **`student_category_scaffold` branch** (branch 2):
`qt_effort_grade_missing`, `qt_formative_grade_missing`,
`qt_summative_grade_missing`.

Null placeholders to remove from the **`student_scaffold` branch** (branch 1):
`null as qt_effort_grade_missing`, `null as qt_formative_grade_missing`,
`null as qt_summative_grade_missing`.

_(Already removed `null as w_grade_inflation` in step 2a.1.)_

- [ ] **Step 2e.1: Remove Miami boolean flags from `student_scaffold` branch**

  File: `int_tableau__gradebook_audit_student_scaffold.sql` — first UNION branch
  (lines 186–252).

  Delete these six `if(...)` expressions:

  ```sql
  if(
      sec.region_school_level = 'MiamiES'
      and sec.is_quarter_end_date_range
      and qg.quarter_comment_value is null,
      true,
      false
  ) as qt_comment_missing,

  if(
      s.region = 'Miami'
      and s.grade_level != 0
      and sec.is_quarter_end_date_range
      and ce.courses_course_name != 'HR'
      and qg.quarter_conduct is null,
      true,
      false
  ) as qt_g1_g8_conduct_code_missing,

  if(
      s.region = 'Miami'
      and s.grade_level != 0
      and sec.is_quarter_end_date_range
      and ce.courses_course_name != 'HR'
      and qg.quarter_conduct not in ('A', 'B', 'C', 'D', 'E', 'F'),
      true,
      false
  ) as qt_g1_g8_conduct_code_incorrect,

  if(
      sec.region_school_level = 'MiamiES'
      and s.grade_level = 0
      and sec.is_quarter_end_date_range
      and ce.courses_course_name = 'HR'
      and qg.quarter_conduct is null,
      true,
      false
  ) as qt_kg_conduct_code_missing,

  if(
      sec.region_school_level = 'MiamiES'
      and s.grade_level = 0
      and sec.is_quarter_end_date_range
      and ce.courses_course_name = 'HR'
      and qg.quarter_conduct not in ('E', 'G', 'S', 'M'),
      true,
      false
  ) as qt_kg_conduct_code_incorrect,

  if(
      sec.region_school_level = 'MiamiES'
      and s.grade_level = 0
      and sec.is_quarter_end_date_range
      and ce.courses_course_name != 'HR'
      and qg.quarter_conduct is not null,
      true,
      false
  ) as qt_kg_conduct_code_not_hr,
  ```

  Also delete these null placeholders at lines 249–252:

  ```sql
  null as qt_effort_grade_missing,
  null as qt_formative_grade_missing,
  null as qt_summative_grade_missing,
  ```

- [ ] **Step 2e.2: Remove Miami null placeholders + flags from
      `student_category_scaffold` branch**

  File: same — second UNION branch (lines 375–424).

  Delete these null placeholders:

  ```sql
  null as qt_comment_missing,
  null as qt_g1_g8_conduct_code_missing,
  null as qt_g1_g8_conduct_code_incorrect,
  null as qt_kg_conduct_code_missing,
  null as qt_kg_conduct_code_incorrect,
  null as qt_kg_conduct_code_not_hr,
  ```

  Delete these three Miami-only `if(...)` expressions:

  ```sql
  if(
      s.region = 'Miami'
      and ge.assignment_category_code = 'W'
      and cg.category_quarter_percent_grade is null
      and sec.is_quarter_end_date_range,
      true,
      false
  ) as qt_effort_grade_missing,

  if(
      s.region_school_level = 'MiamiES'
      and ge.assignment_category_code = 'F'
      and cg.category_quarter_percent_grade is null
      and sec.is_quarter_end_date_range,
      true,
      false
  ) as qt_formative_grade_missing,

  if(
      s.region_school_level = 'MiamiES'
      and sec.credit_type not in ('ENG', 'MATH')
      and ge.assignment_category_code = 'S'
      and cg.category_quarter_percent_grade is null
      and sec.is_quarter_end_date_range,
      true,
      false
  ) as qt_summative_grade_missing,
  ```

- [ ] **Step 2e.3: Remove dead-code columns from student_scaffold YAML**

  File:
  `intermediate/properties/int_tableau__gradebook_audit_student_scaffold.yml`

  Delete column entries for: `qt_comment_missing`,
  `qt_g1_g8_conduct_code_missing`, `qt_g1_g8_conduct_code_incorrect`,
  `qt_kg_conduct_code_missing`, `qt_kg_conduct_code_incorrect`,
  `qt_kg_conduct_code_not_hr`, `qt_effort_grade_missing`,
  `qt_formative_grade_missing`, `qt_summative_grade_missing`.

### 2f: Remove empty CTEs from `flags.sql` and their UNION branches from `rpt.sql`

After steps 2a–2e:

- `student_course_category` CTE UNPIVOT has zero flags left → remove the entire
  CTE and its UNION branch.
- `eoq_items_conduct_code` CTE UNPIVOT has zero flags left → remove the entire
  CTE and its UNION branch.

- [ ] **Step 2f.1: Remove `student_course_category` CTE from `flags.sql`**

  File: `int_tableau__gradebook_audit_flags.sql`

  Delete the entire `student_course_category` CTE (lines 248–284 in the original
  — after the `/* w_grade_inflation... */` comment block through
  `from student_course_category`).

- [ ] **Step 2f.2: Remove `eoq_items_conduct_code` CTE from `flags.sql`**

  Delete the entire `eoq_items_conduct_code` CTE (lines 197–245 in the
  original).

- [ ] **Step 2f.3: Remove the removed flags from the other UNPIVOT lists in
      `flags.sql`**

  In `eoq_items` UNPIVOT list, delete:

  ```sql
  qt_comment_missing,
  qt_g1_g8_conduct_code_missing,
  qt_g1_g8_conduct_code_incorrect,
  ```

  Remaining in `eoq_items` UNPIVOT: `qt_es_comment_missing`,
  `qt_grade_70_comment_missing`, `qt_percent_grade_greater_100`,
  `qt_student_is_ada_80_plus_gpa_less_2`.

- [ ] **Step 2f.4: Remove `student_course_category` UNION branch from
      `rpt.sql`**

  File: `rpt_tableau__gradebook_audit.sql`

  Delete the second UNION ALL block — the one with
  `where t.cte_grouping = 'student_course_category'`. This is the full block
  from `union all` (after branch 1) through `not t.is_current_week` including
  the following `union all` separator.

- [ ] **Step 2f.5: Remove corresponding YAML entries from flags and rpt YAMLs**

  The flags.sql and rpt.sql YAMLs may describe columns that carried
  `student_course_category` data. Remove any column description that exclusively
  references this CTE grouping, if any are present in the YAML.

### 2g: Simplify the Miami EOQ window in `teacher_scaffold.sql`

- [ ] **Step 2g.1: Remove the Miami-specific `is_quarter_end_date_range`
      clause**

  File: `int_tableau__gradebook_audit_teacher_scaffold.sql`, `school_level_mod`
  CTE (lines 164–193).

  Replace the entire CASE expression with:

  ```sql
  case
      when
          tw.school_level = 'HS'
          and tw.`quarter` = 'Q3'
          and current_date(
              '{{ var("local_timezone") }}'
          ) between (tw.quarter_end_date_insession + interval 9 day) and (
              tw.quarter_end_date_insession + interval 20 day
          )
      then true
      when tw.school_level = 'HS' and tw.`quarter` = 'Q3'
      then false
      when
          current_date(
              '{{ var("local_timezone") }}'
          ) between (tw.quarter_end_date_insession - interval 5 day) and (
              tw.quarter_end_date_insession + interval 14 day
          )
      then true
      else false
  end as is_quarter_end_date_range,
  ```

  _(Removed the first `when tw.region = 'Miami' ...` clause and the
  `and tw.region != 'Miami'` guard on the last `when`.)_

### 2h: Build and verify Task 2 changes

- [ ] **Step 2h.1: Run dbt build**

  Run the full build command from the file map header.

  Expected: all models build cleanly. If a contract enforcement error fires
  (`column not found`), find the corresponding YAML and remove the deleted
  column there too.

- [ ] **Step 2h.2: Spot-check removed flags are gone**

  Via BigQuery MCP:

  ```sql
  SELECT DISTINCT audit_flag_name
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  ORDER BY 1
  ```

  Expected absent: `w_grade_inflation`,
  `assign_s_hs_score_not_conversion_chart_options`,
  `assign_s_ms_score_not_conversion_chart_options`,
  `qt_teacher_s_total_greater_200`, `qt_teacher_s_total_less_200`,
  `qt_teacher_s_total_greater_100`, `qt_teacher_s_total_less_100`,
  `s_max_score_greater_100`, `qt_comment_missing`,
  `qt_g1_g8_conduct_code_missing`, `qt_g1_g8_conduct_code_incorrect`,
  `qt_kg_conduct_code_missing`, `qt_kg_conduct_code_incorrect`,
  `qt_kg_conduct_code_not_hr`, `qt_effort_grade_missing`,
  `qt_formative_grade_missing`, `qt_summative_grade_missing`.

- [ ] **Step 2h.3: Remove deactivated rows from
      `stg_google_sheets__gradebook_flags`**

  Open the sheet. Delete any remaining rows for the flags listed in step 2h.2.
  These flags are no longer in the SQL so any rows for them are dead config.

- [ ] **Step 2h.4: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): remove FYI flags, Summative 200, and Miami dead code — gradebook audit AY 2026-2027"
  ```

---

## Task 3: 7-day grace period for percent-graded flags

`w/h/f/s_percent_graded_min_not_met` should only fire for assignments that have
been due for at least 7 days. Currently the percent-graded calculation includes
all assignments in the week window regardless of how recently they were due.

**File:** `int_tableau__gradebook_audit_categories_teacher.sql`

The `total_expected_section_quarter_week_category` and
`total_expected_scored_section_quarter_week_category` window sums in the
`assignments` CTE are fed by `asg.n_expected` / `asg.n_expected_scored` (from
`assignment_score_rollup`). `a.duedate` is available in the `assignments` CTE
via the `int_powerschool__gradebook_assignments` join. Use conditional
aggregation to exclude assignments due within the last 7 days.

- [ ] **Step 3.1: Add grace-period filter to the two window sums in the
      `assignments` CTE**

  File: `int_tableau__gradebook_audit_categories_teacher.sql`, `assignments` CTE
  (lines 44–61).

  Replace:

  ```sql
  sum(asg.n_expected) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.week_number_quarter,
          sec.assignment_category_code
  ) as total_expected_section_quarter_week_category,

  sum(asg.n_expected_scored) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.week_number_quarter,
          sec.assignment_category_code
  ) as total_expected_scored_section_quarter_week_category,
  ```

  with:

  ```sql
  sum(
      if(
          a.duedate
          <= date_sub(current_date('{{ var("local_timezone") }}'), interval 7 day),
          asg.n_expected,
          null
      )
  ) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.week_number_quarter,
          sec.assignment_category_code
  ) as total_expected_section_quarter_week_category,

  sum(
      if(
          a.duedate
          <= date_sub(current_date('{{ var("local_timezone") }}'), interval 7 day),
          asg.n_expected_scored,
          null
      )
  ) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.week_number_quarter,
          sec.assignment_category_code
  ) as total_expected_scored_section_quarter_week_category,
  ```

  **Note:** When `a` is null (no assignment matched the week window),
  `a.duedate` is null, the `if` condition is null, and `if(null, ...)` returns
  null — this is correct. When all assignments in a week are within the 7-day
  grace period, `total_expected_section_quarter_week_category` sums to null,
  `safe_divide(null, null) = null`, and the percent-graded flag evaluates to
  false. That is the intended behavior.

- [ ] **Step 3.2: Run dbt build**

  Run the full build command from the file map header.

- [ ] **Step 3.3: Spot-check the grace period is working**

  Via BigQuery MCP — find any class where `w_percent_graded_min_not_met` fired
  and check that the flagged assignment's `duedate` is more than 7 days in the
  past:

  ```sql
  SELECT
    region,
    school,
    teacher_name,
    assignment_category_code,
    audit_qt_week_number,
    percent_graded_for_quarter_week_class,
    flag_value,
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE audit_flag_name = 'w_percent_graded_min_not_met'
    AND flag_value = 1
  LIMIT 20
  ```

- [ ] **Step 3.4: Commit**

  ```bash
  git commit -m "feat(dbt): add 7-day grace period for percent-graded flags"
  ```

---

## Task 4: Remove the exceptions mechanism entirely

T&L has decided to eliminate the exceptions suppression table. Remove
`stg_google_sheets__gradebook_exceptions` and all 15+ LEFT JOINs to it across
five intermediate models.

### 4a: `int_tableau__gradebook_audit_teacher_scaffold.sql`

Three sets of exception joins to remove: two in `sections`, three in the
`teacher_category_scaffold` branch of `final`, two in the outer `select`.

- [ ] **Step 4a.1: Remove exception joins from the `sections` CTE**

  File: `int_tableau__gradebook_audit_teacher_scaffold.sql`, `sections` CTE
  (lines 36–57).

  Delete both LEFT JOINs to `stg_google_sheets__gradebook_exceptions` (`e1` and
  `e2`) and the two `and e1.include_row is null and e2.include_row is null`
  conditions from the WHERE clause:

  ```sql
  -- DELETE from lines 36–57:
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
      on s.terms_academic_year = e1.academic_year
      and s.sections_course_number = e1.course_number
      and e1.view_name = 'teacher_scaffold'
      and e1.cte = 'sections'
      and e1.school_id is null
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
      on s.terms_academic_year = e2.academic_year
      and s.sections_schoolid = e2.school_id
      and s.sections_course_number = e2.course_number
      and e2.view_name = 'teacher_scaffold'
      and e2.cte = 'sections'
      and e2.school_id is not null

  -- DELETE from WHERE (lines 56–57):
  and e1.include_row is null
  and e2.include_row is null
  ```

- [ ] **Step 4a.2: Remove exception joins from the `teacher_category_scaffold`
      branch of `final`**

  Delete all three LEFT JOINs (`e1`, `e2`, `e3`) and the WHERE condition they
  feed (lines 250–280):

  ```sql
  -- DELETE three left join blocks (e1, e2, e3) and:
  where
      e1.include_row is null and e2.include_row is null and e3.include_row is null
  ```

- [ ] **Step 4a.3: Remove exception joins from the outer `select`**

  Delete the two LEFT JOINs at the end of the file (lines 295–316) and the WHERE
  clause they feed:

  ```sql
  -- DELETE:
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
      on f.academic_year = e1.academic_year
      ...
      and e1.view_name = 'teacher_scaffold'
      and e1.cte is null
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
      on f.academic_year = e2.academic_year
      ...
      and e2.view_name = 'teacher_scaffold'
      and e2.cte is null
  where e1.include_row is null and e2.include_row is null
  ```

### 4b: `int_tableau__gradebook_audit_assignments_teacher.sql`

- [ ] **Step 4b.1: Remove exception join and simplify conditional columns**

  File: `int_tableau__gradebook_audit_assignments_teacher.sql`

  Delete the LEFT JOIN to `stg_google_sheets__gradebook_exceptions` (lines
  110–120):

  ```sql
  -- DELETE:
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
      on sec.academic_year = e.academic_year
      and sec.region = e.region
      and sec.course_number = e.course_number
      and sec.is_quarter_end_date_range = e.is_quarter_end_date_range
      and e.view_name = 'assignments_teacher'
      and e.cte is null
      and e.course_number is not null
      and e.is_quarter_end_date_range is not null
  ```

  Then replace every `if(e.include_row is null, asg.<col>, null) as <col>` with
  the plain column. Lines 44–58 become:

  ```sql
  asg.n_students,
  asg.n_late,
  asg.n_exempt,
  asg.n_missing,
  asg.n_academic_dishonesty,
  asg.n_null,
  asg.n_is_null_missing,
  asg.n_is_null_not_missing,
  asg.n_expected,
  asg.n_expected_scored,
  asg.teacher_avg_score_for_assign_per_class_section_and_assign_id,
  ```

### 4c: `int_tableau__gradebook_audit_categories_teacher.sql`

- [ ] **Step 4c.1: Remove exception join from `assignment_score_rollup` CTE**

  File: `int_tableau__gradebook_audit_categories_teacher.sql`,
  `assignment_score_rollup` CTE (lines 11–22).

  Delete the LEFT JOIN to `stg_google_sheets__gradebook_exceptions` (`e1`) and
  the `where e1.include_row is null` condition:

  ```sql
  -- DELETE:
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
      on s.academic_year = e1.academic_year
      and s.region = e1.region
      and s.school_level = e1.school_level
      and s.credit_type = e1.credit_type
      and e1.view_name = 'categories_teacher'
      and e1.cte = 'assignment_score_rollup'
      and e1.credit_type is not null
  where e1.include_row is null
  ```

- [ ] **Step 4c.2: Remove the final-level exception join**

  Delete the LEFT JOIN at the bottom of the file (lines 298–306) and the
  `where e.include_row is null` clause:

  ```sql
  -- DELETE:
  left join
      {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
      on f.academic_year = e.academic_year
      and f.region = e.region
      and f.course_number = e.course_number
      and f.is_quarter_end_date_range = e.is_quarter_end_date_range
      and e.view_name = 'categories_teacher'
      and e.cte is null
      and e.is_quarter_end_date_range is not null
  where e.include_row is null
  ```

### 4d: `int_tableau__gradebook_audit_flags.sql`

Remove exception joins from the four remaining CTEs (`student_unpivot`,
`teacher_unpivot_cca`, `teacher_unpivot_cc`, `eoq_items`). The
`student_course_category` and `eoq_items_conduct_code` CTEs were already deleted
in Task 2.

- [ ] **Step 4d.1: Remove three exception joins from `student_unpivot` CTE**

  Delete the three LEFT JOINs (`e1`, `e2`, `e3`) and update the WHERE to remove
  the three `e*.include_row is null` conditions. The WHERE should just be:

  ```sql
  where
      audit_flag_value = true
  ```

  Wait — actually look at the original `student_unpivot` WHERE (line 68–69):
  `where e1.include_row is null and e2.include_row is null and e3.include_row is null`

  This was the ONLY filter. UNPIVOT produces rows where `audit_flag_value` is
  any value (both true and false). After removing the exceptions, the CTE should
  still only surface rows where the flag is true, which happens via the INNER
  JOIN to `stg_google_sheets__gradebook_flags` (which is an allowlist, not a
  suppressor). The `audit_flag_value = 1` filter is applied later in `rpt.sql`'s
  `valid_flags` CTE, not here. So after removing the exception joins, the WHERE
  clause can be removed entirely (or changed to just remove the exception
  conditions). The UNPIVOT + INNER JOIN to flags is the correct filter.

  Final `student_unpivot` CTE structure after this step:

  ```sql
  student_unpivot as (
      select u.*, f.cte_grouping, f.audit_category, f.code_type,

      from
          {{ ref("int_tableau__gradebook_audit_assignments_student") }} unpivot (
              audit_flag_value for audit_flag_name in (
                  assign_null_score,
                  assign_score_above_max,
                  assign_w_score_less_5,
                  assign_h_score_less_5,
                  assign_f_score_less_5,
                  assign_w_missing_score_not_5,
                  assign_f_missing_score_not_5,
                  assign_h_missing_score_not_5,
                  assign_w_missing_score_not_0,
                  assign_f_missing_score_not_0,
                  assign_h_missing_score_not_0,
                  assign_s_missing_score_not_0,
                  assign_s_score_less_50p,
                  assign_s_hs_score_less_50p
              )
          ) as u
      inner join
          {{ ref("stg_google_sheets__gradebook_flags") }} as f
          on u.academic_year = f.academic_year
          and u.region = f.region
          and u.school_level = f.school_level
          and u.assignment_category_code = f.code
          and u.audit_flag_name = f.audit_flag_name
          and f.cte_grouping = 'assignment_student'
  ),
  ```

- [ ] **Step 4d.2: Remove two exception joins from `teacher_unpivot_cca` CTE**

  Delete `e1` and `e2` LEFT JOINs and the
  `where e1.include_row is null and e2.include_row is null` clause entirely.

- [ ] **Step 4d.3: Remove one exception join from `teacher_unpivot_cc` CTE**

  Delete the `e` LEFT JOIN and the `where e.include_row is null` clause.

- [ ] **Step 4d.4: Remove one exception join from `eoq_items` CTE**

  Delete the `e1` LEFT JOIN and the `where e1.include_row is null` clause.

### 4e: Delete the exceptions staging model and source entry

- [ ] **Step 4e.1: Delete the staging model SQL and YAML**

  ```bash
  rm src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gradebook_exceptions.sql
  rm src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_exceptions.yml
  ```

- [ ] **Step 4e.2: Remove the source entry from `sources-external.yml`**

  File: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (lines
  277–292 approx.)

  Delete the entire `src_google_sheets__gradebook_exceptions` source entry:

  ```yaml
  # DELETE this block:
  - name: src_google_sheets__gradebook_exceptions
    external: ...
    columns: ...
  ```

### 4f: Build and verify Task 4 changes

- [ ] **Step 4f.1: Run dbt build**

  Run the full build command from the file map header.

  If the build references `stg_google_sheets__gradebook_exceptions` anywhere
  (compile error or "node not found"), you missed a join site. Search for
  remaining refs:

  ```bash
  grep -rn "gradebook_exceptions" src/dbt/kipptaf/models/ --include="*.sql"
  ```

  Expected: zero results.

- [ ] **Step 4f.2: Spot-check output row counts are similar to
      pre-exceptions-removal**

  Via BigQuery MCP:

  ```sql
  SELECT
    region,
    school_level,
    audit_flag_name,
    count(*) as n_rows,
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE flag_value = 1
  GROUP BY 1, 2, 3
  ORDER BY 1, 2, 3
  ```

  Row counts should be similar to (or slightly higher than) pre-exceptions
  results — removing suppressions means some previously-suppressed rows now
  appear. Verify with T&L before merging if any unexpected spikes appear.

- [ ] **Step 4f.3: Commit**

  ```bash
  git commit -m "feat(dbt): remove gradebook exceptions mechanism — AY 2026-2027"
  ```

---

## Tasks 5 and 6 (out of scope for this plan)

**Task 5 — QTD cumulative assignment count:** Blocked on open format question in
issue #3908. Must resolve whether
`stg_google_sheets__gradebook_expectations_assignments` stores cumulative or
per-week targets before implementation can be specced.

**Task 6 — Anchor-row / "in the clear" redesign:** Major structural change to
`rpt_tableau__gradebook_audit.sql`. Needs separate spec and plan.

---

## Self-review checklist

- [x] Spec coverage: all items from the "Scope of work" section of issue #3908
      that are in scope for this plan have a corresponding task (Miami removal,
      Paterson config, FYI flags, Summative 200, Miami dead code, grace period,
      exceptions removal).
- [x] Placeholder scan: no TBD steps. Tasks 1.2 and 1.4 are explicitly blocked
      on T&L confirmation — that is a real external dependency, not a plan gap.
- [x] Type consistency: all SQL changes are additive deletes (removing
      columns/CTEs); no new columns or type changes introduced.
- [x] Steps 5 and 6 are explicitly excluded with documented reasons.
