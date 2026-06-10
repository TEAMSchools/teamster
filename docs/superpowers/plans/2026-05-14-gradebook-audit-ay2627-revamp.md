# Gradebook Audit AY 2026-2027 Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all AY 2026-2027 changes to the gradebook audit pipeline:
annual config rollover for Newark, Camden, and Paterson; remove Miami; remove
FYI, Summative 200, and ADA/GPA flags; add a 7-day grading grace period; add QTD
cumulative assignment count; and remove the exceptions suppression mechanism.

**Architecture:** Task 1 is Google Sheets config only — creating AY 2026 flag
rows while omitting deprecated ones deactivates those flags immediately without
touching SQL. Task 2 replaces the deprecated Google Sheet expectations source
with a PS-native intermediate model (Newark only to start). Tasks 3–6 are SQL
cleanup and logic changes. Task 5 (QTD) is blocked on PR #4077 (PS plugin
integration) landing. Task 7 is the post-merge doc/skill update. Task 8
(anchor-row redesign) is in scope but implementation details are TBD.

**Tech Stack:** dbt (BigQuery dialect), Google Sheets external tables, BigQuery
MCP for spot-checks, `uv run dbt` CLI, branch
`grangel/docs/claude-gradebook-audit-data-model`.

---

## File map

### Google Sheets (external — not in git)

| File                                 | Task | Change      |
| ------------------------------------ | ---- | ----------- |
| `stg_google_sheets__gradebook_flags` | 1    | Sheet edits |

### SQL — prerequisite models (powerschool package)

| File                                                          | Task | Change                                                       |
| ------------------------------------------------------------- | ---- | ------------------------------------------------------------ |
| `base_powerschool__sections.sql`                              | 3    | Add `school_abbreviation` and `school_level` fields          |
| `int_powerschool__gradebook_assignments_scores.sql` (kipptaf) | 4    | Fix Sumner G5 `school_level` override — `= 2025` → `>= 2025` |

### SQL — new models

| File                                                     | Task | Change                                                               |
| -------------------------------------------------------- | ---- | -------------------------------------------------------------------- |
| `int_powerschool__u_expectations[_unpivot].sql`          | 2    | Create                                                               |
| `int_powerschool__u_expectations[_unpivot].yml`          | 2    | Create                                                               |
| `int_powerschool__gradebook_assignment_score_rollup.sql` | 6d   | Create — score rollup extracted from inline CTE; shared by 6d and 6e |
| `int_powerschool__gradebook_assignment_score_rollup.yml` | 6d   | Create                                                               |

### SQL — modified models

| File                                                   | Task(s)  | Change                                                                             |
| ------------------------------------------------------ | -------- | ---------------------------------------------------------------------------------- |
| `int_tableau__gradebook_audit_teacher_scaffold.sql`    | 2, 3, 6  | SQL                                                                                |
| `int_tableau__gradebook_audit_student_scaffold.sql`    | 2, 3     | SQL                                                                                |
| `int_tableau__gradebook_audit_assignments_teacher.sql` | 3, 6     | SQL                                                                                |
| `int_tableau__gradebook_audit_assignments_student.sql` | 3        | SQL                                                                                |
| `int_tableau__gradebook_audit_categories_teacher.sql`  | 3, 4, 6  | SQL                                                                                |
| `int_tableau__gradebook_audit_flags.sql`               | 3, 6     | SQL                                                                                |
| `rpt_tableau__gradebook_audit.sql`                     | 3, 6     | SQL                                                                                |
| `rpt_tableau__gradebook_es_comments.sql`               | 6h.7     | Complete rewrite — standalone CTE-based model; ES removed from main flags pipeline |
| `int_extracts__student_enrollments.sql`                | 3        | Add boolean column                                                                 |
| `rpt_tableau__gradebook_gpa.sql`                       | 3        | Add boolean, remove Paterson filter                                                |
| YAML properties for each modified model                | per task | Column additions / removals                                                        |

### SQL — disabled models

Deprecated sources are disabled (`config: enabled: false`) rather than deleted,
pending any new operational decisions taking effect July 1st.

| File                                                        | Task | Change                       |
| ----------------------------------------------------------- | ---- | ---------------------------- |
| `stg_google_sheets__gradebook_expectations_assignments.yml` | 2    | Set `config: enabled: false` |
| `stg_google_sheets__gradebook_exceptions.yml`               | 6    | Set `config: enabled: false` |

### Documentation

| File                                           | Task | Change                                                      |
| ---------------------------------------------- | ---- | ----------------------------------------------------------- |
| `rpt_tableau__gradebook_audit.sql`             | 8    | Anchor-row redesign (TBD)                                   |
| `docs/reference/gradebook-audit-data-model.md` | 7    | Add AY 2026-2027 section at top; archive AY 2025-2026 below |

**SQL paths:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/<model>.sql`

**YAML paths:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/<model>.yml`
and
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_audit.yml`

**Build strategy: one model at a time.**

After each model change, build and verify only the model just modified — never
the downstream chain. Downstream models reference columns that may not yet exist
in the refactored upstream, so cascading builds will fail mid-refactor. The full
downstream chain is only valid after every model in the lineage has been
updated.

```bash
# Standard per-model build (substitute <model_name> at each step):
uv run dbt build \
  --select <model_name> \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state src/dbt/kipptaf/target/prod
```

---

## Task 1: Google Sheets — gradebook_flags annual rollover

All changes are in the `stg_google_sheets__gradebook_flags` Google Sheet. No SQL
changes.

**How the rollover works:** The AY 2026 rows have been pre-generated from AY
2025 data with deprecated flags excluded and Paterson rows derived from Newark.
Copy the table in step 1.0 and paste directly into the Google Sheet — do not
manually copy rows. The query that produced this table is documented in the
[Start-of-year procedure](../../reference/gradebook-audit-data-model.md) section
of the reference doc for future years.

**Files:** Google Sheets only (external — not in git)

- [x] **Step 1.0: Paste the pre-generated AY 2026 rows into the sheet**

  Copy everything in the code block below (including the header row) and paste
  into the first empty row of `stg_google_sheets__gradebook_flags`. Google
  Sheets will split the tabs into columns automatically. Column order matches
  the sheet: A=academic_year, B=region, C=school_level, D=grade_level (blank),
  E=code_type, F=code, G=audit_category, H=audit_flag_name, I=cte_grouping.

  ```text
  academic_year	region	school_level	grade_level	code_type	code	audit_category	audit_flag_name	cte_grouping
  2026	Camden	ES		Quarter	Q1	Comments	qt_es_comment_missing	student_course
  2026	Camden	ES		Quarter	Q2	Comments	qt_es_comment_missing	student_course
  2026	Camden	ES		Quarter	Q3	Comments	qt_es_comment_missing	student_course
  2026	Camden	ES		Quarter	Q4	Comments	qt_es_comment_missing	student_course
  2026	Camden	HS		Gradebook Category	F	Data Entry	assign_f_missing_score_not_0	assignment_student
  2026	Camden	HS		Gradebook Category	F	Data Entry	assign_f_score_less_5	assignment_student
  2026	Camden	HS		Gradebook Category	F	Data Entry	assign_null_score	assignment_student
  2026	Camden	HS		Gradebook Category	F	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	HS		Gradebook Category	F	Setup	f_assign_max_score_not_10	class_category_assignment
  2026	Camden	HS		Gradebook Category	F	Updated	f_expected_assign_count_not_met	class_category
  2026	Camden	HS		Gradebook Category	F	Data Entry	f_percent_graded_min_not_met	class_category
  2026	Camden	HS		Gradebook Category	H	Data Entry	assign_h_missing_score_not_0	assignment_student
  2026	Camden	HS		Gradebook Category	H	Data Entry	assign_h_score_less_5	assignment_student
  2026	Camden	HS		Gradebook Category	H	Data Entry	assign_null_score	assignment_student
  2026	Camden	HS		Gradebook Category	H	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	HS		Gradebook Category	H	Setup	h_assign_max_score_not_10	class_category_assignment
  2026	Camden	HS		Gradebook Category	H	Updated	h_expected_assign_count_not_met	class_category
  2026	Camden	HS		Gradebook Category	H	Data Entry	h_percent_graded_min_not_met	class_category
  2026	Camden	HS		Gradebook Category	S	Data Entry	assign_null_score	assignment_student
  2026	Camden	HS		Gradebook Category	S	Data Entry	assign_s_hs_score_less_50p	assignment_student
  2026	Camden	HS		Gradebook Category	S	Data Entry	assign_s_missing_score_not_0	assignment_student
  2026	Camden	HS		Gradebook Category	S	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	HS		Gradebook Category	S	Updated	s_expected_assign_count_not_met	class_category
  2026	Camden	HS		Gradebook Category	S	Data Entry	s_percent_graded_min_not_met	class_category
  2026	Camden	HS		Gradebook Category	W	Data Entry	assign_null_score	assignment_student
  2026	Camden	HS		Gradebook Category	W	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	HS		Gradebook Category	W	Data Entry	assign_w_missing_score_not_0	assignment_student
  2026	Camden	HS		Gradebook Category	W	Data Entry	assign_w_score_less_5	assignment_student
  2026	Camden	HS		Gradebook Category	W	Setup	w_assign_max_score_not_10	class_category_assignment
  2026	Camden	HS		Gradebook Category	W	Updated	w_expected_assign_count_not_met	class_category
  2026	Camden	HS		Gradebook Category	W	Data Entry	w_percent_graded_min_not_met	class_category
  2026	Camden	HS		Quarter	Q1	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	HS		Quarter	Q1	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	HS		Quarter	Q2	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	HS		Quarter	Q2	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	HS		Quarter	Q3	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	HS		Quarter	Q3	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	HS		Quarter	Q4	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	HS		Quarter	Q4	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	MS		Gradebook Category	F	Data Entry	assign_f_missing_score_not_5	assignment_student
  2026	Camden	MS		Gradebook Category	F	Data Entry	assign_f_score_less_5	assignment_student
  2026	Camden	MS		Gradebook Category	F	Data Entry	assign_null_score	assignment_student
  2026	Camden	MS		Gradebook Category	F	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	MS		Gradebook Category	F	Setup	f_assign_max_score_not_10	class_category_assignment
  2026	Camden	MS		Gradebook Category	F	Updated	f_expected_assign_count_not_met	class_category
  2026	Camden	MS		Gradebook Category	F	Data Entry	f_percent_graded_min_not_met	class_category
  2026	Camden	MS		Gradebook Category	H	Data Entry	assign_h_missing_score_not_5	assignment_student
  2026	Camden	MS		Gradebook Category	H	Data Entry	assign_h_score_less_5	assignment_student
  2026	Camden	MS		Gradebook Category	H	Data Entry	assign_null_score	assignment_student
  2026	Camden	MS		Gradebook Category	H	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	MS		Gradebook Category	H	Setup	h_assign_max_score_not_10	class_category_assignment
  2026	Camden	MS		Gradebook Category	H	Updated	h_expected_assign_count_not_met	class_category
  2026	Camden	MS		Gradebook Category	H	Data Entry	h_percent_graded_min_not_met	class_category
  2026	Camden	MS		Gradebook Category	S	Data Entry	assign_null_score	assignment_student
  2026	Camden	MS		Gradebook Category	S	Data Entry	assign_s_score_less_50p	assignment_student
  2026	Camden	MS		Gradebook Category	S	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	MS		Gradebook Category	S	Updated	s_expected_assign_count_not_met	class_category
  2026	Camden	MS		Gradebook Category	S	Data Entry	s_percent_graded_min_not_met	class_category
  2026	Camden	MS		Gradebook Category	W	Data Entry	assign_null_score	assignment_student
  2026	Camden	MS		Gradebook Category	W	Data Entry	assign_score_above_max	assignment_student
  2026	Camden	MS		Gradebook Category	W	Data Entry	assign_w_missing_score_not_5	assignment_student
  2026	Camden	MS		Gradebook Category	W	Data Entry	assign_w_score_less_5	assignment_student
  2026	Camden	MS		Gradebook Category	W	Setup	w_assign_max_score_not_10	class_category_assignment
  2026	Camden	MS		Gradebook Category	W	Updated	w_expected_assign_count_not_met	class_category
  2026	Camden	MS		Gradebook Category	W	Data Entry	w_percent_graded_min_not_met	class_category
  2026	Camden	MS		Quarter	Q1	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	MS		Quarter	Q1	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	MS		Quarter	Q2	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	MS		Quarter	Q2	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	MS		Quarter	Q3	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	MS		Quarter	Q3	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Camden	MS		Quarter	Q4	EOQ	qt_grade_70_comment_missing	student_course
  2026	Camden	MS		Quarter	Q4	Data Entry	qt_percent_grade_greater_100	student_course
  2026	Newark	ES		Quarter	Q1	Comments	qt_es_comment_missing	student_course
  2026	Newark	ES		Quarter	Q2	Comments	qt_es_comment_missing	student_course
  2026	Newark	ES		Quarter	Q3	Comments	qt_es_comment_missing	student_course
  2026	Newark	ES		Quarter	Q4	Comments	qt_es_comment_missing	student_course
  2026	Newark	HS		Gradebook Category	F	Data Entry	assign_f_missing_score_not_0	assignment_student
  2026	Newark	HS		Gradebook Category	F	Data Entry	assign_f_score_less_5	assignment_student
  2026	Newark	HS		Gradebook Category	F	Data Entry	assign_null_score	assignment_student
  2026	Newark	HS		Gradebook Category	F	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	HS		Gradebook Category	F	Setup	f_assign_max_score_not_10	class_category_assignment
  2026	Newark	HS		Gradebook Category	F	Updated	f_expected_assign_count_not_met	class_category
  2026	Newark	HS		Gradebook Category	F	Data Entry	f_percent_graded_min_not_met	class_category
  2026	Newark	HS		Gradebook Category	H	Data Entry	assign_h_missing_score_not_0	assignment_student
  2026	Newark	HS		Gradebook Category	H	Data Entry	assign_h_score_less_5	assignment_student
  2026	Newark	HS		Gradebook Category	H	Data Entry	assign_null_score	assignment_student
  2026	Newark	HS		Gradebook Category	H	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	HS		Gradebook Category	H	Setup	h_assign_max_score_not_10	class_category_assignment
  2026	Newark	HS		Gradebook Category	H	Updated	h_expected_assign_count_not_met	class_category
  2026	Newark	HS		Gradebook Category	H	Data Entry	h_percent_graded_min_not_met	class_category
  2026	Newark	HS		Gradebook Category	S	Data Entry	assign_null_score	assignment_student
  2026	Newark	HS		Gradebook Category	S	Data Entry	assign_s_hs_score_less_50p	assignment_student
  2026	Newark	HS		Gradebook Category	S	Data Entry	assign_s_missing_score_not_0	assignment_student
  2026	Newark	HS		Gradebook Category	S	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	HS		Gradebook Category	S	Updated	s_expected_assign_count_not_met	class_category
  2026	Newark	HS		Gradebook Category	S	Data Entry	s_percent_graded_min_not_met	class_category
  2026	Newark	HS		Gradebook Category	W	Data Entry	assign_null_score	assignment_student
  2026	Newark	HS		Gradebook Category	W	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	HS		Gradebook Category	W	Data Entry	assign_w_missing_score_not_0	assignment_student
  2026	Newark	HS		Gradebook Category	W	Data Entry	assign_w_score_less_5	assignment_student
  2026	Newark	HS		Gradebook Category	W	Setup	w_assign_max_score_not_10	class_category_assignment
  2026	Newark	HS		Gradebook Category	W	Updated	w_expected_assign_count_not_met	class_category
  2026	Newark	HS		Gradebook Category	W	Data Entry	w_percent_graded_min_not_met	class_category
  2026	Newark	HS		Quarter	Q1	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	HS		Quarter	Q2	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	HS		Quarter	Q3	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	HS		Quarter	Q4	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	MS		Gradebook Category	F	Data Entry	assign_f_missing_score_not_5	assignment_student
  2026	Newark	MS		Gradebook Category	F	Data Entry	assign_f_score_less_5	assignment_student
  2026	Newark	MS		Gradebook Category	F	Data Entry	assign_null_score	assignment_student
  2026	Newark	MS		Gradebook Category	F	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	MS		Gradebook Category	F	Setup	f_assign_max_score_not_10	class_category_assignment
  2026	Newark	MS		Gradebook Category	F	Updated	f_expected_assign_count_not_met	class_category
  2026	Newark	MS		Gradebook Category	F	Data Entry	f_percent_graded_min_not_met	class_category
  2026	Newark	MS		Gradebook Category	H	Data Entry	assign_h_missing_score_not_5	assignment_student
  2026	Newark	MS		Gradebook Category	H	Data Entry	assign_h_score_less_5	assignment_student
  2026	Newark	MS		Gradebook Category	H	Data Entry	assign_null_score	assignment_student
  2026	Newark	MS		Gradebook Category	H	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	MS		Gradebook Category	H	Setup	h_assign_max_score_not_10	class_category_assignment
  2026	Newark	MS		Gradebook Category	H	Updated	h_expected_assign_count_not_met	class_category
  2026	Newark	MS		Gradebook Category	H	Data Entry	h_percent_graded_min_not_met	class_category
  2026	Newark	MS		Gradebook Category	S	Data Entry	assign_null_score	assignment_student
  2026	Newark	MS		Gradebook Category	S	Data Entry	assign_s_score_less_50p	assignment_student
  2026	Newark	MS		Gradebook Category	S	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	MS		Gradebook Category	S	Updated	s_expected_assign_count_not_met	class_category
  2026	Newark	MS		Gradebook Category	S	Data Entry	s_percent_graded_min_not_met	class_category
  2026	Newark	MS		Gradebook Category	W	Data Entry	assign_null_score	assignment_student
  2026	Newark	MS		Gradebook Category	W	Data Entry	assign_score_above_max	assignment_student
  2026	Newark	MS		Gradebook Category	W	Data Entry	assign_w_missing_score_not_5	assignment_student
  2026	Newark	MS		Gradebook Category	W	Data Entry	assign_w_score_less_5	assignment_student
  2026	Newark	MS		Gradebook Category	W	Setup	w_assign_max_score_not_10	class_category_assignment
  2026	Newark	MS		Gradebook Category	W	Updated	w_expected_assign_count_not_met	class_category
  2026	Newark	MS		Gradebook Category	W	Data Entry	w_percent_graded_min_not_met	class_category
  2026	Newark	MS		Quarter	Q1	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	MS		Quarter	Q2	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	MS		Quarter	Q3	EOQ	qt_grade_70_comment_missing	student_course
  2026	Newark	MS		Quarter	Q4	EOQ	qt_grade_70_comment_missing	student_course
  2026	Paterson	ES		Quarter	Q3	Comments	qt_es_comment_missing	student_course
  2026	Paterson	ES		Quarter	Q4	Comments	qt_es_comment_missing	student_course
  2026	Paterson	MS		Gradebook Category	F	Data Entry	assign_f_missing_score_not_5	assignment_student
  2026	Paterson	MS		Gradebook Category	F	Data Entry	assign_f_score_less_5	assignment_student
  2026	Paterson	MS		Gradebook Category	F	Data Entry	assign_null_score	assignment_student
  2026	Paterson	MS		Gradebook Category	F	Data Entry	assign_score_above_max	assignment_student
  2026	Paterson	MS		Gradebook Category	F	Setup	f_assign_max_score_not_10	class_category_assignment
  2026	Paterson	MS		Gradebook Category	F	Updated	f_expected_assign_count_not_met	class_category
  2026	Paterson	MS		Gradebook Category	F	Data Entry	f_percent_graded_min_not_met	class_category
  2026	Paterson	MS		Gradebook Category	H	Data Entry	assign_h_missing_score_not_5	assignment_student
  2026	Paterson	MS		Gradebook Category	H	Data Entry	assign_h_score_less_5	assignment_student
  2026	Paterson	MS		Gradebook Category	H	Data Entry	assign_null_score	assignment_student
  2026	Paterson	MS		Gradebook Category	H	Data Entry	assign_score_above_max	assignment_student
  2026	Paterson	MS		Gradebook Category	H	Setup	h_assign_max_score_not_10	class_category_assignment
  2026	Paterson	MS		Gradebook Category	H	Updated	h_expected_assign_count_not_met	class_category
  2026	Paterson	MS		Gradebook Category	H	Data Entry	h_percent_graded_min_not_met	class_category
  2026	Paterson	MS		Gradebook Category	S	Data Entry	assign_null_score	assignment_student
  2026	Paterson	MS		Gradebook Category	S	Data Entry	assign_s_score_less_50p	assignment_student
  2026	Paterson	MS		Gradebook Category	S	Data Entry	assign_score_above_max	assignment_student
  2026	Paterson	MS		Gradebook Category	S	Updated	s_expected_assign_count_not_met	class_category
  2026	Paterson	MS		Gradebook Category	S	Data Entry	s_percent_graded_min_not_met	class_category
  2026	Paterson	MS		Gradebook Category	W	Data Entry	assign_null_score	assignment_student
  2026	Paterson	MS		Gradebook Category	W	Data Entry	assign_score_above_max	assignment_student
  2026	Paterson	MS		Gradebook Category	W	Data Entry	assign_w_missing_score_not_5	assignment_student
  2026	Paterson	MS		Gradebook Category	W	Data Entry	assign_w_score_less_5	assignment_student
  2026	Paterson	MS		Gradebook Category	W	Setup	w_assign_max_score_not_10	class_category_assignment
  2026	Paterson	MS		Gradebook Category	W	Updated	w_expected_assign_count_not_met	class_category
  2026	Paterson	MS		Gradebook Category	W	Data Entry	w_percent_graded_min_not_met	class_category
  2026	Paterson	MS		Quarter	Q1	EOQ	qt_grade_70_comment_missing	student_course
  2026	Paterson	MS		Quarter	Q2	EOQ	qt_grade_70_comment_missing	student_course
  2026	Paterson	MS		Quarter	Q3	EOQ	qt_grade_70_comment_missing	student_course
  2026	Paterson	MS		Quarter	Q4	EOQ	qt_grade_70_comment_missing	student_course
  ```

- [x] **Step 1.1: Roll over Newark rows (ES, MS, HS)**

  Copy all Newark rows where `academic_year = 2025`. Paste as new rows. Set
  `academic_year = 2026`. Delete any rows for these deprecated flags before
  saving:
  - `w_grade_inflation`
  - `assign_s_hs_score_not_conversion_chart_options`
  - `assign_s_ms_score_not_conversion_chart_options`
  - `qt_teacher_s_total_greater_200`
  - `qt_teacher_s_total_less_200`
  - `qt_student_is_ada_80_plus_gpa_less_2`

- [x] **Step 1.2: Roll over Camden rows (ES, MS, HS)**

  Same process as step 1.1 for Camden. Copy Camden `academic_year = 2025` rows,
  paste, set `academic_year = 2026`, delete the same deprecated flag rows listed
  above.

- [x] **Step 1.3: Add Paterson MS rows**

  Copy all Newark MS rows for `academic_year = 2026` (just created in step 1.1).
  Paste as new rows. Change `region` to `Paterson`. Paterson MS uses the same
  flags as Newark MS.

- [x] **Step 1.4: Add Paterson ES rows**

  Paterson ES gets EOQ comments only — same pattern as Camden ES and Newark ES.
  Add one row per applicable quarter (`Q3`, `Q4`) for
  `audit_flag_name = qt_es_comment_missing`, `region = Paterson`,
  `school_level = ES`, `academic_year = 2026`. Match the column values of an
  existing Camden ES or Newark ES row for that flag.

- [x] **Step 1.5: Do not add Miami rows**

  Miami is being removed. Do not create any `academic_year = 2026` rows for
  Miami.

- [x] **Step 1.6: Stage the external table**

  ```bash
  uv run dbt run-operation stage_external_sources \
    --args '{"select": "google_sheets.src_google_sheets__gradebook_flags"}' \
    --project-dir src/dbt/kipptaf
  ```

- [x] **Step 1.7: Rebuild staging and verify**

  ```bash
  uv run dbt build \
    --select stg_google_sheets__gradebook_flags \
    --project-dir src/dbt/kipptaf
  ```

  Verify via BigQuery MCP:

  ```sql
  SELECT DISTINCT region, school_level, academic_year
  FROM `teamster-332318.dbt_grangel_tableau.stg_google_sheets__gradebook_flags`
  WHERE academic_year = 2026
  ORDER BY 1, 2
  ```

  Expected: Camden, Newark, Paterson present for 2026. No Miami. Paterson has ES
  and MS only.

- [x] **Step 1.8: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): gradebook flags rollover to AY 2026-2027"
  ```

