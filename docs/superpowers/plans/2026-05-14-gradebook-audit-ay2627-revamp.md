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
integration) landing. Task 7 (anchor-row redesign) is a separate future effort.

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

| File                             | Task | Change                                              |
| -------------------------------- | ---- | --------------------------------------------------- |
| `base_powerschool__sections.sql` | 3    | Add `school_abbreviation` and `school_level` fields |

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

- [ ] **Step 1.8: Build full audit pipeline and spot-check**

  Task 1 has no SQL changes — the old week-grain pipeline is intact. Safe to
  build the full downstream chain here to verify the sheet config is correct:

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_teacher_scaffold+ \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

  Then spot-check:

  ```sql
  SELECT DISTINCT region, school_level, audit_flag_name
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE academic_year = 2026
  ORDER BY 1, 2, 3
  ```

  Check: no Miami rows, none of the deprecated flags listed in step 1.1 appear,
  Paterson ES and MS present.

- [ ] **Step 1.9: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): gradebook flags rollover to AY 2026-2027"
  ```

---

## Task 2: SQL — Create PS-native expectations model and update scaffolds

`stg_google_sheets__gradebook_expectations_assignments` is being deprecated and
replaced by a PS-native intermediate model sourced from
`stg_powerschool__u_expectations` (the U_EXPECTATIONS PowerSchool plugin). This
task creates that model for Newark (the only region with PS plugin data today)
and updates both scaffolds to join it instead of the Google Sheet.

**Newark only for now.** Camden is blocked on PR #4077 (Bini's integration work)
landing in prod. Paterson is blocked on PS instance access. Until each region's
PS data is available, the INNER JOIN in the teacher scaffold will find no
matching rows for that region — category-level audit rows (assignment count
flags, percent-graded flags) will be silent for Camden and Paterson until their
data lands. EOQ and student-level flags in Task 1 are unaffected.

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

- [ ] **Step 2.1: Create the INT expectations model**

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

- [ ] **Step 2.1b: Build and verify the INT model**

  ```bash
  uv run dbt build \
    --select int_powerschool__u_expectations[_unpivot] \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 2.2: Create the YAML for the new INT model**

  Create the properties file at
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__u_expectations[_unpivot].yml`.
  Add a model description and a column entry for each output column. Add a
  `dbt_utils.unique_combination_of_columns` test on
  `(region, school_level, academic_year, quarter, assignment_category_code)`. No
  `week_number` — the model is quarter-grain.

- [ ] **Step 2.3: Redesign `int_tableau__gradebook_audit_teacher_scaffold.sql`**

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
              initcap(
                  regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')
              ) as region,
              coalesce(
                  if(
                      s.school_name = 'KIPP Sumner Elementary'
                      and s.sections_grade_level = 5,
                      'MS',
                      null
                  ),
                  s.school_level
              ) as school_level,
              concat(
                  initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')),
                  coalesce(
                      if(
                          s.school_name = 'KIPP Sumner Elementary'
                          and s.sections_grade_level = 5,
                          'MS',
                          null
                      ),
                      s.school_level
                  )
              ) as region_school_level,
              cast(s.terms_academic_year as string)
              || '-'
              || right(cast(s.terms_academic_year + 1 as string), 2)
                  as academic_year_display,
              if(
                  s.school_level = 'HS',
                  s.sections_external_expression,
                  s.sections_section_number
              ) as section_or_period,
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

  select
      s.*,
      null as assignment_category_code,
      null as assignment_category_name,
      null as assignment_category_term,
      null as expectation,
      null as notes,
      'teacher_scaffold' as scaffold_name,
  from sections as s

  union all

  select
      s.*,
      ge.assignment_category_code,
      ge.assignment_category_name,
      ge.assignment_category_term,
      ge.expectation,
      ge.notes,
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
  - No `week_number` in the join — quarter grain only
  - No `final` CTE — UNION ALL is the SELECT
  - No `is_quarter_end_date_range`, `quarter_end_date_insession`,
    `is_current_week`
  - No week columns
  - Manager columns added
  - `region` derived inline from `_dbt_source_relation`
  - `school_level` and `school_abbreviation` from `base_powerschool__sections`
    (requires step 3h to land first)

  _(Replace `[_unpivot]` with the actual model name decided in step 2.1.)_

- [ ] **Step 2.3b: Build and verify the teacher scaffold**

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

- [ ] **Step 2.4: Update `int_tableau__gradebook_audit_student_scaffold.sql`**

  In the `student_category_scaffold` branch, change the INNER JOIN from
  `stg_google_sheets__gradebook_expectations_assignments` to the new INT model.
  Join key: `region + school_level + academic_year + quarter` — no
  `week_number`.

- [ ] **Step 2.4b: Build and verify the student scaffold**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_student_scaffold \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 2.5: Disable the deprecated staging model**

  Nothing references `stg_google_sheets__gradebook_expectations_assignments`
  after steps 2.3–2.4. Disable it rather than deleting, in case operational
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

- [ ] **Step 2.7: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): replace Google Sheet expectations with PS-native INT model (Newark)"
  ```

