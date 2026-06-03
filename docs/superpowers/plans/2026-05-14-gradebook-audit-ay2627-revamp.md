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

| File                                            | Task | Change |
| ----------------------------------------------- | ---- | ------ |
| `int_powerschool__u_expectations[_unpivot].sql` | 2    | Create |
| `int_powerschool__u_expectations[_unpivot].yml` | 2    | Create |

### SQL — modified models

| File                                                   | Task(s)  | Change                              |
| ------------------------------------------------------ | -------- | ----------------------------------- |
| `int_tableau__gradebook_audit_teacher_scaffold.sql`    | 2, 3, 6  | SQL                                 |
| `int_tableau__gradebook_audit_student_scaffold.sql`    | 2, 3     | SQL                                 |
| `int_tableau__gradebook_audit_assignments_teacher.sql` | 3, 6     | SQL                                 |
| `int_tableau__gradebook_audit_assignments_student.sql` | 3        | SQL                                 |
| `int_tableau__gradebook_audit_categories_teacher.sql`  | 3, 4, 6  | SQL                                 |
| `int_tableau__gradebook_audit_flags.sql`               | 3, 6     | SQL                                 |
| `rpt_tableau__gradebook_audit.sql`                     | 3, 6     | SQL                                 |
| `int_extracts__student_enrollments.sql`                | 3        | Add boolean column                  |
| `rpt_tableau__gradebook_gpa.sql`                       | 3        | Add boolean, remove Paterson filter |
| YAML properties for each modified model                | per task | Column additions / removals         |

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

- [ ] **Step 1.0: Paste the pre-generated AY 2026 rows into the sheet**

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

- [ ] **Step 1.1: Roll over Newark rows (ES, MS, HS)**

  Copy all Newark rows where `academic_year = 2025`. Paste as new rows. Set
  `academic_year = 2026`. Delete any rows for these deprecated flags before
  saving:
  - `w_grade_inflation`
  - `assign_s_hs_score_not_conversion_chart_options`
  - `assign_s_ms_score_not_conversion_chart_options`
  - `qt_teacher_s_total_greater_200`
  - `qt_teacher_s_total_less_200`
  - `qt_student_is_ada_80_plus_gpa_less_2`

- [ ] **Step 1.2: Roll over Camden rows (ES, MS, HS)**

  Same process as step 1.1 for Camden. Copy Camden `academic_year = 2025` rows,
  paste, set `academic_year = 2026`, delete the same deprecated flag rows listed
  above.

- [ ] **Step 1.3: Add Paterson MS rows**

  Copy all Newark MS rows for `academic_year = 2026` (just created in step 1.1).
  Paste as new rows. Change `region` to `Paterson`. Paterson MS uses the same
  flags as Newark MS.

- [ ] **Step 1.4: Add Paterson ES rows**

  Paterson ES gets EOQ comments only — same pattern as Camden ES and Newark ES.
  Add one row per applicable quarter (`Q3`, `Q4`) for
  `audit_flag_name = qt_es_comment_missing`, `region = Paterson`,
  `school_level = ES`, `academic_year = 2026`. Match the column values of an
  existing Camden ES or Newark ES row for that flag.

- [ ] **Step 1.5: Do not add Miami rows**

  Miami is being removed. Do not create any `academic_year = 2026` rows for
  Miami.

- [ ] **Step 1.6: Stage the external table**

  ```bash
  uv run dbt run-operation stage_external_sources \
    --args '{"select": "google_sheets.src_google_sheets__gradebook_flags"}' \
    --project-dir src/dbt/kipptaf
  ```

- [ ] **Step 1.7: Rebuild staging and verify**

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

- [ ] **Step 1.8: Commit**

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