---

## Task 2: SQL — Remove the exceptions mechanism entirely

T&L has decided to eliminate the suppression table
(`stg_google_sheets__gradebook_exceptions`). The exception LEFT JOINs are
removed from each model as part of its individual rewrite in Task 6. This task
only handles disabling the staging model itself.

> **Note:** The 15+ exception LEFT JOINs across five intermediate models
> (`int_tableau__gradebook_audit_teacher_scaffold`,
> `int_tableau__gradebook_audit_assignments_teacher`,
> `int_tableau__gradebook_audit_categories_teacher`,
> `int_tableau__gradebook_audit_flags`, and the student scaffold) are not
> repeated here — they are removed when each model is rewritten in Task 6.

### Disable the exceptions staging model

- [x] **Step 2.1: Disable the staging model**

  In
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_exceptions.yml`,
  add at the top of the model config:

  ```yaml
  config:
    enabled: false
  ```

  The SQL file and source entry stay in place. This preserves the model for
  reference pending any operational decisions after July 1st.

- [x] **Step 2.2: Commit**

  ```bash
  git commit -m "feat(dbt): disable stg_google_sheets__gradebook_exceptions — refs removed in Task 6"
  ```

---

## Task 3: SQL — PS-native expectations model and QTD

`stg_google_sheets__gradebook_expectations_assignments` is being deprecated and
replaced by a PS-native intermediate model sourced from
`stg_powerschool__u_expectations` (the U_EXPECTATIONS PowerSchool plugin). This
task creates that model for Newark (the only region with PS plugin data today)
and updates both scaffolds to join it instead of the Google Sheet.

**Newark only for now.** Camden is blocked on PR #4077 (Bini's integration work)
landing in prod. Paterson is blocked on PS instance access — deploy the plugin
from [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins) once
access is available. Until each region's PS data is available, the INNER JOIN in
the teacher scaffold will find no matching rows for that region — category-level
audit rows (assignment count flags, percent-graded flags) will be silent for
Camden and Paterson until their data lands. EOQ and student-level flags in Task
1 are unaffected.

**Naming convention note:** If the INT model unpivots the wide-format category
counts (`cnt_w/h/f/s`) to long format inside the model itself, it must be named
`int_powerschool__u_expectations_unpivot` (Charlie's convention: model name must
include `unpivot` when the model performs an UNPIVOT). If the unpivot is
deferred to the scaffold instead, the plain name
`int_powerschool__u_expectations` is correct. Decide at implementation time
based on which approach produces cleaner scaffold code — and rename accordingly.

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__u_expectations[_unpivot].sql`
  and its YAML
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_student_scaffold.sql`

- [x] **Step 3.1: Create the INT expectations model**

  Create
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__u_expectations[_unpivot].sql`.

  The model must produce one row per
  `region / school_level / academic_year / quarter / assignment_category_code`
  (quarter grain — no `week_number`). The scaffold joins on this key exactly.
  Source: `stg_powerschool__u_expectations` (`school_level`, `quarter`, `cnt_w`,
  `cnt_h`, `cnt_f`, `cnt_s`). Region comes from joining
  `int_powerschool__calendar_week` on `school_level + quarter`. Academic year is
  injected via `{{ var("current_academic_year") }}`.

  Output columns:

  | Column                     | Source / derivation                                                    |
  | -------------------------- | ---------------------------------------------------------------------- |
  | `academic_year`            | `{{ var("current_academic_year") }}`                                   |
  | `region`                   | from `int_powerschool__calendar_week`                                  |
  | `school_level`             | from `stg_powerschool__u_expectations`                                 |
  | `quarter`                  | from `stg_powerschool__u_expectations`                                 |
  | `assignment_category_code` | `W`, `H`, `F`, or `S` (from unpivot of `cnt_*`)                        |
  | `expectation`              | the count value for that category and quarter                          |
  | `assignment_category_term` | `concat(code, right(quarter, 1))` e.g. `W3`                            |
  | `assignment_category_name` | `Work Habits` / `Homework` / `Formative Mastery` / `Summative Mastery` |
  | `notes`                    | `null` (not available in PS plugin source)                             |

  Whether the UNPIVOT happens inside this model or in the scaffold is a decision
  to make at implementation time (see naming note above).

- [x] **Step 3.1b: Build and verify the INT model**

  ```bash
  uv run dbt build \
    --select int_powerschool__u_expectations[_unpivot] \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [x] **Step 3.2: Create the YAML for the new INT model**

  Create the properties file at
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__u_expectations[_unpivot].yml`.
  Add a model description and a column entry for each output column. Add a
  `dbt_utils.unique_combination_of_columns` test on
  `(region, school_level, academic_year, quarter, assignment_category_code)`. No
  `week_number` — the model is quarter-grain.

> ✅ **PR #4077 merged.** Camden U_EXPECTATIONS data is live in prod. The
> teacher scaffold's `inner join ... on s.region = ge.region` naturally picks up
> Camden rows — no SQL change needed. Both Newark and Camden now produce
> `teacher_category_scaffold` rows.

---

## Task 4: SQL — Update base views and tables

### ~~4a: `base_powerschool__sections` — add `school_abbreviation` and `school_level`~~

> **Implemented in PR #4152.** `school_abbreviation` and `school_level` were
> added to `base_powerschool__sections` in the `powerschool` package and merged
> before step 6a executed. Step 6a reads these fields directly from
> `base_powerschool__sections` — the `stg_powerschool__schools` join was removed
> from the scaffold entirely.

---

### 4b: `stg_google_sheets__gradebook_flags` — drop `grade_level`

`grade_level` was only used by Miami KG/G1-G8 conduct code flags (now gone).
Drop it using BigQuery `SELECT * EXCEPT`.

**File:**
`src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gradebook_flags.sql`

- [x] **Step 4b.1: Update the SELECT**

  Change:

  ```sql
  select
      *,
      case ... end as alt_code,
  from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
  ```

  to:

  ```sql
  select
      * except (grade_level),
      case ... end as alt_code,
  from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
  ```