---

## Task 3: SQL — flag removals and Miami dead code cleanup

Removes deprecated flags and all Miami-only dead-code SQL branches. The sheet
already deactivated these flags in Task 1 — this task removes the dead SQL.
After this task, the `student_course_category` and `eoq_items_conduct_code` CTEs
in `flags.sql` become empty and are deleted; `rpt.sql` shrinks from 5 to 4 UNION
branches.

**Flags being removed:**

| Flag                                             | Reason                                                                    |
| ------------------------------------------------ | ------------------------------------------------------------------------- |
| `w_grade_inflation`                              | FYI flag — excluded from health score, not actionable                     |
| `assign_s_hs_score_not_conversion_chart_options` | FYI flag                                                                  |
| `assign_s_ms_score_not_conversion_chart_options` | FYI flag                                                                  |
| `qt_teacher_s_total_greater_200`                 | Makeup work policy causes false positives                                 |
| `qt_teacher_s_total_less_200`                    | Makeup work policy causes false positives                                 |
| `qt_student_is_ada_80_plus_gpa_less_2`           | Moving to `int_extracts__student_enrollments` for use in other dashboards |
| `qt_teacher_s_total_greater_100`                 | Miami-only dead code                                                      |
| `qt_teacher_s_total_less_100`                    | Miami-only dead code                                                      |
| `s_max_score_greater_100`                        | Miami-only dead code                                                      |
| `qt_comment_missing`                             | Miami-only dead code                                                      |
| `qt_g1_g8_conduct_code_missing`                  | Miami-only dead code                                                      |
| `qt_g1_g8_conduct_code_incorrect`                | Miami-only dead code                                                      |
| `qt_kg_conduct_code_missing`                     | Miami-only dead code                                                      |
| `qt_kg_conduct_code_incorrect`                   | Miami-only dead code                                                      |
| `qt_kg_conduct_code_not_hr`                      | Miami-only dead code                                                      |
| `qt_effort_grade_missing`                        | Miami-only dead code                                                      |
| `qt_formative_grade_missing`                     | Miami-only dead code                                                      |
| `qt_summative_grade_missing`                     | Miami-only dead code                                                      |

### 3a: Remove FYI flag `w_grade_inflation`

- [ ] **Step 3a.1: Remove from `student_scaffold.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_student_scaffold.sql`

  In the **`student_scaffold` branch** (first UNION branch), delete:

  ```sql
  null as w_grade_inflation,
  ```

  In the **`student_category_scaffold` branch** (second UNION branch), delete:

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

- [ ] **Step 3a.2: Remove from `student_course_category` UNPIVOT in
      `flags.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags.sql`

  In the `student_course_category` CTE UNPIVOT list, delete
  `w_grade_inflation,`.

- [ ] **Step 3a.3: Update YAMLs**

  Remove `w_grade_inflation` column entry from:
  - `intermediate/properties/int_tableau__gradebook_audit_student_scaffold.yml`
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`

### 3b: Remove FYI flags `assign_s_hs/ms_score_not_conversion_chart_options`

- [ ] **Step 3b.1: Remove from `assignments_student.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_student.sql`

  Delete these two `if(...)` expressions from the final `select`:

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

- [ ] **Step 3b.2: Remove from `student_unpivot` UNPIVOT in `flags.sql`**

  Delete from the `student_unpivot` CTE UNPIVOT list:

  ```sql
  assign_s_ms_score_not_conversion_chart_options,
  assign_s_hs_score_not_conversion_chart_options
  ```

- [ ] **Step 3b.3: Update YAMLs**

  Remove both column entries from:
  - `intermediate/properties/int_tableau__gradebook_audit_assignments_student.yml`
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`

