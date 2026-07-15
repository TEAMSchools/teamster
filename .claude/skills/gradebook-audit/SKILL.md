---
name: gradebook-audit
description: >-
  Use when any question or task touches the gradebook audit data model or its
  lineage. Triggers: explaining the model, listing refs/lineage/sources for the
  gradebook audit dashboard, adding/removing a flag, adding a region, debugging
  a flag that isn't firing, or working on any model from
  int_tableau__gradebook_audit_* through rpt_tableau__gradebook_audit.
---

# Gradebook Audit Data Model

## Always read first

Before answering any question or making any change, read the reference doc. It
is the authoritative source for lineage, flag definitions, scaffold structure,
and configuration behavior. The spec covers AY 2026-2027 design decisions.

- Reference doc:
  [`docs/reference/gradebook-audit-data-model.md`](../../../docs/reference/gradebook-audit-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md`](../../../docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md`](../../../docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md)

**Key gotcha:** `academic_year` stores the STARTING year. AY 2026-2027 =
`academic_year = 2026`. Confirm this with the user before generating any data.

---

## Configurable thresholds

These values are hardcoded in SQL. When the user asks to change a threshold,
find the location below and update the literal.

| Threshold                                                                                                                                            | Current value | Location                                                                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------- |
| `min_graded_percent` — minimum fraction of expected assignments that must be scored for an assignment to pass the `percent_graded_min_not_met` check | `0.90` (90%)  | `invalid_assign_check` CTE in `int_powerschool__gradebook_assignment_scores_rollup.sql` line 94 |

To change `min_graded_percent`: update the literal `0.90` in the
`invalid_assign_check` CTE (`if(assign_percent_graded < 0.90, true, false)`).

---

## Procedure: List refs, lineage, or sources for the gradebook audit dashboard

Do NOT search the codebase. Go directly to the exposure file:

`src/dbt/kipptaf/models/exposures/tableau.yml`

Find the exposure named `gradebook_audit` and read its `depends_on` list — that
is the authoritative answer. If no `gradebook_audit` exposure exists yet, fall
back to `gradebook_and_gpa_dashboard` and note the rename is pending.

Current `depends_on` list (update if the exposure changes):

- `rpt_tableau__gradebook_audit`

There is also a disabled exposure `gradebook_audit_teacher_report` — mention it
only if the user asks about disabled or archived workbooks.

---

## Procedure: Explain the data model

Read the reference doc and answer from it. For AY 2026-2027 changes, also read
the spec doc.

---