- [ ] **Step 2.1: Disable the staging model**

  In
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_exceptions.yml`,
  add at the top of the model config:

  ```yaml
  config:
    enabled: false
  ```

  The SQL file and source entry stay in place. This preserves the model for
  reference pending any operational decisions after July 1st.

- [ ] **Step 2.2: Commit**

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

- [ ] **Step 3.1: Create the INT expectations model**

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

- [ ] **Step 3.1b: Build and verify the INT model**

  ```bash
  uv run dbt build \
    --select int_powerschool__u_expectations[_unpivot] \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 3.2: Create the YAML for the new INT model**

  Create the properties file at
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__u_expectations[_unpivot].yml`.
  Add a model description and a column entry for each output column. Add a
  `dbt_utils.unique_combination_of_columns` test on
  `(region, school_level, academic_year, quarter, assignment_category_code)`. No
  `week_number` — the model is quarter-grain.

> ⚠️ **Blocked on PR #4077.** This task uses the intermediate model created by
> the PS plugin integration (Camden/Paterson U_EXPECTATIONS). PR #4077 must be
> merged and Dagster must have materialized the new model in prod before this
> task can be executed. Details will be added once PR #4077 is complete.

---

## Task 4: SQL — Update base views and tables

### 4a: `base_powerschool__sections` — add `school_abbreviation` and `school_level` (prerequisite)

Must land before the teacher scaffold is built in step 6.1.

**File:** `src/dbt/powerschool/models/sis/base/base_powerschool__sections.sql`

- [ ] **Step 4a.1: Add both columns to the SELECT list**

  Find `sch.name as school_name,` and add immediately after:

  ```sql
  sch.abbreviation as school_abbreviation,
  sch.school_level,
  ```

- [ ] **Step 4a.2: Add columns to the properties YAML**

  File:
  `src/dbt/powerschool/models/sis/base/properties/base_powerschool__sections.yml`

  ```yaml
  - name: school_abbreviation
    description:
      Short school name abbreviation from stg_powerschool__schools, used as the
      display name in Tableau dashboards.
    data_type: string
  - name: school_level
    description: School level (ES, MS, or HS) from stg_powerschool__schools.
    data_type: string
  ```

- [ ] **Step 4a.3: Build and verify**

  ```bash
  uv run dbt build \
    --select base_powerschool__sections \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 4b: `stg_google_sheets__gradebook_flags` — drop `grade_level`

`grade_level` was only used by Miami KG/G1-G8 conduct code flags (now gone).
Drop it using BigQuery `SELECT * EXCEPT`.

**File:**
`src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gradebook_flags.sql`

- [ ] **Step 4b.1: Update the SELECT**

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