### 3c: Remove Summative 200 flags

These flags check whether total summative point values for the quarter are above
or below 200. The makeup work policy means teachers legitimately exceed or fall
short of the 200-point target without it indicating a compliance problem — the
flags produce false positives and are being removed.

- [ ] **Step 3c.1: Remove `qt_teacher_s_total_greater/less_200` from
      `categories_teacher.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

  Delete from the final `select`:

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

- [ ] **Step 3c.2: Remove from `teacher_unpivot_cc` UNPIVOT in `flags.sql`**

  Delete:

  ```sql
  qt_teacher_s_total_greater_200,
  qt_teacher_s_total_less_200,
  ```

- [ ] **Step 3c.3: Update YAMLs**

  Remove both column entries from:
  - `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`

### 3d: Migrate `qt_student_is_ada_80_plus_gpa_less_2` out of the gradebook audit

This flag is being split into two new booleans and removed from the gradebook
audit:

- A **cumulative GPA** version added to `int_extracts__student_enrollments`
  (student-level, for use in any dashboard)
- A **per-course year-to-date GPA** version added to
  `rpt_tableau__gradebook_gpa`

> ⚠️ **Open question for T&L (see issue #3908 comment):** current logic uses
> `< 2.0` (strictly less than). Confirm whether threshold should be `<= 2.0`.
> Use `< 2.0` until confirmed otherwise.

- [ ] **Step 3d.1: Remove from `student_scaffold.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_student_scaffold.sql`

  In the **`student_scaffold` branch**, delete:

  ```sql
  if(
      s.school_level_alt != 'ES'
      and s.ada_above_or_at_80
      and qg.quarter_course_grade_points < 2.0,
      true,
      false
  ) as qt_student_is_ada_80_plus_gpa_less_2,
  ```

  In the **`student_category_scaffold` branch**, delete:

  ```sql
  null as qt_student_is_ada_80_plus_gpa_less_2,
  ```

- [ ] **Step 3d.2: Remove from `eoq_items` UNPIVOT in `flags.sql`**

  Delete from the `eoq_items` CTE UNPIVOT list:

  ```sql
  qt_student_is_ada_80_plus_gpa_less_2
  ```

- [ ] **Step 3d.3: Update gradebook audit YAMLs**

  Remove `qt_student_is_ada_80_plus_gpa_less_2` from:
  - `intermediate/properties/int_tableau__gradebook_audit_student_scaffold.yml`
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`