- [x] **Step 4b.2: Remove `grade_level` from the YAML**

  File:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_flags.yml`

  Delete the `grade_level` column entry.

- [x] **Step 4b.3: Build and verify**

  ```bash
  uv run dbt build \
    --select stg_google_sheets__gradebook_flags \
    --project-dir src/dbt/kipptaf
  ```

---

### 4c: `int_extracts__student_enrollments` — add ADA/GPA cumulative boolean

> ⚠️ **Open question for T&L (see issue #3908 comment):** use `< 2.0` until
> threshold is confirmed.

**File:**
`src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments.sql`

- [x] **Step 4c.1: Add boolean column**

  In the final `select`, after `ada_above_or_at_80` and GPA columns (ST06
  ordering — logicals after plain refs):

  ```sql
  if(
      ada_above_or_at_80 and cumulative_y1_gpa < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_cum_gpa_less_2,
  ```

- [x] **Step 4c.2: Add column to YAML**

  File:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`

  ```yaml
  - name: is_ada_above_or_at_80_cum_gpa_less_2
    description: >
      True when the student's ADA is at or above 80% and their cumulative
      year-to-date GPA (cumulative_y1_gpa) is below 2.0.
    data_type: boolean
  ```

- [x] **Step 4c.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_extracts__student_enrollments \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 4d: `int_powerschool__gradebook_assignments_scores` — Sumner G5 fix + `is_expected` grace period

Two changes to this model: fix the Sumner Elementary G5 → MS override hardcoded
to `cc_academic_year = 2025`, and add a 7-day post-due grace period to
`is_expected`. The grace period applies universally — all `is_expected_*`
derived columns inherit it automatically, covering null, zero, missing, late,
academic-dishonesty, and scored checks across every downstream consumer
(`categories_teacher`, `assignments_teacher`, `assignments_student`,
`fct_grades_assignments`).

**File:**
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`

- [x] **Step 4d.1: Update the year condition**

  Find (line ~40):

  ```sql
  if(
      e.cc_academic_year = 2025
      and e.cc_schoolid = 179905
      and e.sections_grade_level = 5,
      'MS',
      d.school_level
  ) as school_level,
  ```

  Change `= 2025` to `>= 2025`:

  ```sql
  if(
      e.cc_academic_year >= 2025
      and e.cc_schoolid = 179905
      and e.sections_grade_level = 5,
      'MS',
      d.school_level
  ) as school_level,
  ```

- [x] **Step 4d.2: Add 7-day grace period to `is_expected`**

  In the `scores` CTE (line ~29), add a third `when` branch:

  Find:

  ```sql
  case
      when coalesce(s.isexempt, 0) = 1
      then false
      when a.iscountedinfinalgrade = 0
      then false
      else true
  end as is_expected,
  ```

  Replace:

  ```sql
  case
      when coalesce(s.isexempt, 0) = 1
      then false
      when a.iscountedinfinalgrade = 0
      then false
      when current_date('{{ var("local_timezone") }}') <= date_add(a.duedate, interval 7 day)
      then false
      else true
  end as is_expected,
  ```

  `a.duedate` is already in scope (line 9). All `is_expected_*` derived columns
  (lines 130–144) AND with `is_expected`, so they inherit the grace period
  without further changes. Update the `is_expected` column description in the
  properties YAML to document the 7-day rule.

- [ ] **Step 4d.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_powerschool__gradebook_assignments_scores \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

## Task 5: SQL — `rpt_tableau__gradebook_gpa` updates

> ⚠️ **Pending decision:**
> `teacher_avg_score_for_assign_per_class_section_and_assign_id` currently lives
> in `int_tableau__gradebook_audit_assignments_teacher` but is used by the GPA
> Tableau workbook, not the audit workbook. Plan is to extract the
> `assignment_score_rollup` CTE into its own intermediate model
> (`int_powerschool__gradebook_assignment_score_rollup`) so
> `rpt_tableau__gradebook_gpa` can reference it directly. **Grain question
> unresolved:** `rpt_gpa` operates at student × section × quarter grain; the
> rollup is at `assignmentsectionid` grain (per individual assignment). Need to
> decide what aggregation level `rpt_gpa` needs before implementing. Step to be
> added here once decided.

### 5a: `rpt_tableau__gradebook_gpa` — add per-course boolean, remove Paterson filter

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_gpa.sql`

- [x] **Step 5.1: Add per-course GPA boolean**

  In the final `select`, after `ada_above_or_at_80`:

  ```sql
  if(
      s.ada_above_or_at_80 and s.gpa_y1 < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_gpa_y1_less_2,
  ```

- [x] **Step 5.2: Remove Paterson exclusion**

  In the `student_roster` CTE WHERE clause, remove
  `and enr.region != 'Paterson'`. The full WHERE becomes:

  ```sql
  where
      enr.rn_year = 1
      and not enr.is_out_of_district
      and enr.enroll_status != -1
  ```

- [x] **Step 5.3: Add column to YAML**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_gpa.yml`

  ```yaml
  - name: is_ada_above_or_at_80_gpa_y1_less_2
    description: >
      True when the student's ADA is at or above 80% and their year-to-date
      course GPA (gpa_y1) is below 2.0. Per-course grain.
    data_type: boolean
  ```

- [ ] **Step 5.4: Build and verify**

  ```bash
  uv run dbt build \
    --select rpt_tableau__gradebook_gpa \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

  Verify Paterson now appears:

  ```sql
  SELECT DISTINCT region, school_level
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_gpa`
  WHERE academic_year = 2026
  ORDER BY 1, 2
  ```

---

---

## Task 6: SQL — Quarter-grain scaffold and model updates

**Flag reference table** — use this as your checklist when working through each
model. Every flag in this table must be removed from its source model, its YAML,
and the UNPIVOT list in `int_tableau__gradebook_audit_flags.sql`.

| Flag                                             | Lives in model                                     | Reason                             |
| ------------------------------------------------ | -------------------------------------------------- | ---------------------------------- |
| `w_grade_inflation`                              | `int_tableau__gradebook_audit_student_scaffold`    | FYI flag — in 2.4                  |
| `assign_s_hs_score_not_conversion_chart_options` | `int_tableau__gradebook_audit_assignments_student` | FYI flag                           |
| `assign_s_ms_score_not_conversion_chart_options` | `int_tableau__gradebook_audit_assignments_student` | FYI flag                           |
| `qt_teacher_s_total_greater_200`                 | `int_tableau__gradebook_audit_categories_teacher`  | Makeup work policy false positives |
| `qt_teacher_s_total_less_200`                    | `int_tableau__gradebook_audit_categories_teacher`  | Makeup work policy false positives |
| `qt_student_is_ada_80_plus_gpa_less_2`           | `int_tableau__gradebook_audit_student_scaffold`    | Migrated — in 2.4                  |
| `qt_teacher_s_total_greater_100`                 | `int_tableau__gradebook_audit_categories_teacher`  | Miami-only dead code               |
| `qt_teacher_s_total_less_100`                    | `int_tableau__gradebook_audit_categories_teacher`  | Miami-only dead code               |
| `s_max_score_greater_100`                        | `int_tableau__gradebook_audit_assignments_teacher` | Miami-only dead code               |
| `qt_comment_missing`                             | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_g1_g8_conduct_code_missing`                  | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_g1_g8_conduct_code_incorrect`                | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_kg_conduct_code_missing`                     | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_kg_conduct_code_incorrect`                   | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_kg_conduct_code_not_hr`                      | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_effort_grade_missing`                        | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_formative_grade_missing`                     | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |
| `qt_summative_grade_missing`                     | `int_tableau__gradebook_audit_student_scaffold`    | Miami-only dead code — in 2.4      |

---

### 6a: `int_tableau__gradebook_audit_teacher_scaffold.sql` — quarter-grain redesign

- [x] **Step 6a.1: Redesign
      `int_tableau__gradebook_audit_teacher_scaffold.sql`**

  This step replaces the entire scaffold with the quarter-grain design. The
  current four-CTE model (`sections`, `term_weeks`, `school_level_mod`, `final`)
  - outer SELECT becomes a single `sections` CTE + a direct two-branch UNION ALL
    SELECT.

  **The new structure:**

  ```sql
  with
      /* base_powerschool__sections is section-grain (one row per section), which is
         correct here — the teacher scaffold is the master schedule, not student-level */
      teacher_master_schedule as (
          select
              s._dbt_source_relation,
              s.terms_academic_year as academic_year,
              s.sections_dcid,
              s.sections_id as sectionid,
              s.sections_schoolid as schoolid,
              s.sections_course_number as course_number,
              s.sections_section_number as section_number,
              s.sections_external_expression as external_expression,
              s.courses_course_name as course_name,
              s.courses_credittype as credit_type,
              s.courses_excludefromgpa as exclude_from_gpa,
              s.teachernumber as teacher_number,
              s.teacher_lastfirst as teacher_name,
              sch.abbreviation as school,

              r.sam_account_name as teacher_tableau_username,
              r.reports_to_employee_number as manager_employee_number,
              r.reports_to_formatted_name as manager_name,
              r.reports_to_sam_account_name as manager_tableau_username,

              l.head_of_school_preferred_name_lastfirst as hos,
              l.school_leader_preferred_name_lastfirst as school_leader,
              l.school_leader_sam_account_name as school_leader_tableau_username,

              t.yearid,
              t.term as `quarter`,
              t.semester,
              t.term_start_date as quarter_start_date,
              t.term_end_date as quarter_end_date,
              t.is_current_term,
              sch.school_level,

              initcap(
                  regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')
              ) as region,

              if(
                  s.school_name = 'KIPP Sumner Elementary'
                  and s.sections_grade_level = 5,
                  'MS',
                  null
              ) as school_level_alt,

              cast(s.terms_academic_year as string)
              || '-'
              || right(cast(s.terms_academic_year + 1 as string), 2)
                  as academic_year_display,

          from {{ ref("base_powerschool__sections") }} as s
          left join
              {{ ref("stg_powerschool__schools") }} as sch
              on s.sections_schoolid = sch.school_number
              and {{ union_dataset_join_clause(left_alias="s", right_alias="sch") }}
          left join
              {{ ref("int_people__staff_roster") }} as r
              on s.teachernumber = r.powerschool_teacher_number
          left join
              {{ ref("int_people__leadership_crosswalk") }} as l
              on s.sections_schoolid = l.home_work_location_powerschool_school_id
          inner join
              {{ ref("int_powerschool__terms") }} as t
              on s.sections_schoolid = t.schoolid
              and s.terms_yearid = t.yearid
              and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
          where
              s.terms_academic_year = {{ var("current_academic_year") }}
              and s.sections_no_of_students != 0
      )

  /* Explicit column listing required for all models under the tableau schema.
     school_level and region_school_level are derived using school_level_alt
     so the if() expression appears only once (in the CTE). */
  select
      s._dbt_source_relation,
      s.academic_year,
      s.academic_year_display,
      s.yearid,
      s.schoolid,
      s.school,
      s.region,
      s.sections_dcid,
      s.sectionid,
      s.section_number,
      s.external_expression,
      s.course_number,
      s.course_name,
      s.credit_type,
      s.exclude_from_gpa,
      s.teacher_number,
      s.teacher_name,
      s.teacher_tableau_username,
      s.manager_employee_number,
      s.manager_name,
      s.manager_tableau_username,
      s.hos,
      s.school_leader,
      s.school_leader_tableau_username,
      s.quarter,
      s.semester,
      s.quarter_start_date,
      s.quarter_end_date,
      s.is_current_term,

      null as assignment_category_code,
      null as assignment_category_name,
      null as assignment_category_term,
      null as expectation,
      null as notes,

      coalesce(s.school_level_alt, s.school_level) as school_level,

      concat(s.region, coalesce(s.school_level_alt, s.school_level)) as region_school_level,

      if(
          coalesce(s.school_level_alt, s.school_level) = 'HS',
          s.external_expression,
          s.section_number
      ) as section_or_period,

      'teacher_scaffold' as scaffold_name,

  from teacher_master_schedule as s

  union all

  select
      s._dbt_source_relation,
      s.academic_year,
      s.academic_year_display,
      s.yearid,
      s.schoolid,
      s.school,
      s.region,
      s.sections_dcid,
      s.sectionid,
      s.section_number,
      s.external_expression,
      s.course_number,
      s.course_name,
      s.credit_type,
      s.exclude_from_gpa,
      s.teacher_number,
      s.teacher_name,
      s.teacher_tableau_username,
      s.manager_employee_number,
      s.manager_name,
      s.manager_tableau_username,
      s.hos,
      s.school_leader,
      s.school_leader_tableau_username,
      s.quarter,
      s.semester,
      s.quarter_start_date,
      s.quarter_end_date,
      s.is_current_term,

      ge.assignment_category_code,
      ge.assignment_category_name,
      ge.assignment_category_term,
      ge.expectation,
      ge.notes,

      coalesce(s.school_level_alt, s.school_level) as school_level,

      concat(s.region, coalesce(s.school_level_alt, s.school_level)) as region_school_level,

      if(
          coalesce(s.school_level_alt, s.school_level) = 'HS',
          s.external_expression,
          s.section_number
      ) as section_or_period,

      'teacher_category_scaffold' as scaffold_name,

  from teacher_master_schedule as s
  inner join
      {{ ref("int_powerschool__u_expectations[_unpivot]") }} as ge
      on s.region = ge.region
      and s.school_level = ge.school_level
      and s.academic_year = ge.academic_year
      and s.quarter = ge.quarter
  ```

  Key differences from the old model:
  - CTE renamed `sections` → `teacher_master_schedule` — this scaffold is the
    teacher master schedule; `base_powerschool__sections` (section-grain) is the
    correct source, not `base_powerschool__course_enrollments` (student-grain)
  - `is_ap_course` removed — only used by
    `assign_s_hs_score_not_conversion_chart_options` (FYI flag, removed per
    issue #3908)
  - `s.terms_yearid` removed — redundant with `t.yearid` (equal by join
    condition); `yearid` is kept as the output column for downstream joins
  - `school_level_alt` defined once in CTE; `school_level`,
    `region_school_level`, and `section_or_period` derived in the main SELECT
    using it — no repeated `if(school_name = ...)` expression
  - No `week_number` in the join — quarter grain only
  - No `final` CTE — UNION ALL is the SELECT
  - No `is_quarter_end_date_range`, `quarter_end_date_insession`,
    `is_current_week`
  - No week columns
  - Manager columns added
  - `region` derived inline from `_dbt_source_relation`
  - `school_level` and `school_abbreviation` (`sch.school_level`,
    `sch.abbreviation`) come from a `left join stg_powerschool__schools` — kept
    at the kipptaf level per CLAUDE.md; step 4a was reverted

  _(Replace `[_unpivot]` with the actual model name decided in step 3.1.)_

- [x] **Step 6a.2: Build and verify the teacher scaffold**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_teacher_scaffold \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

  Verify quarter grain, Q1–Q4 present, Newark has category rows:

  ```sql
  SELECT DISTINCT region, school_level, scaffold_name, quarter
  FROM `teamster-332318.dbt_grangel_tableau.int_tableau__gradebook_audit_teacher_scaffold`
  WHERE academic_year = 2026
  ORDER BY 1, 2, 3, 4
  ```

  Expected: Newark and Camden with both scaffold variants, Q1–Q4. Paterson has
  `teacher_scaffold` rows only (PS plugin not yet deployed there).

  > **Note (actual implementation):** `school_abbreviation` and `school_level`
  > come directly from `base_powerschool__sections` (PR #4152); the
  > `stg_powerschool__schools` join in the plan's code block was removed.
  > `_dbt_source_relation` replaced by `_dbt_source_project` throughout.
  > `int_powerschool__terms` was updated to expose `_dbt_source_project` (needed
  > for the direct equality join replacing `union_dataset_join_clause`).

### 6b: `int_tableau__gradebook_audit_student_scaffold.sql` — quarter-grain redesign

- [x] **Step 6b.1: Redesign
      `int_tableau__gradebook_audit_student_scaffold.sql`**

  This step applies all changes to the student scaffold: replace the
  expectations join, remove all week/EOQ columns, remove deprecated flags, add
  manager columns, add PatersonES to the ES comment flag. This is the complete
  target state of the model.

  **Key simplification:** the `student_category_scaffold` branch previously had
  its own INNER JOIN to `stg_google_sheets__gradebook_expectations_assignments`
  to get `assignment_category_name`, `assignment_category_term`, etc. Since
  `sec` (teacher_category_scaffold) already carries all those fields from its
  own expectations join, that join is redundant. **Remove it entirely** and
  reference `sec.*` for expectation fields.

  **Summer toggle:** both `category_grades` and the `quarter_course_grades` join
  have a seasonal toggle. See the `gradebook-audit` skill procedure "Recover
  category grades after academic year rollover" for when and how to flip these.

  ```sql
  with
      quarter_course_grades as (
          select
              _dbt_source_relation,
              academic_year,
              yearid,
              studentid,
              sectionid,
              storecode,
              termbin_start_date,
              term_percent_grade_adjusted as quarter_course_percent_grade,
              term_grade_points as quarter_course_grade_points,
              comment_value as quarter_comment_value,

              'current_year' as grades_type,

          from {{ ref("base_powerschool__final_grades") }}

          union all

          select
              _dbt_source_relation,
              academic_year,
              yearid,
              studentid,
              sectionid,
              storecode,
              null as termbin_start_date,
              `percent` as quarter_course_percent_grade,
              gpa_points as quarter_course_grade_points,
              comment_value as quarter_comment_value,

              'last_year' as grades_type,

          from {{ ref("stg_powerschool__storedgrades") }}
          where
              academic_year = {{ var("current_academic_year") - 1 }}
              and storecode_type = 'Q'
              and not is_transfer_grade
      )

  /* student_scaffold: one row per student × section × quarter
     student_category_scaffold: one row per student × section × quarter × category */

  select
      s._dbt_source_relation,
      s.academic_year,
      s.academic_year_display,
      s.yearid,
      s.region,
      s.school_level_alt as school_level,
      s.schoolid,
      s.school,
      s.students_dcid,
      s.studentid,
      s.student_number,
      s.student_name,
      s.grade_level,
      s.salesforce_id,
      s.ktc_cohort,
      s.enroll_status,
      s.cohort,
      s.gender,
      s.ethnicity,
      s.advisory,
      s.hos,
      s.year_in_school,
      s.year_in_network,
      s.rn_undergrad,
      s.is_out_of_district,
      s.is_self_contained,
      s.is_retained_year,
      s.is_retained_ever,
      s.lunch_status,
      s.gifted_and_talented,
      s.iep_status,
      s.lep_status,
      s.is_504,
      s.is_counseling_services,
      s.is_student_athlete,
      s.`ada`,
      s.ada_above_or_at_80,

      ce.cc_sectionid as sectionid,
      ce.cc_course_number as course_number,
      ce.cc_dateenrolled as date_enrolled,
      ce.sections_dcid,
      ce.sections_section_number as section_number,
      ce.sections_external_expression as external_expression,
      ce.sections_termid as termid,
      ce.courses_credittype as credit_type,
      ce.courses_course_name as course_name,
      ce.courses_excludefromgpa as exclude_from_gpa,
      ce.teachernumber as teacher_number,
      ce.teacher_lastfirst as teacher_name,
      ce.is_ap_course,

      sec.teacher_tableau_username,
      sec.manager_employee_number,
      sec.manager_name,
      sec.manager_tableau_username,
      sec.school_leader,
      sec.school_leader_tableau_username,
      sec.region_school_level,
      sec.quarter,
      sec.semester,
      sec.quarter_start_date,
      sec.quarter_end_date,
      sec.is_current_term,
      sec.section_or_period,

      qg.quarter_course_percent_grade,
      qg.quarter_course_grade_points,
      qg.quarter_comment_value,

      'student_scaffold' as scaffold_name,

      null as assignment_category_name,
      null as assignment_category_code,
      null as assignment_category_term,
      null as expectation,
      null as notes,

      null as category_quarter_percent_grade,

      if(
          qg.quarter_course_percent_grade > 100, true, false
      ) as qt_percent_grade_greater_100,

      if(
          s.school_level_alt != 'ES'
          and qg.quarter_course_percent_grade < 70
          and qg.quarter_comment_value is null,
          true,
          false
      ) as qt_grade_70_comment_missing,

      if(
          sec.region_school_level in ('CamdenES', 'NewarkES', 'PatersonES')
          and ce.courses_credittype in ('HR', 'MATH', 'ENG', 'RHET')
          and qg.quarter_comment_value is null,
          true,
          false
      ) as qt_es_comment_missing,

  from {{ ref("int_extracts__student_enrollments") }} as s
  inner join
      {{ ref("base_powerschool__course_enrollments") }} as ce
      on s.studentid = ce.cc_studentid
      and s.yearid = ce.terms_yearid
      and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
      and not ce.is_dropped_section
      and ce.sections_no_of_students != 0
  inner join
      {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
      on ce.terms_yearid = sec.yearid
      and ce.cc_sectionid = sec.sectionid
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
      and sec.scaffold_name = 'teacher_scaffold'
  left join
      quarter_course_grades as qg
      on ce.terms_yearid = qg.yearid
      and ce.cc_studentid = qg.studentid
      and ce.cc_sectionid = qg.sectionid
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
      and sec.quarter = qg.storecode
      and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
      and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
      and qg.grades_type = 'current_year' /* summer toggle: see skill */
  where
      s.academic_year = {{ var("current_academic_year") }}
      and s.rn_year = 1
      and s.enroll_status = 0
      and not s.is_out_of_district

  union all

  select
      s._dbt_source_relation,
      s.academic_year,
      s.academic_year_display,
      s.yearid,
      s.region,
      s.school_level_alt as school_level,
      s.schoolid,
      s.school,
      s.students_dcid,
      s.studentid,
      s.student_number,
      s.student_name,
      s.grade_level,
      s.salesforce_id,
      s.ktc_cohort,
      s.enroll_status,
      s.cohort,
      s.gender,
      s.ethnicity,
      s.advisory,
      s.hos,
      s.year_in_school,
      s.year_in_network,
      s.rn_undergrad,
      s.is_out_of_district,
      s.is_self_contained,
      s.is_retained_year,
      s.is_retained_ever,
      s.lunch_status,
      s.gifted_and_talented,
      s.iep_status,
      s.lep_status,
      s.is_504,
      s.is_counseling_services,
      s.is_student_athlete,
      s.`ada`,
      s.ada_above_or_at_80,

      ce.cc_sectionid as sectionid,
      ce.cc_course_number as course_number,
      ce.cc_dateenrolled as date_enrolled,
      ce.sections_dcid,
      ce.sections_section_number as section_number,
      ce.sections_external_expression as external_expression,
      ce.sections_termid as termid,
      ce.courses_credittype as credit_type,
      ce.courses_course_name as course_name,
      ce.courses_excludefromgpa as exclude_from_gpa,
      ce.teachernumber as teacher_number,
      ce.teacher_lastfirst as teacher_name,
      ce.is_ap_course,

      sec.teacher_tableau_username,
      sec.manager_employee_number,
      sec.manager_name,
      sec.manager_tableau_username,
      sec.school_leader,
      sec.school_leader_tableau_username,
      sec.region_school_level,
      sec.quarter,
      sec.semester,
      sec.quarter_start_date,
      sec.quarter_end_date,
      sec.is_current_term,
      sec.section_or_period,

      qg.quarter_course_percent_grade,
      qg.quarter_course_grade_points,
      qg.quarter_comment_value,

      'student_category_scaffold' as scaffold_name,

      sec.assignment_category_name,
      sec.assignment_category_code,
      sec.assignment_category_term,
      sec.expectation,
      sec.notes,

      cg.percent_grade as category_quarter_percent_grade,

      null as qt_percent_grade_greater_100,
      null as qt_grade_70_comment_missing,
      null as qt_es_comment_missing,

  from {{ ref("int_extracts__student_enrollments") }} as s
  inner join
      {{ ref("base_powerschool__course_enrollments") }} as ce
      on s.studentid = ce.cc_studentid
      and s.yearid = ce.terms_yearid
      and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
      and not ce.is_dropped_section
      and ce.sections_no_of_students != 0
  inner join
      {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
      on ce.terms_yearid = sec.yearid
      and ce.cc_sectionid = sec.sectionid
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
      and sec.scaffold_name = 'teacher_category_scaffold'
  left join
      quarter_course_grades as qg
      on ce.terms_yearid = qg.yearid
      and ce.cc_studentid = qg.studentid
      and ce.cc_sectionid = qg.sectionid
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
      and sec.quarter = qg.storecode
      and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
      and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
      and qg.grades_type = 'current_year' /* summer toggle: see skill */
  left join
      {{ ref("int_powerschool__category_grades") }} as cg
      on ce.terms_yearid = cg.yearid
      and ce.cc_studentid = cg.studentid
      and ce.cc_sectionid = cg.sectionid
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="cg") }}
      and sec.assignment_category_term = cg.storecode
      and cg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
      /* summer toggle: change -1990 to -1991 after PS academic year rollover
         in July until new-year grade data is available; revert when ready */
      and cg.yearid = {{ var("current_academic_year") - 1990 }}
  where
      s.academic_year = {{ var("current_academic_year") }}
      and s.rn_year = 1
      and s.enroll_status = 0
      and not s.is_out_of_district
  ```

  Key changes from the old model:
  - All week columns removed (`week_start_date`, `week_start_monday`, etc.)
  - `is_quarter_end_date_range`, `quarter_end_date_insession`, `is_current_week`
    removed
  - Manager columns added from `sec`
  - Miami excluded via `_dbt_source_project != 'kippmiami'` in teacher scaffold
    WHERE; student scaffold inherits the exclusion through INNER JOIN
  - `sections_no_of_students != 0` applied independently in both scaffolds:
    teacher scaffold WHERE clause; student scaffold on the `ce` JOIN condition
  - Deprecated flags removed (Miami conduct codes, `w_grade_inflation`,
    effort/formative/summative)
  - `qt_es_comment_missing` updated: removed `is_quarter_end_date_range`
    condition, added `PatersonES`
  - `qt_grade_70_comment_missing` updated: removed `is_quarter_end_date_range`
    condition
  - `qt_student_is_ada_80_plus_gpa_less_2` removed (migrated to `int_extracts`)
  - Expectations join removed from `student_category_scaffold` branch — fields
    come from `sec` instead
  - `category_grades` join updated from `ge.assignment_category_term` to
    `sec.assignment_category_term`
  - `quarter_conduct` removed entirely — from both SELECT lists and from the
    `quarter_course_grades` CTE (`citizenship` / `behavior` aliases dropped).
    Only referenced by Miami conduct code flags, which are being removed.
  - `category_quarter_average_all_courses` removed entirely — was only used to
    compute `w_grade_inflation`, which is being removed.
  - `category_grades` CTE eliminated — without the window function it was just a
    filtered read; inlined as a direct LEFT JOIN to
    `int_powerschool__category_grades`. Summer toggle moves from CTE WHERE to
    the JOIN condition.
  - All column listings are explicit per Bini's requirement for tableau schema
    models (no `SELECT *` or `SELECT * EXCEPT`).

- [x] **Step 6b.2: Build and verify the student scaffold**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_student_scaffold \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 6b.3: Disable the deprecated staging model**

  Nothing references `stg_google_sheets__gradebook_expectations_assignments`
  after steps 6.1–6.2. Disable it rather than deleting, in case operational
  decisions after July 1st affect the final approach.

  In
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_expectations_assignments.yml`,
  add at the top of the model config:

  ```yaml
  config:
    enabled: false
  ```

  Verify no remaining active references:

  ```bash
  grep -rn "gradebook_expectations_assignments" src/dbt/kipptaf/models/ --include="*.sql"
  ```

  Expected: zero results (the disabled model's own SQL file is fine to stay).

- [x] **Step 6b.4: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): replace Google Sheet expectations with PS-native INT model (Newark)"
  ```

### 6c: `int_tableau__gradebook_audit_assignments_student`

Complete replacement. Changes from the old model:

- `ce.*` → explicit column listing (Bini's rule for tableau schema)
- Date window: `week_start_date/week_end_date` →
  `quarter_start_date/quarter_end_date`
- Two FYI flags removed: `assign_s_ms_score_not_conversion_chart_options`,
  `assign_s_hs_score_not_conversion_chart_options`
- Single-line comments use `--`; multi-line use `/* */`

- [x] **Step 6c.1: Rewrite the model**

  **File:**
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_student.sql`

  ```sql
  select
      ce._dbt_source_relation,
      ce.academic_year,
      ce.academic_year_display,
      ce.yearid,
      ce.region,
      ce.school_level,
      ce.schoolid,
      ce.school,
      ce.students_dcid,
      ce.studentid,
      ce.student_number,
      ce.student_name,
      ce.grade_level,
      ce.salesforce_id,
      ce.ktc_cohort,
      ce.enroll_status,
      ce.cohort,
      ce.gender,
      ce.ethnicity,
      ce.advisory,
      ce.hos,
      ce.year_in_school,
      ce.year_in_network,
      ce.rn_undergrad,
      ce.is_out_of_district,
      ce.is_self_contained,
      ce.is_retained_year,
      ce.is_retained_ever,
      ce.lunch_status,
      ce.gifted_and_talented,
      ce.iep_status,
      ce.lep_status,
      ce.is_504,
      ce.is_counseling_services,
      ce.is_student_athlete,
      ce.`ada`,
      ce.ada_above_or_at_80,

      ce.sectionid,
      ce.course_number,
      ce.date_enrolled,
      ce.sections_dcid,
      ce.section_number,
      ce.external_expression,
      ce.termid,
      ce.credit_type,
      ce.course_name,
      ce.exclude_from_gpa,
      ce.teacher_number,
      ce.teacher_name,
      ce.is_ap_course,

      ce.teacher_tableau_username,
      ce.manager_employee_number,
      ce.manager_name,
      ce.manager_tableau_username,
      ce.school_leader,
      ce.school_leader_tableau_username,
      ce.region_school_level,
      ce.quarter,
      ce.semester,
      ce.quarter_start_date,
      ce.quarter_end_date,
      ce.is_current_term,
      ce.section_or_period,
      ce.assignment_category_name,
      ce.assignment_category_code,
      ce.assignment_category_term,
      ce.expectation,
      ce.notes,

      ce.quarter_course_percent_grade,
      ce.quarter_course_grade_points,
      ce.quarter_comment_value,
      ce.category_quarter_percent_grade,

      a.assignmentid,
      a.assignment_name,
      a.duedate,
      a.scoretype,
      a.scorepoints,
      a.totalpointvalue,
      a.is_exempt,
      a.is_expected_late,
      a.is_expected_missing,
      a.is_expected_zero,
      a.is_expected_academic_dishonesty,
      a.is_expected_null,
      a.score_entered,
      a.assign_final_score_percent,
      a.half_total_point_value,

      a.is_expected as assign_expected_to_be_scored,
      a.is_expected_scored as assign_expected_with_score,

      if(a.is_expected_null = 1, true, false) as assign_null_score,

      if(a.score_entered > a.totalpointvalue, true, false) as assign_score_above_max,

      if(
          ce.assignment_category_code = 'W'
          and a.is_expected_missing = 0
          and a.score_entered < 5,
          true,
          false
      ) as assign_w_score_less_5,

      if(
          ce.assignment_category_code = 'H'
          and a.is_expected_missing = 0
          and a.score_entered < 5,
          true,
          false
      ) as assign_h_score_less_5,

      if(
          ce.assignment_category_code = 'F'
          and a.is_expected_missing = 0
          and a.score_entered < 5,
          true,
          false
      ) as assign_f_score_less_5,

      if(
          ce.assignment_category_code = 'W'
          and ce.school_level != 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 5,
          true,
          false
      ) as assign_w_missing_score_not_5,

      if(
          ce.assignment_category_code = 'H'
          and ce.school_level != 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 5,
          true,
          false
      ) as assign_h_missing_score_not_5,

      if(
          ce.assignment_category_code = 'F'
          and ce.school_level != 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 5,
          true,
          false
      ) as assign_f_missing_score_not_5,

      if(
          ce.assignment_category_code = 'W'
          and ce.school_level = 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 0,
          true,
          false
      ) as assign_w_missing_score_not_0,

      if(
          ce.assignment_category_code = 'H'
          and ce.school_level = 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 0,
          true,
          false
      ) as assign_h_missing_score_not_0,

      if(
          ce.assignment_category_code = 'F'
          and ce.school_level = 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 0,
          true,
          false
      ) as assign_f_missing_score_not_0,

      if(
          ce.assignment_category_code = 'S'
          and ce.school_level = 'HS'
          and a.is_expected_missing = 1
          and a.score_entered != 0,
          true,
          false
      ) as assign_s_missing_score_not_0,

      if(
          ce.assignment_category_code = 'S'
          and ce.school_level != 'HS'
          and a.score_entered < a.half_total_point_value,
          true,
          false
      ) as assign_s_score_less_50p,

      if(
          ce.assignment_category_code = 'S'
          and ce.school_level = 'HS'
          and a.is_missing = 0
          and a.score_entered < a.half_total_point_value,
          true,
          false
      ) as assign_s_hs_score_less_50p,

  from {{ ref("int_tableau__gradebook_audit_student_scaffold") }} as ce
  left join
      {{ ref("int_powerschool__gradebook_assignments_scores") }} as a
      on ce.sections_dcid = a.sectionsdcid
      and ce.students_dcid = a.students_dcid
      and ce.assignment_category_code = a.category_code
      and a.duedate between ce.quarter_start_date and ce.quarter_end_date
      and ce.date_enrolled <= a.duedate
      and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
      and a.iscountedinfinalgrade = 1
      and a.scoretype in ('POINTS', 'PERCENT')
  where ce.scaffold_name = 'student_category_scaffold'
  ```

- [x] **Step 6c.2: Update YAML**

  Remove `assign_s_ms_score_not_conversion_chart_options` and
  `assign_s_hs_score_not_conversion_chart_options` from
  `intermediate/properties/int_tableau__gradebook_audit_assignments_student.yml`.

- [x] **Step 6c.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_assignments_student \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6d: `int_tableau__gradebook_audit_assignments_teacher`

Complete replacement. Changes from the old model:

- `sec.*` → explicit column listing (Bini's rule for tableau schema)
- Date window: `week_start_monday/week_end_sunday` →
  `quarter_start_date/quarter_end_date`
- `s_max_score_greater_100` removed (Miami dead code)
- Exceptions LEFT JOIN removed; `if(e.include_row is null, ...)` pattern
  unwrapped to plain `asg.<col>`
- `ORDER BY sec.week_number_quarter` removed from running count window — no week
  dimension at quarter grain

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_teacher.sql`

- [x] **Step 6d.1: Rewrite the model**

  ```sql
  with
      assignment_score_rollup as (
          select
              _dbt_source_relation,
              assignmentsectionid,

              count(students_dcid) as n_students,

              sum(is_expected_late) as n_late,
              sum(is_exempt) as n_exempt,
              sum(is_expected_missing) as n_missing,
              sum(is_expected_null) as n_null,
              sum(is_expected_academic_dishonesty) as n_academic_dishonesty,

              sum(
                  if(is_expected_null = 1 and is_expected_missing = 1, 1, 0)
              ) as n_is_null_missing,

              sum(
                  if(is_expected_null = 1 and is_expected_missing = 0, 1, 0)
              ) as n_is_null_not_missing,

              countif(is_expected) as n_expected,
              countif(is_expected_scored) as n_expected_scored,

              avg(
                  if(is_expected_scored, assign_final_score_percent, null)
              ) as teacher_avg_score_for_assign_per_class_section_and_assign_id,

          from {{ ref("int_powerschool__gradebook_assignments_scores") }}
          group by _dbt_source_relation, assignmentsectionid
      )

  select
      sec._dbt_source_relation,
      sec.academic_year,
      sec.academic_year_display,
      sec.yearid,
      sec.schoolid,
      sec.school,
      sec.region,
      sec.sections_dcid,
      sec.sectionid,
      sec.section_number,
      sec.external_expression,
      sec.course_number,
      sec.course_name,
      sec.credit_type,
      sec.exclude_from_gpa,
      sec.is_ap_course,
      sec.teacher_number,
      sec.teacher_name,
      sec.teacher_tableau_username,
      sec.manager_employee_number,
      sec.manager_name,
      sec.manager_tableau_username,
      sec.hos,
      sec.school_leader,
      sec.school_leader_tableau_username,
      sec.quarter,
      sec.semester,
      sec.quarter_start_date,
      sec.quarter_end_date,
      sec.is_current_term,
      sec.assignment_category_code,
      sec.assignment_category_name,
      sec.assignment_category_term,
      sec.expectation,
      sec.notes,
      sec.school_level,
      sec.region_school_level,
      sec.section_or_period,
      sec.scaffold_name,

      a.assignmentsectionid,
      a.assignmentid,
      a.name as assignment_name,
      a.duedate,
      a.scoretype,
      a.totalpointvalue,

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

      -- flags
      if(
          sec.assignment_category_code = 'W' and a.totalpointvalue != 10, true, false
      ) as w_assign_max_score_not_10,

      if(
          sec.assignment_category_code = 'F' and a.totalpointvalue != 10, true, false
      ) as f_assign_max_score_not_10,

      if(
          sec.assignment_category_code = 'H'
          and sec.school_level != 'ES'
          and a.totalpointvalue != 10,
          true,
          false
      ) as h_assign_max_score_not_10,

      sum(a.totalpointvalue) over (
          partition by
              sec._dbt_source_relation,
              sec.quarter,
              sec.sectionid,
              sec.assignment_category_code
      ) as sum_totalpointvalue_section_quarter_category,

      count(a.assignmentid) over (
          partition by
              sec._dbt_source_relation, sec.sectionid, sec.assignment_category_term
      ) as teacher_running_total_assign_by_cat,

  from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
  left join
      {{ ref("int_powerschool__gradebook_assignments") }} as a
      on sec.sections_dcid = a.sectionsdcid
      and sec.assignment_category_name = a.category_name
      and a.duedate between sec.quarter_start_date and sec.quarter_end_date
      and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
  left join
      assignment_score_rollup as asg
      on a.assignmentsectionid = asg.assignmentsectionid
      and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
  where sec.scaffold_name = 'teacher_category_scaffold'
  ```

- [x] **Step 6d.2: Update YAML**

  Remove `s_max_score_greater_100` from
  `intermediate/properties/int_tableau__gradebook_audit_assignments_teacher.yml`.

> ✅ **Done:** The `assignment_score_rollup` CTE was extracted into
> `int_powerschool__gradebook_assignment_score_rollup`. Both 6d and 6e now
> `ref()` the shared model and join on `_dbt_source_project` (no macro). The
> inline CTE is removed from both models.

- [x] **Step 6d.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_assignments_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6e: `int_tableau__gradebook_audit_categories_teacher`

Complete replacement. Changes from the old model:

- `assignment_score_rollup` CTE simplified — exception filter removed,
  `GROUP BY` preserved (joining `int_powerschool__gradebook_assignments_scores`
  directly would fan out by student count)
- Date window: `week_start_monday/week_end_sunday` →
  `quarter_start_date/quarter_end_date`
- `week_number_quarter` removed from running count `ORDER BY`
- All week columns removed from `final` CTE SELECT and GROUP BY
- Manager columns added to `final` CTE SELECT and GROUP BY
- `is_quarter_end_date_range`, `quarter_end_date_insession` removed
- Four S-total flags removed from final SELECT:
  `qt_teacher_s_total_greater/less_200/100`
- `f.*` → explicit column listing in final SELECT
- **Per-assignment grain** — `a.assignmentid` and `a.duedate` added to
  `assignments` CTE SELECT; `asg.n_expected` / `asg.n_expected_scored` carried
  directly (no window sum); `final` groups by `assignmentid` + `duedate`; output
  grain is `(section, quarter, category, assignment)`
- `total_expected_section_quarter_category` → `n_expected`;
  `total_expected_scored_section_quarter_category` → `n_expected_scored`;
  `percent_graded_for_quarter_class` → `percent_graded_for_assignment`
- 7-day grace period handled upstream in step 4d.2 (`is_expected` on the scores
  model)
- `final` CTE eliminated — per-assignment grain means each group has exactly one
  row; `avg()` wrappers and `GROUP BY` removed; outer SELECT reads directly
  `from percent_graded as f`

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

- [x] **Step 6e.1: Rewrite the model**

  ```sql
  with
      assignment_score_rollup as (
          select
              _dbt_source_relation,
              assignmentsectionid,

              countif(is_expected) as n_expected,
              countif(is_expected_scored) as n_expected_scored,

          from {{ ref("int_powerschool__gradebook_assignments_scores") }}
          group by 1, 2
      ),

      assignments as (
          select
              sec.*,

              a.assignmentid,
              a.duedate,

              asg.n_expected,
              asg.n_expected_scored,

              count(a.assignmentid) over (
                  partition by
                      sec._dbt_source_relation,
                      sec.sectionid,
                      sec.assignment_category_term
              ) as teacher_running_total_assign_by_cat,

              sum(a.totalpointvalue) over (
                  partition by
                      sec._dbt_source_relation,
                      sec.quarter,
                      sec.sectionid,
                      sec.assignment_category_code
              ) as sum_totalpointvalue_section_quarter_category,

          from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
          left join
              {{ ref("int_powerschool__gradebook_assignments") }} as a
              on sec.sections_dcid = a.sectionsdcid
              and sec.assignment_category_name = a.category_name
              and a.duedate between sec.quarter_start_date and sec.quarter_end_date
              and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
          left join
              assignment_score_rollup as asg
              on a.assignmentsectionid = asg.assignmentsectionid
              and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
          where sec.scaffold_name = 'teacher_category_scaffold'
      ),

      percent_graded as (
          select
              *,

              safe_divide(
                  n_expected_scored,
                  n_expected
              ) as percent_graded_for_assignment,

          from assignments
      ),

  select
      f._dbt_source_relation,
      f.schoolid,
      f.yearid,
      f.academic_year,
      f.quarter,
      f.semester,
      f.quarter_start_date,
      f.quarter_end_date,
      f.is_current_term,
      f.school,
      f.region,
      f.school_level,
      f.region_school_level,
      f.academic_year_display,
      f.sections_dcid,
      f.sectionid,
      f.section_number,
      f.external_expression,
      f.course_number,
      f.course_name,
      f.credit_type,
      f.exclude_from_gpa,
      f.is_ap_course,
      f.teacher_number,
      f.teacher_name,
      f.teacher_tableau_username,
      f.manager_employee_number,
      f.manager_name,
      f.manager_tableau_username,
      f.hos,
      f.school_leader,
      f.school_leader_tableau_username,
      f.section_or_period,
      f.assignment_category_code,
      f.assignment_category_name,
      f.assignment_category_term,
      f.notes,
      f.assignmentid,
      f.duedate,
      f.expectation,
      f.teacher_running_total_assign_by_cat,
      f.sum_totalpointvalue_section_quarter_category,
      f.n_expected,
      f.n_expected_scored,
      f.percent_graded_for_assignment,

      -- flags
      if(
          f.assignment_category_code = 'W'
          and f.percent_graded_for_assignment < .7,
          true,
          false
      ) as w_percent_graded_min_not_met,

      if(
          f.assignment_category_code = 'H'
          and f.percent_graded_for_assignment < .7,
          true,
          false
      ) as h_percent_graded_min_not_met,

      if(
          f.assignment_category_code = 'F'
          and f.percent_graded_for_assignment < .7,
          true,
          false
      ) as f_percent_graded_min_not_met,

      if(
          f.assignment_category_code = 'S'
          and f.percent_graded_for_assignment < .7,
          true,
          false
      ) as s_percent_graded_min_not_met,

      if(
          f.assignment_category_code = 'W'
          and f.teacher_running_total_assign_by_cat < f.expectation,
          true,
          false
      ) as w_expected_assign_count_not_met,

      if(
          f.assignment_category_code = 'H'
          and f.teacher_running_total_assign_by_cat < f.expectation,
          true,
          false
      ) as h_expected_assign_count_not_met,

      if(
          f.assignment_category_code = 'F'
          and f.teacher_running_total_assign_by_cat < f.expectation,
          true,
          false
      ) as f_expected_assign_count_not_met,

      if(
          f.assignment_category_code = 'S'
          and f.teacher_running_total_assign_by_cat < f.expectation,
          true,
          false
      ) as s_expected_assign_count_not_met,

  from percent_graded as f
  ```

- [x] **Step 6e.2: Update YAML**

  Remove all four S-total column entries from
  `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`.
  Update column names: `total_expected_section_quarter_week_category` →
  `n_expected`, `total_expected_scored_section_quarter_week_category` →
  `n_expected_scored`, `percent_graded_for_quarter_week_class` →
  `percent_graded_for_assignment`. Add `assignmentid`, `duedate`, and manager
  columns.

- [x] **Step 6e.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_categories_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6f: `int_tableau__gradebook_audit_flags.sql` — complete rewrite

Complete replacement. Changes from the old model:

**CTEs:**

- `student_unpivot`: remove 3 exception JOINs; remove
  `assign_s_ms_score_not_conversion_chart_options` and
  `assign_s_hs_score_not_conversion_chart_options` from UNPIVOT list
- `teacher_unpivot_cca`: remove 2 exception JOINs; remove
  `s_max_score_greater_100` from UNPIVOT list
- `teacher_unpivot_cc`: remove 1 exception JOIN; remove 4 S-total flags from
  UNPIVOT list
- `eoq_items`: remove 1 exception JOIN; remove `qt_comment_missing`,
  `qt_g1_g8_conduct_code_missing`, `qt_g1_g8_conduct_code_incorrect`,
  `qt_student_is_ada_80_plus_gpa_less_2` from UNPIVOT list; remaining:
  `qt_es_comment_missing`, `qt_grade_70_comment_missing`,
  `qt_percent_grade_greater_100`
- `student_course_category` CTE: deleted entirely
- `eoq_items_conduct_code` CTE: deleted entirely

**UNION ALL branches — all 4 remaining branches:**

- Remove 8 week columns, `is_quarter_end_date_range`,
  `quarter_end_date_insession`, `quarter_conduct`,
  `category_quarter_average_all_courses`, `assign_expected_to_be_scored`,
  `assign_expected_with_score`
- Add `manager_employee_number`, `manager_name`, `manager_tableau_username` —
  real in all branches (student scaffold and assignments_student both carry
  manager columns; nulling them while teacher name is populated would be
  incorrect)
- Remove `total_expected_section_quarter_week_category` and
  `total_expected_scored_section_quarter_week_category` null placeholders —
  superseded by `n_expected`/`n_expected_scored` already in the output
- Rename `percent_graded_for_quarter_week_class` →
  `percent_graded_for_assignment`
- In `teacher_unpivot_cc` branch:
  `null as n_expected`/`null as n_expected_scored` →
  `r.n_expected`/`r.n_expected_scored` (now real from `categories_teacher`
  per-assignment grain)
- Remove `and r.week_number_quarter = t.week_number_quarter` from the
  `assignments_teacher` join in the first branch
- Pre-existing bug fixes: `null as um_totalpointvalue_section_quarter_category`
  → `null as sum_totalpointvalue_section_quarter_category`; `null as expected_`
  → `null as is_expected_late`

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags.sql`

- [x] **Step 6f.1: Rewrite the model**

  ```sql
  with
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

      teacher_unpivot_cca as (
          select r.*, f.cte_grouping, f.audit_category, f.code_type,

          from
              {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} unpivot (
                  audit_flag_value for audit_flag_name in (
                      w_assign_max_score_not_10,
                      h_assign_max_score_not_10,
                      f_assign_max_score_not_10
                  )
              ) as r
          inner join
              {{ ref("stg_google_sheets__gradebook_flags") }} as f
              on r.academic_year = f.academic_year
              and r.region = f.region
              and r.school_level = f.school_level
              and r.assignment_category_code = f.code
              and r.audit_flag_name = f.audit_flag_name
              and f.cte_grouping = 'class_category_assignment'
      ),

      teacher_unpivot_cc as (
          select r.*, f.cte_grouping, f.audit_category, f.code_type,

          from
              {{ ref("int_tableau__gradebook_audit_categories_teacher") }} unpivot (
                  audit_flag_value for audit_flag_name in (
                      w_expected_assign_count_not_met,
                      h_expected_assign_count_not_met,
                      f_expected_assign_count_not_met,
                      s_expected_assign_count_not_met,
                      w_percent_graded_min_not_met,
                      h_percent_graded_min_not_met,
                      f_percent_graded_min_not_met,
                      s_percent_graded_min_not_met
                  )
              ) as r
          inner join
              {{ ref("stg_google_sheets__gradebook_flags") }} as f
              on r.academic_year = f.academic_year
              and r.region = f.region
              and r.school_level = f.school_level
              and r.assignment_category_code = f.code
              and r.audit_flag_name = f.audit_flag_name
              and f.cte_grouping = 'class_category'
      ),

      eoq_items as (
          select r.*, f.cte_grouping, f.audit_category, f.code_type,

          from
              {{ ref("int_tableau__gradebook_audit_student_scaffold") }} unpivot (
                  audit_flag_value for audit_flag_name in (
                      qt_es_comment_missing,
                      qt_grade_70_comment_missing,
                      qt_percent_grade_greater_100
                  )
              ) as r
          inner join
              {{ ref("stg_google_sheets__gradebook_flags") }} as f
              on r.academic_year = f.academic_year
              and r.region = f.region
              and r.school_level = f.school_level
              and r.quarter = f.code
              and r.audit_flag_name = f.audit_flag_name
              and r.scaffold_name = 'student_scaffold'
              and f.cte_grouping in ('student_course', 'student')
              and f.audit_category != 'Conduct Code'
      )

  -- student assignment-level flags
  select
      r._dbt_source_relation,
      r.academic_year,
      r.academic_year_display,
      r.yearid,
      r.region,
      r.school_level,
      r.schoolid,
      r.school,
      r.students_dcid,
      r.studentid,
      r.student_number,
      r.student_name,
      r.grade_level,
      r.salesforce_id,
      r.ktc_cohort,
      r.enroll_status,
      r.cohort,
      r.gender,
      r.ethnicity,
      r.advisory,
      r.hos,
      r.region_school_level,
      r.year_in_school,
      r.year_in_network,
      r.rn_undergrad,
      r.is_out_of_district,
      r.is_self_contained,
      r.is_retained_year,
      r.is_retained_ever,
      r.lunch_status,
      r.gifted_and_talented,
      r.iep_status,
      r.lep_status,
      r.is_504,
      r.is_counseling_services,
      r.is_student_athlete,
      r.ada,
      r.ada_above_or_at_80,
      r.sectionid,
      r.course_number,
      r.date_enrolled,
      r.sections_dcid,
      r.section_number,
      r.external_expression,
      r.termid,
      r.credit_type,
      r.course_name,
      r.exclude_from_gpa,
      r.teacher_number,
      r.teacher_name,
      r.is_ap_course,
      r.teacher_tableau_username,
      r.manager_employee_number,
      r.manager_name,
      r.manager_tableau_username,
      r.school_leader,
      r.school_leader_tableau_username,
      r.quarter,
      r.semester,
      r.quarter_start_date,
      r.quarter_end_date,
      r.is_current_term,
      r.quarter_course_percent_grade,
      r.quarter_course_grade_points,
      r.quarter_comment_value,
      r.section_or_period,
      r.assignment_category_name,
      r.assignment_category_code,
      r.assignment_category_term,
      r.expectation,
      r.notes,
      r.category_quarter_percent_grade,
      r.assignmentid,
      r.assignment_name,
      r.duedate,
      r.scoretype,
      r.totalpointvalue,
      r.scorepoints,
      r.is_expected_late,
      r.is_exempt,
      r.is_expected_missing,
      r.is_expected_zero,
      r.is_expected_academic_dishonesty,
      r.score_entered,
      r.assign_final_score_percent,
      r.cte_grouping,
      r.audit_flag_name,

      t.n_students,
      t.n_late,
      t.n_exempt,
      t.n_missing,
      t.n_academic_dishonesty,
      t.n_null,
      t.n_is_null_missing,
      t.n_is_null_not_missing,
      t.n_expected,
      t.n_expected_scored,

      null as percent_graded_for_assignment,

      t.sum_totalpointvalue_section_quarter_category,
      t.teacher_running_total_assign_by_cat,
      t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

      r.audit_category,
      r.code_type,

      if(r.audit_flag_value, 1, 0) as audit_flag_value,

  from student_unpivot as r
  left join
      {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} as t
      on r.region = t.region
      and r.schoolid = t.schoolid
      and r.quarter = t.quarter
      and r.sectionid = t.sectionid
      and r.assignmentid = t.assignmentid

  union all

  -- EOQ student-course flags
  select
      _dbt_source_relation,
      academic_year,
      academic_year_display,
      yearid,
      region,
      school_level,
      schoolid,
      school,
      students_dcid,
      studentid,
      student_number,
      student_name,
      grade_level,
      salesforce_id,
      ktc_cohort,
      enroll_status,
      cohort,
      gender,
      ethnicity,
      advisory,
      hos,
      region_school_level,
      year_in_school,
      year_in_network,
      rn_undergrad,
      is_out_of_district,
      is_self_contained,
      is_retained_year,
      is_retained_ever,
      lunch_status,
      gifted_and_talented,
      iep_status,
      lep_status,
      is_504,
      is_counseling_services,
      is_student_athlete,
      ada,
      ada_above_or_at_80,
      sectionid,
      course_number,
      date_enrolled,
      sections_dcid,
      section_number,
      external_expression,
      termid,
      credit_type,
      course_name,
      exclude_from_gpa,
      teacher_number,
      teacher_name,
      is_ap_course,
      teacher_tableau_username,
      manager_employee_number,
      manager_name,
      manager_tableau_username,
      school_leader,
      school_leader_tableau_username,
      `quarter`,
      semester,
      quarter_start_date,
      quarter_end_date,
      is_current_term,
      quarter_course_percent_grade,
      quarter_course_grade_points,
      quarter_comment_value,
      section_or_period,

      null as assignment_category_name,
      null as assignment_category_code,
      null as assignment_category_term,
      null as expectation,
      null as notes,
      null as category_quarter_percent_grade,
      null as assignmentid,
      null as assignment_name,
      null as duedate,
      null as scoretype,
      null as totalpointvalue,
      null as scorepoints,
      null as is_expected_late,
      null as is_exempt,
      null as is_expected_missing,
      null as is_expected_zero,
      null as is_expected_academic_dishonesty,
      null as score_entered,
      null as assign_final_score_percent,

      cte_grouping,
      audit_flag_name,

      null as n_students,
      null as n_late,
      null as n_exempt,
      null as n_missing,
      null as n_academic_dishonesty,
      null as n_null,
      null as n_is_null_missing,
      null as n_is_null_not_missing,
      null as n_expected,
      null as n_expected_scored,

      null as percent_graded_for_assignment,
      null as sum_totalpointvalue_section_quarter_category,
      null as teacher_running_total_assign_by_cat,
      null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

      audit_category,
      code_type,

      if(audit_flag_value, 1, 0) as audit_flag_value,

  from eoq_items

  union all

  -- class_category_assignment: w/h/f_assign_max_score_not_10
  select
      r._dbt_source_relation,
      r.academic_year,
      r.academic_year_display,
      r.yearid,
      r.region,
      r.school_level,
      r.schoolid,
      r.school,

      null as students_dcid,
      null as studentid,
      null as student_number,
      null as student_name,
      null as grade_level,
      null as salesforce_id,
      null as ktc_cohort,
      null as enroll_status,
      null as cohort,
      null as gender,
      null as ethnicity,
      null as advisory,

      r.hos,
      r.region_school_level,

      null as year_in_school,
      null as year_in_network,
      null as rn_undergrad,
      null as is_out_of_district,
      null as is_self_contained,
      null as is_retained_year,
      null as is_retained_ever,
      null as lunch_status,
      null as gifted_and_talented,
      null as iep_status,
      null as lep_status,
      null as is_504,
      null as is_counseling_services,
      null as is_student_athlete,
      null as ada,
      null as ada_above_or_at_80,

      r.sectionid,
      r.course_number,

      null as date_enrolled,

      r.sections_dcid,
      r.section_number,
      r.external_expression,

      null as termid,

      r.credit_type,
      r.course_name,
      r.exclude_from_gpa,
      r.teacher_number,
      r.teacher_name,
      r.is_ap_course,
      r.teacher_tableau_username,
      r.manager_employee_number,
      r.manager_name,
      r.manager_tableau_username,
      r.school_leader,
      r.school_leader_tableau_username,
      r.quarter,
      r.semester,
      r.quarter_start_date,
      r.quarter_end_date,
      r.is_current_term,

      null as quarter_course_percent_grade,
      null as quarter_course_grade_points,
      null as quarter_comment_value,

      r.section_or_period,
      r.assignment_category_name,
      r.assignment_category_code,
      r.assignment_category_term,
      r.expectation,
      r.notes,

      null as category_quarter_percent_grade,

      r.assignmentid,
      r.assignment_name,
      r.duedate,
      r.scoretype,
      r.totalpointvalue,

      null as scorepoints,
      null as is_expected_late,
      null as is_exempt,
      null as is_expected_missing,
      null as is_expected_zero,
      null as is_expected_academic_dishonesty,
      null as score_entered,
      null as assign_final_score_percent,

      r.cte_grouping,
      r.audit_flag_name,

      r.n_students,
      r.n_late,
      r.n_exempt,
      r.n_missing,
      r.n_academic_dishonesty,
      r.n_null,
      r.n_is_null_missing,
      r.n_is_null_not_missing,
      r.n_expected,
      r.n_expected_scored,

      null as percent_graded_for_assignment,
      null as sum_totalpointvalue_section_quarter_category,
      null as teacher_running_total_assign_by_cat,

      r.teacher_avg_score_for_assign_per_class_section_and_assign_id,
      r.audit_category,
      r.code_type,

      if(r.audit_flag_value, 1, 0) as audit_flag_value,

  from teacher_unpivot_cca as r

  union all

  -- class_category: w/h/f/s_expected_assign_count_not_met, w/h/f/s_percent_graded_min_not_met
  select
      r._dbt_source_relation,
      r.academic_year,
      r.academic_year_display,
      r.yearid,
      r.region,
      r.school_level,
      r.schoolid,
      r.school,

      null as students_dcid,
      null as studentid,
      null as student_number,
      null as student_name,
      null as grade_level,
      null as salesforce_id,
      null as ktc_cohort,
      null as enroll_status,
      null as cohort,
      null as gender,
      null as ethnicity,
      null as advisory,

      r.hos,
      r.region_school_level,

      null as year_in_school,
      null as year_in_network,
      null as rn_undergrad,
      null as is_out_of_district,
      null as is_self_contained,
      null as is_retained_year,
      null as is_retained_ever,
      null as lunch_status,
      null as gifted_and_talented,
      null as iep_status,
      null as lep_status,
      null as is_504,
      null as is_counseling_services,
      null as is_student_athlete,
      null as ada,
      null as ada_above_or_at_80,

      r.sectionid,
      r.course_number,

      null as date_enrolled,

      r.sections_dcid,
      r.section_number,
      r.external_expression,

      null as termid,

      r.credit_type,
      r.course_name,
      r.exclude_from_gpa,
      r.teacher_number,
      r.teacher_name,
      r.is_ap_course,
      r.teacher_tableau_username,
      r.manager_employee_number,
      r.manager_name,
      r.manager_tableau_username,
      r.school_leader,
      r.school_leader_tableau_username,
      r.quarter,
      r.semester,
      r.quarter_start_date,
      r.quarter_end_date,
      r.is_current_term,

      null as quarter_course_percent_grade,
      null as quarter_course_grade_points,
      null as quarter_comment_value,

      r.section_or_period,
      r.assignment_category_name,
      r.assignment_category_code,
      r.assignment_category_term,
      r.expectation,
      r.notes,

      null as category_quarter_percent_grade,
      r.assignmentid,
      null as assignment_name,
      r.duedate,
      null as scoretype,
      null as totalpointvalue,
      null as scorepoints,
      null as is_expected_late,
      null as is_exempt,
      null as is_expected_missing,
      null as is_expected_zero,
      null as is_expected_academic_dishonesty,
      null as score_entered,
      null as assign_final_score_percent,

      r.cte_grouping,
      r.audit_flag_name,

      null as n_students,
      null as n_late,
      null as n_exempt,
      null as n_missing,
      null as n_academic_dishonesty,
      null as n_null,
      null as n_is_null_missing,
      null as n_is_null_not_missing,
      r.n_expected,
      r.n_expected_scored,

      r.percent_graded_for_assignment,
      r.sum_totalpointvalue_section_quarter_category,
      r.teacher_running_total_assign_by_cat,

      null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

      r.audit_category,
      r.code_type,

      if(r.audit_flag_value, 1, 0) as audit_flag_value,

  from teacher_unpivot_cc as r
  ```

- [x] **Step 6f.2: Update YAML**

  In `intermediate/properties/int_tableau__gradebook_audit_flags.yml`:
  - Remove columns: all week columns, `is_quarter_end_date_range`,
    `quarter_end_date_insession`, `quarter_conduct`,
    `category_quarter_average_all_courses`, `assign_expected_to_be_scored`,
    `assign_expected_with_score`
  - Remove deleted flag columns:
    `assign_s_ms_score_not_conversion_chart_options`,
    `assign_s_hs_score_not_conversion_chart_options`, `s_max_score_greater_100`,
    4 S-total flags, `qt_comment_missing`, `qt_g1_g8_conduct_code_*`,
    `qt_student_is_ada_80_plus_gpa_less_2`
  - Rename: `total_expected_section_quarter_week_category` → removed (merged
    into `n_expected`), `total_expected_scored_section_quarter_week_category` →
    removed, `percent_graded_for_quarter_week_class` →
    `percent_graded_for_assignment`
  - Add: `manager_employee_number`, `manager_name`, `manager_tableau_username`

- [x] **Step 6f.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_flags \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6g: `rpt_tableau__gradebook_audit.sql` — complete rewrite

Complete replacement. Changes from the old model:

**`teacher_aggs` CTE:**

- Remove: `week_number_quarter as audit_qt_week_number`,
  `is_quarter_end_date_range`, `week_start_monday as audit_start_date`,
  `week_end_sunday as audit_end_date`,
  `school_week_start_date_lead as audit_due_date`, computed `is_current_week`
  expression
- Remove: `total_expected_scored_section_quarter_week_category`,
  `total_expected_section_quarter_week_category` (renamed to `n_expected*` in
  flags)
- Rename: `percent_graded_for_quarter_week_class` →
  `percent_graded_for_assignment`
- Add: `manager_employee_number`, `manager_name`, `manager_tableau_username`

**`valid_flags` CTE:**

- Remove: `week_number_quarter as audit_qt_week_number`,
  `category_quarter_average_all_courses`, `quarter_conduct`

**UNION branches:**

- Delete second branch (`cte_grouping = 'student_course_category'`) — that CTE
  no longer exists in flags; shrinks from 5 to 4 branches
- All 4 remaining join conditions: remove
  `t.audit_qt_week_number = v.audit_qt_week_number`
- All 4 WHERE clauses: remove `t.audit_start_date <= current_date(...)` and
  `not t.is_current_week` (week dimension gone; grace period handled upstream)
- Branch 3 WHERE: remove `cte_grouping != 'student_course_category'` (vacuously
  true now)

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`

- [x] **Step 6g.1: Rewrite the model**

  ```sql
  with
      anchor as (
          select
              academic_year,
              academic_year_display,
              region,
              school_level,
              region_school_level,
              schoolid,
              school,
              `quarter`,
              semester,
              quarter_start_date,
              quarter_end_date,
              is_current_term as is_current_quarter,
              section_or_period,
              sectionid,
              sections_dcid,
              section_number,
              external_expression,
              credit_type,
              course_number,
              course_name,
              exclude_from_gpa,
              is_ap_course,
              teacher_number,
              teacher_name,
              teacher_tableau_username,
              manager_employee_number,
              manager_name,
              manager_tableau_username,
              school_leader,
              school_leader_tableau_username,

              max(audit_flag_value) = 0 as is_healthy_gradebook,

          from {{ ref("int_tableau__gradebook_audit_flags") }}
          group by
              academic_year,
              academic_year_display,
              region,
              school_level,
              region_school_level,
              schoolid,
              school,
              `quarter`,
              semester,
              quarter_start_date,
              quarter_end_date,
              is_current_term,
              section_or_period,
              sectionid,
              sections_dcid,
              section_number,
              external_expression,
              credit_type,
              course_number,
              course_name,
              exclude_from_gpa,
              is_ap_course,
              teacher_number,
              teacher_name,
              teacher_tableau_username,
              manager_employee_number,
              manager_name,
              manager_tableau_username,
              school_leader,
              school_leader_tableau_username
      ),

      teacher_aggs as (
          select
              academic_year,
              academic_year_display,
              region,
              school_level,
              region_school_level,
              schoolid,
              school,
              `quarter`,
              semester,
              quarter_start_date,
              quarter_end_date,
              is_current_term as is_current_quarter,
              assignment_category_name,
              assignment_category_code,
              assignment_category_term,
              expectation,
              notes,
              section_or_period,
              sectionid,
              sections_dcid,
              section_number,
              external_expression,
              credit_type,
              course_number,
              course_name,
              exclude_from_gpa,
              is_ap_course,
              teacher_number,
              teacher_name,
              teacher_tableau_username,
              manager_employee_number,
              manager_name,
              manager_tableau_username,
              school_leader,
              school_leader_tableau_username,
              assignmentid as teacher_assign_id,
              assignment_name as teacher_assign_name,
              duedate as teacher_assign_due_date,
              scoretype as teacher_assign_score_type,
              totalpointvalue as teacher_assign_max_score,
              n_students,
              n_late,
              n_exempt,
              n_missing,
              n_null,
              n_academic_dishonesty,
              n_is_null_missing,
              n_is_null_not_missing,
              n_expected,
              n_expected_scored,
              percent_graded_for_assignment,
              sum_totalpointvalue_section_quarter_category,
              teacher_running_total_assign_by_cat,
              teacher_avg_score_for_assign_per_class_section_and_assign_id,
              audit_category,
              cte_grouping,
              code_type,
              audit_flag_name,

              max(audit_flag_value) as audit_flag_value,

          from {{ ref("int_tableau__gradebook_audit_flags") }}
          group by all
      ),

      valid_flags as (
          select
              academic_year,
              region,
              schoolid,
              `quarter`,
              assignment_category_term,
              sectionid,
              teacher_number,
              assignmentid as teacher_assign_id,
              studentid,
              student_number,
              student_name,
              grade_level,
              salesforce_id,
              ktc_cohort,
              enroll_status,
              cohort,
              gender,
              ethnicity,
              advisory,
              year_in_school,
              year_in_network,
              rn_undergrad,
              is_out_of_district,
              is_retained_year,
              is_retained_ever,
              lunch_status,
              gifted_and_talented,
              iep_status,
              lep_status,
              is_504,
              is_counseling_services,
              is_student_athlete,
              ada,
              ada_above_or_at_80,
              date_enrolled,
              category_quarter_percent_grade,
              quarter_course_percent_grade,
              quarter_course_grade_points,
              quarter_comment_value,
              scorepoints as raw_score,
              score_entered,
              assign_final_score_percent,
              is_exempt,
              is_expected_late,
              is_expected_missing,
              is_expected_academic_dishonesty,
              audit_category,
              cte_grouping,
              code_type,
              audit_flag_name,
              audit_flag_value as flag_value,

          from {{ ref("int_tableau__gradebook_audit_flags") }}
          where audit_flag_value = 1
      )

  -- anchor rows: one per section × quarter, healthy/not healthy, no flag/student detail
  select
      academic_year,
      academic_year_display,
      region,
      school_level,
      region_school_level,
      schoolid,
      school,
      `quarter`,
      semester,
      quarter_start_date,
      quarter_end_date,
      is_current_quarter,
      null as assignment_category_name,
      null as assignment_category_code,
      null as assignment_category_term,
      null as expectation,
      null as notes,
      section_or_period,
      sectionid,
      sections_dcid,
      section_number,
      external_expression,
      credit_type,
      course_number,
      course_name,
      exclude_from_gpa,
      is_ap_course,
      teacher_number,
      teacher_name,
      teacher_tableau_username,
      manager_employee_number,
      manager_name,
      manager_tableau_username,
      school_leader,
      school_leader_tableau_username,
      null as teacher_assign_id,
      null as teacher_assign_name,
      null as teacher_assign_due_date,
      null as teacher_assign_score_type,
      null as teacher_assign_max_score,
      null as n_students,
      null as n_late,
      null as n_exempt,
      null as n_missing,
      null as n_null,
      null as n_academic_dishonesty,
      null as n_is_null_missing,
      null as n_is_null_not_missing,
      null as n_expected,
      null as n_expected_scored,
      null as percent_graded_for_assignment,
      null as sum_totalpointvalue_section_quarter_category,
      null as teacher_running_total_assign_by_cat,
      null as teacher_avg_score_for_assign_per_class_section_and_assign_id,
      null as audit_category,
      null as cte_grouping,
      null as code_type,
      'no_active_flags' as audit_flag_name,
      null as audit_flag_value,
      null as studentid,
      null as student_number,
      null as student_name,
      null as grade_level,
      null as salesforce_id,
      null as ktc_cohort,
      null as enroll_status,
      null as cohort,
      null as gender,
      null as ethnicity,
      null as advisory,
      null as year_in_school,
      null as year_in_network,
      null as rn_undergrad,
      null as is_out_of_district,
      null as is_retained_year,
      null as is_retained_ever,
      null as lunch_status,
      null as gifted_and_talented,
      null as iep_status,
      null as lep_status,
      null as is_504,
      null as is_counseling_services,
      null as is_student_athlete,
      null as ada,
      null as ada_above_or_at_80,
      null as date_enrolled,
      null as category_quarter_percent_grade,
      null as quarter_course_percent_grade,
      null as quarter_course_grade_points,
      null as quarter_comment_value,
      null as raw_score,
      null as score_entered,
      null as assign_final_score_percent,
      null as is_exempt,
      null as is_expected_late,
      null as is_expected_missing,
      null as is_expected_academic_dishonesty,
      true as is_anchor_row,
      is_healthy_gradebook,
      null as flag_value,

  from anchor

  union all

  -- flag rows: assignment_student (Gradebook Category, student-assignment grain)
  select
      t.academic_year,
      t.academic_year_display,
      t.region,
      t.school_level,
      t.region_school_level,
      t.schoolid,
      t.school,
      t.`quarter`,
      t.semester,
      t.quarter_start_date,
      t.quarter_end_date,
      t.is_current_quarter,
      t.assignment_category_name,
      t.assignment_category_code,
      t.assignment_category_term,
      t.expectation,
      t.notes,
      t.section_or_period,
      t.sectionid,
      t.sections_dcid,
      t.section_number,
      t.external_expression,
      t.credit_type,
      t.course_number,
      t.course_name,
      t.exclude_from_gpa,
      t.is_ap_course,
      t.teacher_number,
      t.teacher_name,
      t.teacher_tableau_username,
      t.manager_employee_number,
      t.manager_name,
      t.manager_tableau_username,
      t.school_leader,
      t.school_leader_tableau_username,
      t.teacher_assign_id,
      t.teacher_assign_name,
      t.teacher_assign_due_date,
      t.teacher_assign_score_type,
      t.teacher_assign_max_score,
      t.n_students,
      t.n_late,
      t.n_exempt,
      t.n_missing,
      t.n_null,
      t.n_academic_dishonesty,
      t.n_is_null_missing,
      t.n_is_null_not_missing,
      t.n_expected,
      t.n_expected_scored,
      t.percent_graded_for_assignment,
      t.sum_totalpointvalue_section_quarter_category,
      t.teacher_running_total_assign_by_cat,
      t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
      t.audit_category,
      t.cte_grouping,
      t.code_type,
      t.audit_flag_name,
      t.audit_flag_value,
      v.studentid,
      v.student_number,
      v.student_name,
      v.grade_level,
      v.salesforce_id,
      v.ktc_cohort,
      v.enroll_status,
      v.cohort,
      v.gender,
      v.ethnicity,
      v.advisory,
      v.year_in_school,
      v.year_in_network,
      v.rn_undergrad,
      v.is_out_of_district,
      v.is_retained_year,
      v.is_retained_ever,
      v.lunch_status,
      v.gifted_and_talented,
      v.iep_status,
      v.lep_status,
      v.is_504,
      v.is_counseling_services,
      v.is_student_athlete,
      v.ada,
      v.ada_above_or_at_80,
      v.date_enrolled,
      v.category_quarter_percent_grade,
      v.quarter_course_percent_grade,
      v.quarter_course_grade_points,
      v.quarter_comment_value,
      v.raw_score,
      v.score_entered,
      v.assign_final_score_percent,
      v.is_exempt,
      v.is_expected_late,
      v.is_expected_missing,
      v.is_expected_academic_dishonesty,
      false as is_anchor_row,
      null as is_healthy_gradebook,
      v.flag_value,

  from teacher_aggs as t
  inner join
      valid_flags as v
      on t.academic_year = v.academic_year
      and t.region = v.region
      and t.schoolid = v.schoolid
      and t.quarter = v.quarter
      and t.sectionid = v.sectionid
      and t.teacher_number = v.teacher_number
      and t.assignment_category_term = v.assignment_category_term
      and t.teacher_assign_id = v.teacher_assign_id
      and t.audit_category = v.audit_category
      and t.cte_grouping = v.cte_grouping
      and t.audit_flag_name = v.audit_flag_name
  where
      t.code_type = 'Gradebook Category'
      and t.cte_grouping = 'assignment_student'

  union all

  -- flag rows: eoq_items (Quarter grain)
  select
      t.academic_year,
      t.academic_year_display,
      t.region,
      t.school_level,
      t.region_school_level,
      t.schoolid,
      t.school,
      t.`quarter`,
      t.semester,
      t.quarter_start_date,
      t.quarter_end_date,
      t.is_current_quarter,
      t.assignment_category_name,
      t.assignment_category_code,
      t.assignment_category_term,
      t.expectation,
      t.notes,
      t.section_or_period,
      t.sectionid,
      t.sections_dcid,
      t.section_number,
      t.external_expression,
      t.credit_type,
      t.course_number,
      t.course_name,
      t.exclude_from_gpa,
      t.is_ap_course,
      t.teacher_number,
      t.teacher_name,
      t.teacher_tableau_username,
      t.manager_employee_number,
      t.manager_name,
      t.manager_tableau_username,
      t.school_leader,
      t.school_leader_tableau_username,
      t.teacher_assign_id,
      t.teacher_assign_name,
      t.teacher_assign_due_date,
      t.teacher_assign_score_type,
      t.teacher_assign_max_score,
      t.n_students,
      t.n_late,
      t.n_exempt,
      t.n_missing,
      t.n_null,
      t.n_academic_dishonesty,
      t.n_is_null_missing,
      t.n_is_null_not_missing,
      t.n_expected,
      t.n_expected_scored,
      t.percent_graded_for_assignment,
      t.sum_totalpointvalue_section_quarter_category,
      t.teacher_running_total_assign_by_cat,
      t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
      t.audit_category,
      t.cte_grouping,
      t.code_type,
      t.audit_flag_name,
      t.audit_flag_value,
      v.studentid,
      v.student_number,
      v.student_name,
      v.grade_level,
      v.salesforce_id,
      v.ktc_cohort,
      v.enroll_status,
      v.cohort,
      v.gender,
      v.ethnicity,
      v.advisory,
      v.year_in_school,
      v.year_in_network,
      v.rn_undergrad,
      v.is_out_of_district,
      v.is_retained_year,
      v.is_retained_ever,
      v.lunch_status,
      v.gifted_and_talented,
      v.iep_status,
      v.lep_status,
      v.is_504,
      v.is_counseling_services,
      v.is_student_athlete,
      v.ada,
      v.ada_above_or_at_80,
      v.date_enrolled,
      v.category_quarter_percent_grade,
      v.quarter_course_percent_grade,
      v.quarter_course_grade_points,
      v.quarter_comment_value,
      v.raw_score,
      v.score_entered,
      v.assign_final_score_percent,
      v.is_exempt,
      v.is_expected_late,
      v.is_expected_missing,
      v.is_expected_academic_dishonesty,
      false as is_anchor_row,
      null as is_healthy_gradebook,
      v.flag_value,

  from teacher_aggs as t
  inner join
      valid_flags as v
      on t.academic_year = v.academic_year
      and t.region = v.region
      and t.schoolid = v.schoolid
      and t.quarter = v.quarter
      and t.sectionid = v.sectionid
      and t.teacher_number = v.teacher_number
      and t.audit_category = v.audit_category
      and t.cte_grouping = v.cte_grouping
      and t.audit_flag_name = v.audit_flag_name
  where
      t.code_type = 'Quarter'

  union all

  -- flag rows: class_category_assignment (Gradebook Category, class-assignment grain)
  select
      t.academic_year,
      t.academic_year_display,
      t.region,
      t.school_level,
      t.region_school_level,
      t.schoolid,
      t.school,
      t.`quarter`,
      t.semester,
      t.quarter_start_date,
      t.quarter_end_date,
      t.is_current_quarter,
      t.assignment_category_name,
      t.assignment_category_code,
      t.assignment_category_term,
      t.expectation,
      t.notes,
      t.section_or_period,
      t.sectionid,
      t.sections_dcid,
      t.section_number,
      t.external_expression,
      t.credit_type,
      t.course_number,
      t.course_name,
      t.exclude_from_gpa,
      t.is_ap_course,
      t.teacher_number,
      t.teacher_name,
      t.teacher_tableau_username,
      t.manager_employee_number,
      t.manager_name,
      t.manager_tableau_username,
      t.school_leader,
      t.school_leader_tableau_username,
      t.teacher_assign_id,
      t.teacher_assign_name,
      t.teacher_assign_due_date,
      t.teacher_assign_score_type,
      t.teacher_assign_max_score,
      t.n_students,
      t.n_late,
      t.n_exempt,
      t.n_missing,
      t.n_null,
      t.n_academic_dishonesty,
      t.n_is_null_missing,
      t.n_is_null_not_missing,
      t.n_expected,
      t.n_expected_scored,
      t.percent_graded_for_assignment,
      t.sum_totalpointvalue_section_quarter_category,
      t.teacher_running_total_assign_by_cat,
      t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
      t.audit_category,
      t.cte_grouping,
      t.code_type,
      t.audit_flag_name,
      t.audit_flag_value,
      v.studentid,
      v.student_number,
      v.student_name,
      v.grade_level,
      v.salesforce_id,
      v.ktc_cohort,
      v.enroll_status,
      v.cohort,
      v.gender,
      v.ethnicity,
      v.advisory,
      v.year_in_school,
      v.year_in_network,
      v.rn_undergrad,
      v.is_out_of_district,
      v.is_retained_year,
      v.is_retained_ever,
      v.lunch_status,
      v.gifted_and_talented,
      v.iep_status,
      v.lep_status,
      v.is_504,
      v.is_counseling_services,
      v.is_student_athlete,
      v.ada,
      v.ada_above_or_at_80,
      v.date_enrolled,
      v.category_quarter_percent_grade,
      v.quarter_course_percent_grade,
      v.quarter_course_grade_points,
      v.quarter_comment_value,
      v.raw_score,
      v.score_entered,
      v.assign_final_score_percent,
      v.is_exempt,
      v.is_expected_late,
      v.is_expected_missing,
      v.is_expected_academic_dishonesty,
      false as is_anchor_row,
      null as is_healthy_gradebook,
      v.flag_value,

  from teacher_aggs as t
  inner join
      valid_flags as v
      on t.academic_year = v.academic_year
      and t.region = v.region
      and t.schoolid = v.schoolid
      and t.quarter = v.quarter
      and t.sectionid = v.sectionid
      and t.teacher_number = v.teacher_number
      and t.assignment_category_term = v.assignment_category_term
      and t.teacher_assign_id = v.teacher_assign_id
      and t.audit_category = v.audit_category
      and t.cte_grouping = v.cte_grouping
      and t.audit_flag_name = v.audit_flag_name
  where
      t.code_type = 'Gradebook Category'
      and t.cte_grouping = 'class_category_assignment'

  union all

  -- flag rows: class_category (Gradebook Category, class-category grain)
  select
      t.academic_year,
      t.academic_year_display,
      t.region,
      t.school_level,
      t.region_school_level,
      t.schoolid,
      t.school,
      t.`quarter`,
      t.semester,
      t.quarter_start_date,
      t.quarter_end_date,
      t.is_current_quarter,
      t.assignment_category_name,
      t.assignment_category_code,
      t.assignment_category_term,
      t.expectation,
      t.notes,
      t.section_or_period,
      t.sectionid,
      t.sections_dcid,
      t.section_number,
      t.external_expression,
      t.credit_type,
      t.course_number,
      t.course_name,
      t.exclude_from_gpa,
      t.is_ap_course,
      t.teacher_number,
      t.teacher_name,
      t.teacher_tableau_username,
      t.manager_employee_number,
      t.manager_name,
      t.manager_tableau_username,
      t.school_leader,
      t.school_leader_tableau_username,
      t.teacher_assign_id,
      t.teacher_assign_name,
      t.teacher_assign_due_date,
      t.teacher_assign_score_type,
      t.teacher_assign_max_score,
      t.n_students,
      t.n_late,
      t.n_exempt,
      t.n_missing,
      t.n_null,
      t.n_academic_dishonesty,
      t.n_is_null_missing,
      t.n_is_null_not_missing,
      t.n_expected,
      t.n_expected_scored,
      t.percent_graded_for_assignment,
      t.sum_totalpointvalue_section_quarter_category,
      t.teacher_running_total_assign_by_cat,
      t.teacher_avg_score_for_assign_per_class_section_and_assign_id,
      t.audit_category,
      t.cte_grouping,
      t.code_type,
      t.audit_flag_name,
      t.audit_flag_value,
      v.studentid,
      v.student_number,
      v.student_name,
      v.grade_level,
      v.salesforce_id,
      v.ktc_cohort,
      v.enroll_status,
      v.cohort,
      v.gender,
      v.ethnicity,
      v.advisory,
      v.year_in_school,
      v.year_in_network,
      v.rn_undergrad,
      v.is_out_of_district,
      v.is_retained_year,
      v.is_retained_ever,
      v.lunch_status,
      v.gifted_and_talented,
      v.iep_status,
      v.lep_status,
      v.is_504,
      v.is_counseling_services,
      v.is_student_athlete,
      v.ada,
      v.ada_above_or_at_80,
      v.date_enrolled,
      v.category_quarter_percent_grade,
      v.quarter_course_percent_grade,
      v.quarter_course_grade_points,
      v.quarter_comment_value,
      v.raw_score,
      v.score_entered,
      v.assign_final_score_percent,
      v.is_exempt,
      v.is_expected_late,
      v.is_expected_missing,
      v.is_expected_academic_dishonesty,
      false as is_anchor_row,
      null as is_healthy_gradebook,
      v.flag_value,

  from teacher_aggs as t
  inner join
      valid_flags as v
      on t.academic_year = v.academic_year
      and t.region = v.region
      and t.schoolid = v.schoolid
      and t.quarter = v.quarter
      and t.sectionid = v.sectionid
      and t.teacher_number = v.teacher_number
      and t.assignment_category_term = v.assignment_category_term
      and t.audit_category = v.audit_category
      and t.cte_grouping = v.cte_grouping
      and t.audit_flag_name = v.audit_flag_name
  where
      t.code_type = 'Gradebook Category'
      and t.cte_grouping = 'class_category'
  ```

- [x] **Step 6g.2: Build and verify**

  ```bash
  uv run dbt build \
    --select rpt_tableau__gradebook_audit \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6h: Spot-check and commit Task 3

- [x] **Step 6h.1: Spot-check removed flags**

  Via BigQuery MCP — query each modified model directly (not
  `rpt_tableau__gradebook_audit` until the full chain is valid):

  ```sql
  /* Verify flags are gone from categories_teacher */
  SELECT DISTINCT
  FROM `teamster-332318.dbt_grangel_tableau.int_tableau__gradebook_audit_categories_teacher`
  WHERE qt_teacher_s_total_greater_200 IS NOT NULL
    OR qt_teacher_s_total_less_200 IS NOT NULL
  LIMIT 1
  ```

  Expected: 0 rows for each deprecated flag column.

  > ✅ **Verified:** All deprecated flag columns removed across 6a–6f. Flag
  > removal commits landed across the Task 6 series.

- [x] **Step 6h.2: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): Task 3 — flag removals, model updates, and prerequisites"
  ```

### 6h.5: `rpt_tableau__assignment_checks.sql` — deprecate

This model is being deprecated. Disable it and archive per the standard pattern.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__assignment_checks.sql`

- [ ] **Step 6h.5.1: Disable the model**

  Add `config(enabled=false)` and update the exposure in `tableau.yml` to remove
  the `ref("rpt_tableau__assignment_checks")` entry from `gradebook_audit`.

- [ ] **Step 6h.5.2: Build and verify**

  ```bash
  uv run dbt build \
    --select rpt_tableau__assignment_checks \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6h.6: `rpt_tableau__gradebook_ms_hs_comments.sql` — remove Miami

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_ms_hs_comments.sql`

- [x] **Step 6h.6.1: Review and update**

  > ✅ **No changes needed.** `rpt_tableau__gradebook_ms_hs_comments` reads from
  > `int_tableau__gradebook_audit_flags`, which sources from the teacher
  > scaffold. The teacher scaffold already excludes Miami
  > (`_dbt_source_project != 'kippmiami'` in its WHERE), so no Miami rows reach
  > this model. Zero Miami references confirmed via grep across the model and
  > all upstream models.

- [x] **Step 6h.6.2: Build and verify**

  ```bash
  uv run dbt build \
    --select rpt_tableau__gradebook_ms_hs_comments \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6h.7: `rpt_tableau__gradebook_es_comments.sql` — standalone CTE rewrite

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`

**What changed:** The model was completely rewritten as a standalone CTE-based
model. It no longer depends on the flags pipeline. Key design decisions:

- Source: `base_powerschool__course_enrollments` joined to
  `int_powerschool__terms` for quarter grain (one row per student × course ×
  quarter)
- Scope: `credittype IN ('HR', 'MATH', 'ENG')`, `region != 'Miami'`,
  `school_level = 'ES'`
- Dedup: `not is_dropped_section` +
  `row_number() over (partition by cc_studentid, cc_course_number, term order by cc_dateleft desc) = 1`
  — handles both dropped courses and section-to-section transfers
- `total_days_enrolled_in_quarter`: window sum across all sections for the same
  student/course/quarter, capped at `quarter_length_days` — correctly accounts
  for transfer students when determining `is_partial_quarter`
- `is_partial_quarter = true` when
  `total_days_enrolled_in_quarter / quarter_length_days < 0.25`
- ES rows were also removed from `stg_google_sheets__gradebook_flags` by the
  user — ES is no longer handled by the main flags pipeline for AY 2026-2027+

- [x] **Step 6h.7.1: Rewrite the model** (complete)

- [x] **Step 6h.7.2: Build and verify** (complete — spot-checked: max 1 row per
      student/course/quarter, max 4 quarters per student/course, transfer
      student `is_partial_quarter` correctly `false` when combined enrollment ≥
      25%)

---

### 6h.8: `exposures/tableau.yml` — split gradebook audit from GPA

The `gradebook_and_gpa_dashboard` exposure currently covers both the gradebook
audit and GPA views, which are being split into two separate Tableau reports.

**File:** `src/dbt/kipptaf/models/exposures/tableau.yml`

- [ ] **Step 6h.8.1: Split the exposure**

  Replace `gradebook_and_gpa_dashboard` with two separate exposures:
  1. **`gradebook_audit`** — gradebook audit models only:
     - `rpt_tableau__gradebook_audit`
     - `rpt_tableau__gradebook_es_comments`
     - `rpt_tableau__gradebook_ms_hs_comments`

  2. **`gradebook_gpa`** (or keep existing name) — GPA models only:
     - `rpt_tableau__gradebook_gpa`
     - `rpt_tableau__gradebook_gpa_cumulative`

  Carry over the existing Tableau LSID (`id`) and `cron_schedule` to whichever
  exposure maps to the original workbook. Assign the new workbook's LSID once it
  exists in Tableau.

  > ⚠️ Confirm LSID assignments with the user before editing — the original
  > workbook ID (`5046a976-ed0e-4c77-93fe-78b732cb5548`) must stay on the
  > correct exposure.

---

### 6i: Anchor-row / "in the clear" redesign

Replace the current design in `rpt_tableau__gradebook_audit.sql` — which
generates one row per possible flag slot per section × quarter with
`flag_value = 0` for non-fired flags — with a leaner pattern: one anchor row per
section × quarter plus rows only where flags actually fired. A fully compliant
teacher has only the anchor row. The anchor row provides the classroom
denominator for the school-level summary view.

Also required: school-level summary view in Tableau showing the number or
percentage of classrooms with at least one active flag, with click-through to a
filtered teacher list.

> ⚠️ **Implementation details TBD.** Anchor row structure (sentinel flag name vs
> null, what columns it carries) and the updated Tableau health score formula
> will be designed when this task is reached.

---

## Task 7: Update reference documentation and skill

Once all SQL changes are merged and the model is stable, update the reference
doc to reflect the new state of the pipeline and trim the skill to remove
development-time references that are no longer current.

- [ ] **Step 8.1: Add AY 2026-2027 section to the reference doc**

  File: `docs/reference/gradebook-audit-data-model.md`

  At the top of the file, add an "AY 2026-2027 Model (current)" section with:
  - Updated coverage table (Newark, Camden, Paterson — no Miami)
  - Updated lineage diagram (quarter-grain scaffold, no `term_weeks`, PS-native
    expectations model, no exceptions table)
  - Updated layer summary and key data flows
  - Updated scaffold section (no week columns, new sections CTE structure)

  Rename the existing content to "AY 2025-2026 Model (archived)" and preserve it
  below the new section.

- [ ] **Step 8.2: Update the start-of-year procedure in the reference doc**

  The start-of-year procedure already has the flag row generation query. Verify
  it reflects the current region configuration (Newark, Camden, Paterson) and
  that the deprecated flags list is up to date.

- [ ] **Step 8.3: Trim the gradebook-audit skill**

  File: `.claude/skills/gradebook-audit/SKILL.md`

  Remove the spec and plan doc references from the "Always read first" section.
  Those are development-time documents; after merge they become historical
  artifacts. The skill should only reference the reference doc:

  ```markdown
  - Reference doc:
    [`docs/reference/gradebook-audit-data-model.md`](../../docs/reference/gradebook-audit-data-model.md)
  ```

  The spec (`docs/superpowers/specs/`) and plan (`docs/superpowers/plans/`) stay
  in git as historical context but are not needed for ongoing operations.

- [ ] **Step 8.4: Commit**

  ```bash
  git add -u
  git commit -m "docs: update gradebook audit reference doc for AY 2026-2027; trim skill"
  ```