## Procedure: Add a new flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed.
`rpt_tableau__gradebook_audit.sql` has two UNPIVOT lists that both need updating
for a `student_course`-grain flag — `health_calc` (3 flags, drives
`is_healthy_gradebook`) and `flags_unpivot` (2 flags, drives the Branch 3 output
rows). A non-`student_course` flag (teacher/assignment grain, like
`expected_assign_count_not_met`) only goes in `health_calc`'s list and is
emitted as a literal `audit_flag_name`/`audit_flag_value` pair in its own Branch
(see Branch 2's pattern).

1. Add the boolean column to the source model that computes the flag (see
   reference doc flag inventory for which model owns each flag type).
2. Student-course flag: add the flag name to BOTH the `health_calc` and
   `flags_unpivot` UNPIVOT lists in `rpt_tableau__gradebook_audit.sql`.
   Teacher/assignment-grain flag: add it only to `health_calc`'s list and add a
   branch emitting it as a literal, following Branch 2's pattern.
3. Update the properties YAML for the source model and
   `rpt_tableau__gradebook_audit`.
4. Build the modified models. Verify the flag appears in
   `rpt_tableau__gradebook_audit`.

---

## Procedure: Remove a flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed.

1. Remove the boolean column from the source model that computes the flag.
2. Remove the flag name from the `health_calc` UNPIVOT list, and from
   `flags_unpivot`'s UNPIVOT list if it was a `student_course` flag, in
   `rpt_tableau__gradebook_audit.sql`.
3. Update the properties YAML for the source model and
   `rpt_tableau__gradebook_audit`.
4. Build the modified models.

---

## Procedure: Add a new region

1. Ensure the **KIPP NJ Gradebook Audit** PS plugin is deployed to the new
   region's PowerSchool instance and the `U_EXPECTATIONS` table is populated.
   Plugin source and update instructions:
   [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins)
2. Verify `int_powerschool__u_expectations_qtd_unpivot` returns rows for the new
   region.
3. No flag sheet changes needed — the UNPIVOT lists in
   `rpt_tableau__gradebook_audit` apply to all regions. The only exclusions,
   applied uniformly across all three branches in
   `int_tableau__gradebook_audit_flags_calculations`, are
   `_dbt_source_project != 'kippmiami'` and `school_level_alt != 'ES'` (MS/HS
   only). Confirm sections for the new region appear in
   `int_tableau__gradebook_audit_flags_calculations`.

---

## Procedure: Work on the gradebook audit dashboard after academic year rollover

**Trigger phrases:** "we have swapped academic years on the database and I need
to make edits to the gradebook audit dashboard before the start of the school
year", "the database rolled over to the new year but school hasn't started yet
and I need data to work on the dash", "I need to work on the gradebook audit
views this summer"

**What's happening:** In July, the data engineering team bumps
`current_academic_year` (e.g., 2025 → 2026). At that point:

- The scaffold filters to `academic_year = 2026`, but PowerSchool has no
  sections or enrollments for the new year yet — the scaffold returns no rows.
- Even if sections existed, quarter course grades for the prior year live in
  `stg_powerschool__storedgrades` (archived), not
  `base_powerschool__final_grades` (which only holds live/active grades for the
  current year).

Both problems must be fixed together. Changing only the scaffold year or only
the `grades_type` will still produce no data.

**Files to edit:**

- `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags_calculations.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`

**Two changes to make:**

1. In `int_tableau__gradebook_audit_flags_calculations` — change the year filter
   (appears 3 times, marked with `/* summer toggle: see skill */`):

   ```sql
   -- change this (appears 3 times):
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

   Also change the `quarter_course_grades` join grades type filter (appears 1
   time, also marked with `/* summer toggle: see skill */`):

   ```sql
   -- change this:
   and qg.grades_type = 'current_year'
   -- to this:
   and qg.grades_type = 'last_year'
   ```

   This routes the grade lookup to `stg_powerschool__storedgrades` (prior-year
   archived quarter grades) instead of `base_powerschool__final_grades` (empty
   until teachers start entering grades for the new year).

2. In `rpt_tableau__gradebook_audit` — change the year filter in both UNION
   branches (appears twice in WHERE clauses, marked with
   `/* summer toggle: see skill */`):

   ```sql
   -- change this (appears 2 times):
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

Build and verify after both changes:

```bash
uv run dbt build \
  --select int_tableau__gradebook_audit_flags_calculations rpt_tableau__gradebook_audit \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state target/prod
```

**When to revert:** once the new school year starts and teachers begin entering
grades in PowerSchool (typically Q1), revert all changes:
`current_academic_year - 1` → `current_academic_year` in both files, and
`'last_year'` → `'current_year'` in flags calculations.

---

## Procedure: Debug a flag that isn't firing

Ask: which flag, region, school level, and quarter.

Check in order:

1. **Boolean `true` in the source model?** Find which model computes the flag
   (reference doc flag inventory) and query it directly.
2. **Section in the scaffold?** Check
   `int_tableau__gradebook_audit_flags_calculations` for the section/quarter
   combination. Two silent exclusion rules apply uniformly across all three
   branches (`sections_teacher`, `assignment_teacher`, `student_course`):
   - `_dbt_source_project != 'kippmiami'` — Miami is excluded at source (AY
     2026-2027 onward)
   - `school_level_alt != 'ES'` — ES is excluded everywhere, including the
     `student_course` branch; ES is handled separately by
     `rpt_tableau__gradebook_es_comments`
3. **Flag in the UNPIVOT list?** Two lists in `rpt_tableau__gradebook_audit.sql`
   matter: `health_calc`'s 3-flag list (`qt_percent_grade_greater_100`,
   `qt_grade_70_comment_missing`, `expected_assign_count_not_met`) drives
   `is_healthy_gradebook`; `flags_unpivot`'s 2-flag list (the same two
   `student_course` flags) drives the Branch 3 output rows.
   `expected_assign_count_not_met` is emitted as a hardcoded literal in Branch
   2, not unpivoted.

`stg_google_sheets__gradebook_flags` is disabled — do not check the allowlist
sheet. `stg_google_sheets__gradebook_exceptions` is also disabled — do not check
for exception rows.

---

## Procedure: Work on a model in the lineage

Read the reference doc section for the specific model before touching it. Key
rules from the implementation plan:

- **Build one model at a time** — never cascade downstream mid-refactor.
- A grain change in the scaffolds cascades to all downstream join conditions.
  Downstream models must be updated before a full chain build is valid.