- [ ] **Step 3d.4: Add cumulative GPA boolean to
      `int_extracts__student_enrollments`**

  File:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments.sql`

  Add this column to the final `select` list (after the existing
  `ada_above_or_at_80` and GPA columns — follow ST06 column ordering: plain refs
  first, then logicals):

  ```sql
  if(
      ada_above_or_at_80 and cumulative_y1_gpa < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_cum_gpa_less_2,
  ```

  Then add the column to the properties YAML at
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`:

  ```yaml
  - name: is_ada_above_or_at_80_cum_gpa_less_2
    description: >
      True when the student's ADA is at or above 80% and their cumulative
      year-to-date GPA (cumulative_y1_gpa) is below 2.0.
    data_type: boolean
  ```

- [ ] **Step 3d.5: Build and verify `int_extracts__student_enrollments`**

  ```bash
  uv run dbt build \
    --select int_extracts__student_enrollments \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 3d.6: Add per-course GPA boolean to `rpt_tableau__gradebook_gpa`**

  File: `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_gpa.sql`

  Add this column to the final `select` list (after the existing
  `ada_above_or_at_80` column — follow ST06 ordering):

  ```sql
  if(
      s.ada_above_or_at_80 and s.gpa_y1 < 2.0,
      true,
      false
  ) as is_ada_above_or_at_80_gpa_y1_less_2,
  ```

  Then add the column to the properties YAML at
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_gpa.yml`:

  ```yaml
  - name: is_ada_above_or_at_80_gpa_y1_less_2
    description: >
      True when the student's ADA is at or above 80% and their year-to-date
      course GPA (gpa_y1) is below 2.0. Per-course grain.
    data_type: boolean
  ```

- [ ] **Step 3d.7: Remove the Paterson exclusion from
      `rpt_tableau__gradebook_gpa`**

  In the `student_roster` CTE WHERE clause (line 128–133), remove:

  ```sql
  and enr.region != 'Paterson'
  ```

  The full WHERE becomes:

  ```sql
  where
      enr.rn_year = 1
      and not enr.is_out_of_district
      and enr.enroll_status != -1
  ```

- [ ] **Step 3d.8: Build and verify `rpt_tableau__gradebook_gpa`**

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

### 3e: Remove Miami dead-code flags from `categories_teacher.sql` and

`assignments_teacher.sql`

- [ ] **Step 3e.1: Remove `qt_teacher_s_total_greater/less_100` from
      `categories_teacher.sql`**

  Delete from the final `select`:

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

- [ ] **Step 3e.2: Remove `s_max_score_greater_100` from
      `assignments_teacher.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_teacher.sql`

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

- [ ] **Step 3e.3: Remove from UNPIVOT lists in `flags.sql`**

  From `teacher_unpivot_cc` UNPIVOT, delete:

  ```sql
  qt_teacher_s_total_greater_100,
  qt_teacher_s_total_less_100,
  ```

  From `teacher_unpivot_cca` UNPIVOT, delete:

  ```sql
  s_max_score_greater_100
  ```

- [ ] **Step 3e.4: Update YAMLs**
  - `intermediate/properties/int_tableau__gradebook_audit_categories_teacher.yml`:
    delete `qt_teacher_s_total_greater_100` and `qt_teacher_s_total_less_100`.
  - `intermediate/properties/int_tableau__gradebook_audit_assignments_teacher.yml`:
    delete `s_max_score_greater_100`.
  - `intermediate/properties/int_tableau__gradebook_audit_flags.yml`: delete all
    three.

### 3f: Remove Miami dead-code flags from `student_scaffold.sql`

- [ ] **Step 3f.1: Remove Miami flags from `student_scaffold` branch
      (branch 1)**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_student_scaffold.sql`

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

  Also delete these null placeholders from branch 1:

  ```sql
  null as qt_effort_grade_missing,
  null as qt_formative_grade_missing,
  null as qt_summative_grade_missing,
  ```

- [ ] **Step 3f.2: Remove Miami null placeholders and flags from
      `student_category_scaffold` branch (branch 2)**

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

- [ ] **Step 3f.3: Update student_scaffold YAML**

  Delete column entries for: `qt_comment_missing`,
  `qt_g1_g8_conduct_code_missing`, `qt_g1_g8_conduct_code_incorrect`,
  `qt_kg_conduct_code_missing`, `qt_kg_conduct_code_incorrect`,
  `qt_kg_conduct_code_not_hr`, `qt_effort_grade_missing`,
  `qt_formative_grade_missing`, `qt_summative_grade_missing`.

### 3g: Remove empty CTEs from `flags.sql` and their UNION branches from

`rpt.sql`

After steps 3a–3f, two CTEs have no flags left:

- `student_course_category` (had: `w_grade_inflation`,
  `qt_effort_grade_missing`, `qt_formative_grade_missing`,
  `qt_summative_grade_missing`)
- `eoq_items_conduct_code` (had: `qt_kg_conduct_code_missing`,
  `qt_kg_conduct_code_incorrect`, `qt_kg_conduct_code_not_hr`,
  `qt_g1_g8_conduct_code_missing`, `qt_g1_g8_conduct_code_incorrect`)

And `eoq_items` loses 4 of its 7 flags, keeping only: `qt_es_comment_missing`,
`qt_grade_70_comment_missing`, `qt_percent_grade_greater_100`.

- [ ] **Step 3g.1: Remove `student_course_category` CTE from `flags.sql`**

  Delete the entire `student_course_category` CTE — from the
  `/* w_grade_inflation... */` comment through `from student_course_category`.

- [ ] **Step 3g.2: Remove `eoq_items_conduct_code` CTE from `flags.sql`**

  Delete the entire `eoq_items_conduct_code` CTE.

- [ ] **Step 3g.3: Remove departed flags from `eoq_items` UNPIVOT**

  Delete from the `eoq_items` CTE UNPIVOT list:

  ```sql
  qt_comment_missing,
  qt_g1_g8_conduct_code_missing,
  qt_g1_g8_conduct_code_incorrect,
  qt_student_is_ada_80_plus_gpa_less_2
  ```

- [ ] **Step 3g.4: Remove `student_course_category` UNION branch from
      `rpt.sql`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`

  Delete the UNION ALL block with
  `where t.cte_grouping = 'student_course_category'` including its leading
  `union all` separator. The report shrinks from 5 to 4 UNION branches.

### 3h: Add `school_abbreviation` and `school_level` to `base_powerschool__sections`

`base_powerschool__sections` already joins `stg_powerschool__schools` and
selects `sch.name as school_name`. Adding `school_abbreviation` (short name for
Tableau dashboard real estate) and `school_level` (ES/MS/HS, needed for the
teacher scaffold quarter-grain refactor that eliminates the `term_weeks` CTE).

`region` does NOT need to be added here — it is derived inline from
`_dbt_source_relation` using
`initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))`, the same pattern
used by `int_powerschool__calendar_week`.

**File:** `src/dbt/powerschool/models/sis/base/base_powerschool__sections.sql`

- [ ] **Step 3h.1: Add both columns to the SELECT list**

  In `base_powerschool__sections.sql`, find the line:

  ```sql
  sch.name as school_name,
  ```

  Add immediately after it:

  ```sql
  sch.abbreviation as school_abbreviation,
  sch.school_level,
  ```

- [ ] **Step 3h.2: Add the columns to the properties YAML**

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

- [ ] **Step 3h.3: Build and verify**

  ```bash
  uv run dbt build \
    --select base_powerschool__sections \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

### 3i: Simplify the Miami EOQ window in `teacher_scaffold.sql`

- [ ] **Step 3h.1: Remove the Miami clause from `is_quarter_end_date_range`**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql`

  In the `school_level_mod` CTE, replace the entire CASE expression with:

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

### 3j: Drop `grade_level` from `stg_google_sheets__gradebook_flags`

`grade_level` was only used in the `eoq_items_conduct_code` CTE (now deleted in
step 3g) to distinguish Miami KG from G1-G8 conduct code flags. With Miami
removed and that CTE gone, the column is permanently unused. Drop it from the
staging model using BigQuery's `SELECT * EXCEPT` syntax.

- [ ] **Step 3j.1: Update `stg_google_sheets__gradebook_flags.sql`**

  File:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__gradebook_flags.sql`

  Change:

  ```sql
  select
      *,

      case
          ...
      end as alt_code,

  from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
  ```

  to:

  ```sql
  select
      * except (grade_level),

      case
          ...
      end as alt_code,

  from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
  ```

- [ ] **Step 3j.2: Remove `grade_level` from the staging model YAML**

  File:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_flags.yml`

  Delete the `grade_level` column entry.

### 3k: Add manager columns to `teacher_scaffold.sql` — `sections` CTE

New requirement: surface the teacher's direct manager (number, name, Tableau
username) on every scaffold row. All three columns are already on
`int_people__staff_roster` via the existing `r` alias — no additional join
needed.