- [ ] **Step 4b.2: Remove `grade_level` from the YAML**

  File:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_flags.yml`

  Delete the `grade_level` column entry.

- [ ] **Step 4b.3: Build and verify**

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

- [ ] **Step 4c.1: Add boolean column**

  In the final `select`, after `ada_above_or_at_80` and GPA columns (ST06
  ordering — logicals after plain refs):

  ```sql
  if(
      ada_above_or_at_80 and cumulative_y1_gpa < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_cum_gpa_less_2,
  ```

- [ ] **Step 4c.2: Add column to YAML**

  File:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`

  ```yaml
  - name: is_ada_above_or_at_80_cum_gpa_less_2
    description: >
      True when the student's ADA is at or above 80% and their cumulative
      year-to-date GPA (cumulative_y1_gpa) is below 2.0.
    data_type: boolean
  ```

- [ ] **Step 4c.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_extracts__student_enrollments \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 4d: `int_powerschool__gradebook_assignments_scores` — fix Sumner G5 `school_level` override

This model has the Sumner Elementary G5 → MS override hardcoded to
`cc_academic_year = 2025`. Since the underlying assignment data is multi-year,
this condition is false for AY 2026 and Sumner G5 students silently get
`school_level = 'ES'` instead of `'MS'`. Changing to `>= 2025` applies the
override for all years from 2025 onwards.

**File:**
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`

- [ ] **Step 4d.1: Update the year condition**

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

- [ ] **Step 4d.2: Build and verify**

  ```bash
  uv run dbt build \
    --select int_powerschool__gradebook_assignments_scores \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

## Task 5: SQL — `rpt_tableau__gradebook_gpa` updates

### 5a: `rpt_tableau__gradebook_gpa` — add per-course boolean, remove Paterson filter

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_gpa.sql`

- [ ] **Step 5.1: Add per-course GPA boolean**

  In the final `select`, after `ada_above_or_at_80`:

  ```sql
  if(
      s.ada_above_or_at_80 and s.gpa_y1 < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_gpa_y1_less_2,
  ```

- [ ] **Step 5.2: Remove Paterson exclusion**

  In the `student_roster` CTE WHERE clause, remove
  `and enr.region != 'Paterson'`. The full WHERE becomes:

  ```sql
  where
      enr.rn_year = 1
      and not enr.is_out_of_district
      and enr.enroll_status != -1
  ```

- [ ] **Step 5.3: Add column to YAML**

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

- [ ] **Step 6a.1: Redesign
      `int_tableau__gradebook_audit_teacher_scaffold.sql`**

  This step replaces the entire scaffold with the quarter-grain design. The
  current four-CTE model (`sections`, `term_weeks`, `school_level_mod`, `final`)
  - outer SELECT becomes a single `sections` CTE + a direct two-branch UNION ALL
    SELECT.

  **The new structure:**

  ```sql
  with
      sections as (
          select
              s._dbt_source_relation,
              s.terms_yearid,
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
              s.is_ap_course,
              s.teachernumber as teacher_number,
              s.teacher_lastfirst as teacher_name,
              s.school_abbreviation as school,

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
              s.school_level,

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
      s.is_ap_course,
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

  from sections as s

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
      s.is_ap_course,
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

  from sections as s
  inner join
      {{ ref("int_powerschool__u_expectations[_unpivot]") }} as ge
      on s.region = ge.region
      and s.school_level = ge.school_level
      and s.academic_year = ge.academic_year
      and s.quarter = ge.quarter
  ```

  Key differences from the old model:
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
  - `school_level` and `school_abbreviation` from `base_powerschool__sections`
    (requires step 4a to land first)

  _(Replace `[_unpivot]` with the actual model name decided in step 3.1.)_

- [ ] **Step 6a.2: Build and verify the teacher scaffold**

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

  Expected: Newark with both scaffold variants, Q1–Q4. Camden/Paterson have
  `teacher_scaffold` rows only (no PS expectations data yet).

### 6b: `int_tableau__gradebook_audit_student_scaffold.sql` — quarter-grain redesign

- [ ] **Step 6b.1: Redesign
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

- [ ] **Step 6b.2: Build and verify the student scaffold**

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

- [ ] **Step 6b.4: Commit**

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
- Block comments `/* */` replacing `--` per style convention

- [ ] **Step 6c.1: Rewrite the model**

  **File:**
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_student.sql`

  ```sql
  select
      /* student enrollment fields */
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

      /* course enrollment fields */
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

      /* scaffold fields */
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

      /* grade fields */
      ce.quarter_course_percent_grade,
      ce.quarter_course_grade_points,
      ce.quarter_comment_value,
      ce.category_quarter_percent_grade,

      /* assignment fields */
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

      /* flags */
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

- [ ] **Step 6c.2: Update YAML**

  Remove `assign_s_ms_score_not_conversion_chart_options` and
  `assign_s_hs_score_not_conversion_chart_options` from
  `intermediate/properties/int_tableau__gradebook_audit_assignments_student.yml`.

- [ ] **Step 6c.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_assignments_student \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6d: `int_tableau__gradebook_audit_assignments_teacher`

Remove one Miami dead-code flag. Also update the assignment date window — TBD
during model review.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_teacher.sql`

- [ ] **Step 6d.1: Remove `s_max_score_greater_100` from the final SELECT**

  Delete:

  ```sql
  if(
      sec.region = 'Miami'
      and sec.assignment_category_code = 'S'
      and a.totalpointvalue > 100,
      true,
      false
  ) as s_max_score_greater_100,
  ```

- [ ] **Step 6d.2: Update assignment date window (TBD)**

  Change the join condition from week grain to quarter grain. Details will be
  added when `int_tableau__gradebook_audit_assignments_teacher` is reviewed in
  the CTE-by-CTE session.

- [ ] **Step 6d.3: Update YAML**

  Remove `s_max_score_greater_100` from
  `intermediate/properties/int_tableau__gradebook_audit_assignments_teacher.yml`.

- [ ] **Step 6d.4: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_assignments_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6e: `int_tableau__gradebook_audit_categories_teacher`

Remove Summative 200 flags (both Camden/Newark 200-pt and Miami 100-pt variants)
from the final SELECT. The 7-day grace period change (Task 4) and exceptions
removal (Task 6) happen later.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

- [ ] **Step 6e.1: Remove four S-total flag expressions from the final SELECT**

  Delete:

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

- [ ] **Step 6e.2: Update YAML**

  Remove all four column entries from
  `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`.

- [ ] **Step 6e.3: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_categories_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6f: `int_tableau__gradebook_audit_flags.sql` — consolidated UNPIVOT updates and CTE deletions

All UNPIVOT list changes and CTE deletions in one step.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags.sql`

- [ ] **Step 6f.1: Update `student_unpivot` UNPIVOT list**

  Delete from the UNPIVOT list:

  ```sql
  assign_s_ms_score_not_conversion_chart_options,
  assign_s_hs_score_not_conversion_chart_options
  ```

- [ ] **Step 6f.2: Update `teacher_unpivot_cca` UNPIVOT list**

  Delete:

  ```sql
  s_max_score_greater_100
  ```

- [ ] **Step 6f.3: Update `teacher_unpivot_cc` UNPIVOT list**

  Delete:

  ```sql
  qt_teacher_s_total_greater_200,
  qt_teacher_s_total_less_200,
  qt_teacher_s_total_greater_100,
  qt_teacher_s_total_less_100,
  ```

- [ ] **Step 6f.4: Delete the `student_course_category` CTE**

  Delete the entire CTE — from the `/* w_grade_inflation... */` comment through
  `from student_course_category`.

- [ ] **Step 6f.5: Delete the `eoq_items_conduct_code` CTE**

  Delete the entire `eoq_items_conduct_code` CTE.

- [ ] **Step 6f.6: Update `eoq_items` UNPIVOT list**

  Delete from the `eoq_items` UNPIVOT:

  ```sql
  qt_comment_missing,
  qt_g1_g8_conduct_code_missing,
  qt_g1_g8_conduct_code_incorrect,
  qt_student_is_ada_80_plus_gpa_less_2
  ```

  Remaining in `eoq_items`: `qt_es_comment_missing`,
  `qt_grade_70_comment_missing`, `qt_percent_grade_greater_100`.

- [ ] **Step 6f.7: Update YAML**

  Remove all deleted flag column entries from
  `intermediate/properties/int_tableau__gradebook_audit_flags.yml`.

- [ ] **Step 6f.8: Build and verify**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_flags \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6g: `rpt_tableau__gradebook_audit.sql` — remove empty UNION branch

**File:**
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`

- [ ] **Step 6g.1: Remove the `student_course_category` UNION branch**

  Delete the UNION ALL block with
  `where t.cte_grouping = 'student_course_category'` including its leading
  `union all` separator. The report shrinks from 5 to 4 UNION branches.

- [ ] **Step 6g.2: Build and verify**

  ```bash
  uv run dbt build \
    --select rpt_tableau__gradebook_audit \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

---

### 6h: Spot-check and commit Task 3

- [ ] **Step 6h.1: Spot-check removed flags**

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

- [ ] **Step 6h.2: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): Task 3 — flag removals, model updates, and prerequisites"
  ```

---

---

## Task 7: SQL — 7-day grace period for percent-graded flags

`w/h/f/s_percent_graded_min_not_met` should only fire for assignments that have
been due for at least 7 days. Currently the percent-graded calculation includes
all assignments in the week window regardless of how recently they were due.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

- [ ] **Step 7.1: Add grace-period filter to the two window sums**

  In the `assignments` CTE, replace:

  ```sql
  sum(asg.n_expected) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.assignment_category_code
  ) as total_expected_section_quarter_category,

  sum(asg.n_expected_scored) over (
      partition by
          sec._dbt_source_relation,
          sec.sectionid,
          sec.quarter,
          sec.assignment_category_code
  ) as total_expected_scored_section_quarter_category,
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
          sec.assignment_category_code
  ) as total_expected_section_quarter_category,

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
          sec.assignment_category_code
  ) as total_expected_scored_section_quarter_category,
  ```

  Note: column names updated from `*_week_category` to `*_quarter_category` — no
  `week_number_quarter` in the partition at quarter grain.

- [ ] **Step 7.2: Build `categories_teacher` only**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_categories_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 7.3: Spot-check `categories_teacher` directly**

  Query the model directly — do not use `rpt_tableau__gradebook_audit`
  (downstream chain not yet valid mid-refactor). Confirm the grace-period flag
  columns exist and the percent-graded values look reasonable:

  ```sql
  SELECT
    region,
    school,
    teacher_name,
    assignment_category_code,
    quarter,
    total_expected_section_quarter_category,
    total_expected_scored_section_quarter_category,
    percent_graded_for_quarter_class,
    w_percent_graded_min_not_met,
  FROM `teamster-332318.dbt_grangel_tableau.int_tableau__gradebook_audit_categories_teacher`
  WHERE academic_year = 2026
    AND w_percent_graded_min_not_met
  LIMIT 20
  ```

- [ ] **Step 7.4: Commit**

  ```bash
  git commit -m "feat(dbt): add 7-day grace period for percent-graded flags"
  ```

---

## Task 8: Update reference documentation and skill

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

---

## Task 9: Anchor-row / "in the clear" redesign

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