- [ ] **Step 3k.1: Add manager columns to the `sections` CTE SELECT list**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql`

  In the `sections` CTE, add these three columns after
  `r.sam_account_name as teacher_tableau_username`:

  ```sql
  r.reports_to_employee_number as manager_employee_number,
  r.reports_to_formatted_name as manager_name,
  r.reports_to_sam_account_name as manager_tableau_username,
  ```

- [ ] **Step 3k.2: Add the columns to the `sections` CTE YAML**

  File:
  `intermediate/properties/int_tableau__gradebook_audit_teacher_scaffold.yml`

  Add three column entries after `teacher_tableau_username`:

  ```yaml
  - name: manager_employee_number
    description: ADP employee number of the teacher's direct manager.
    data_type: string
  - name: manager_name
    description: >
      Full name (Last, First) of the teacher's direct manager, from
      int_people__staff_roster.reports_to_formatted_name.
    data_type: string
  - name: manager_tableau_username
    description:
      SAM account name of the teacher's direct manager, used as their Tableau
      username.
    data_type: string
  ```

  These columns pass through to every downstream model that selects `sec.*` from
  the scaffold. Verify the downstream YAML contracts don't need updating
  (intermediate models don't enforce contracts, but
  `rpt_tableau__gradebook_audit` does — add the columns there too if the
  contract requires it).

### 3l: Build, verify, and commit Task 3

- [ ] **Step 3l.1: Run dbt build — Task 3 models only**

  The scaffolds are now quarter-grain but the assignment models still reference
  week columns — do not cascade downstream. Build only the models modified in
  Task 3:

  ```bash
  uv run dbt build \
    --select \
      base_powerschool__sections \
      stg_google_sheets__gradebook_flags \
      int_tableau__gradebook_audit_teacher_scaffold \
      int_tableau__gradebook_audit_student_scaffold \
      int_tableau__gradebook_audit_assignments_student \
      int_tableau__gradebook_audit_assignments_teacher \
      int_tableau__gradebook_audit_categories_teacher \
      int_extracts__student_enrollments \
      rpt_tableau__gradebook_gpa \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

  If a contract error fires (`column not found`), find the corresponding YAML
  and remove the deleted column.

- [ ] **Step 3l.2: Spot-check removed flags are absent and manager columns
      present**

  Via BigQuery MCP:

  ```sql
  SELECT DISTINCT audit_flag_name
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE academic_year = 2026
  ORDER BY 1
  ```

  Expected absent: all 18 flags listed in the Task 3 flag table above.

  ```sql
  SELECT manager_employee_number, manager_name, manager_tableau_username
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE academic_year = 2026
    AND manager_name IS NOT NULL
  LIMIT 5
  ```

  Expected: manager columns populated for sections where the teacher has a
  manager in the staff roster.

- [ ] **Step 3l.3: Commit**

  ```bash
  git add -u
  git commit -m "feat(dbt): remove deprecated flags and Miami dead code; add manager columns — gradebook audit AY 2026-2027"
  ```

---

## Task 4: SQL — 7-day grace period for percent-graded flags

`w/h/f/s_percent_graded_min_not_met` should only fire for assignments that have
been due for at least 7 days. Currently the percent-graded calculation includes
all assignments in the week window regardless of how recently they were due.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

- [ ] **Step 4.1: Add grace-period filter to the two window sums**

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

- [ ] **Step 4.2: Build `categories_teacher` only**

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_categories_teacher \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

- [ ] **Step 4.3: Spot-check `categories_teacher` directly**

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

- [ ] **Step 4.4: Commit**

  ```bash
  git commit -m "feat(dbt): add 7-day grace period for percent-graded flags"
  ```

---

## Task 5: SQL — QTD cumulative assignment count

> ⚠️ **Blocked on PR #4077.** This task uses the intermediate model created by
> the PS plugin integration (Camden/Paterson U_EXPECTATIONS). PR #4077 must be
> merged and Dagster must have materialized the new model in prod before this
> task can be executed. Details will be added once PR #4077 is complete.

---

## Task 6: SQL — Remove the exceptions mechanism entirely

T&L has decided to eliminate the suppression table. Remove
`stg_google_sheets__gradebook_exceptions` and all 15+ LEFT JOINs across five
intermediate models.

### 6a: `int_tableau__gradebook_audit_teacher_scaffold.sql`

- [ ] **Step 6a.1: Remove exception joins from the `sections` CTE**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql`

  Delete both LEFT JOINs (`e1`, `e2`) and their two conditions from the WHERE
  clause:

  ```sql
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

  -- also delete from WHERE:
  and e1.include_row is null
  and e2.include_row is null
  ```

- [ ] **Step 6a.2: Remove exception joins from the `teacher_category_scaffold`
      branch of `final`**

  Delete all three LEFT JOINs (`e1`, `e2`, `e3`) and:

  ```sql
  where
      e1.include_row is null and e2.include_row is null and e3.include_row is null
  ```

- [ ] **Step 6a.3: Remove exception joins from the outer `select`**

  Delete the two LEFT JOINs at the end of the file and:

  ```sql
  where e1.include_row is null and e2.include_row is null
  ```

### 6b: `int_tableau__gradebook_audit_assignments_teacher.sql`

- [ ] **Step 6b.1: Remove exception join and unwrap conditional columns**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_assignments_teacher.sql`

  Delete the LEFT JOIN to `stg_google_sheets__gradebook_exceptions`. Replace
  every `if(e.include_row is null, asg.<col>, null) as <col>` with the plain
  column:

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

### 6c: `int_tableau__gradebook_audit_categories_teacher.sql`

- [ ] **Step 6c.1: Remove exception join from `assignment_score_rollup` CTE**

  File:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_categories_teacher.sql`

  Delete the LEFT JOIN (`e1`) and the `where e1.include_row is null` condition.

- [ ] **Step 6c.2: Remove the final-level exception join**

  Delete the LEFT JOIN at the bottom of the file and
  `where e.include_row is null`.

### 6d: `int_tableau__gradebook_audit_flags.sql`

- [ ] **Step 6d.1: Remove three exception joins from `student_unpivot` CTE**

  Delete LEFT JOINs `e1`, `e2`, `e3` and remove the entire WHERE clause. The
  UNPIVOT + INNER JOIN to `stg_google_sheets__gradebook_flags` is the correct
  filter; no WHERE is needed.

- [ ] **Step 6d.2: Remove two exception joins from `teacher_unpivot_cca` CTE**

  Delete `e1` and `e2` LEFT JOINs and the WHERE clause.

- [ ] **Step 6d.3: Remove one exception join from `teacher_unpivot_cc` CTE**

  Delete the `e` LEFT JOIN and the WHERE clause.

- [ ] **Step 6d.4: Remove one exception join from `eoq_items` CTE**

  Delete the `e1` LEFT JOIN and the WHERE clause.

### 6e: Disable the exceptions staging model

- [ ] **Step 6e.1: Disable the staging model**

  In
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__gradebook_exceptions.yml`,
  add at the top of the model config:

  ```yaml
  config:
    enabled: false
  ```

  The SQL file and source entry stay in place. This preserves the model for
  reference pending any operational decisions after July 1st.

### 6f: Build, verify, and commit Task 6

- [ ] **Step 6f.1: Run dbt build — full downstream chain**

  Task 6 is the last structural change. By this point all models in the lineage
  should be updated (including the assignment models' quarter-grain date window
  changes — see plan gap note below). If all prior tasks are complete, the full
  chain is now valid:

  ```bash
  uv run dbt build \
    --select int_tableau__gradebook_audit_teacher_scaffold+ \
    --project-dir src/dbt/kipptaf \
    --defer \
    --state src/dbt/kipptaf/target/prod
  ```

  > ⚠️ **Plan gap:** `int_tableau__gradebook_audit_assignments_teacher`,
  > `int_tableau__gradebook_audit_assignments_student`, and
  > `int_tableau__gradebook_audit_categories_teacher` still join on
  > `week_start_monday / week_end_sunday` from the scaffold. These joins must be
  > updated to `quarter_start_date / quarter_end_date` before the full chain
  > will build. Steps for those changes will be added when those models are
  > reviewed.

  Then confirm no remaining references:

  ```bash
  grep -rn "gradebook_exceptions" src/dbt/kipptaf/models/ --include="*.sql"
  ```

  Expected: zero results.

- [ ] **Step 6f.2: Spot-check row counts**

  Via BigQuery MCP:

  ```sql
  SELECT
    region,
    school_level,
    audit_flag_name,
    count(*) as n_rows,
  FROM `teamster-332318.dbt_grangel_tableau.rpt_tableau__gradebook_audit`
  WHERE flag_value = 1
    AND academic_year = 2026
  GROUP BY 1, 2, 3
  ORDER BY 1, 2, 3
  ```

  Counts may be slightly higher than before — removing suppressions means some
  previously-suppressed rows now appear. Verify with T&L if unexpected spikes
  appear before merging.

- [ ] **Step 6f.3: Commit**

  ```bash
  git commit -m "feat(dbt): remove gradebook exceptions mechanism — AY 2026-2027"
  ```

---

## Task 7 (out of scope): Anchor-row / "in the clear" redesign

Major structural change to `rpt_tableau__gradebook_audit.sql`. Required for the
school-level classroom percentage summary view. Needs a separate spec and plan.
