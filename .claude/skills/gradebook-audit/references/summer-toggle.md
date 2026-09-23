# Procedure: Work on the gradebook audit dashboard after academic year rollover

**Trigger phrases:** "we have swapped academic years on the database and I need
to make edits to the gradebook audit dashboard before the start of the school
year", "the database rolled over to the new year but school hasn't started yet
and I need data to work on the dash", "I need to work on the gradebook audit
views this summer"

**Scope — this is the data-team dbt toggle only.** Updating the assignment
_expectations_ for the new year is a separate task owned by the academics team,
done in PowerSchool via the `U_EXPECTATIONS` plugin — not a dbt change. For
that, see
[Procedure: Roll the assignment expectations over to a new year](../playbooks/academic-year-rollover.md);
for the plugin itself and who owns it, see
[`../playbooks/maintain-the-plugin.md`](../playbooks/maintain-the-plugin.md).
The steps below cover only the dbt-side year / grade-source toggle.

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

**Files to edit** (as of the July 2026 intermediate extraction — the student
grade/comment toggle points moved out of
`rpt_gsheets__gradebook_audit_student_flags` into the new
`int_extracts__gradebook_audit_student_flags`, which the gsheets report now
reads; the gsheets report itself no longer carries any toggle):

- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`
- `src/dbt/kipptaf/models/students/intermediate/int_extracts__gradebook_audit_student_flags.sql`
- `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__u_expectations_qtd_unpivot.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`
- `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gradebook_audit_template.sql`
- `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gradebook_audit_all_weeks.sql`

**Six changes to make:**

1. In `rpt_tableau__gradebook_audit` — change the year filter in
   `category_join`'s `WHERE` clause (1 occurrence, marked
   `/* summer toggle: see skill */`):

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

2. In `int_extracts__gradebook_audit_student_flags` — change both occurrences
   (marked `/* summer toggle: see skill */`): the outer `academic_year` filter,
   and the `quarter_course_grades` join's `grades_type` filter:

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

   ```sql
   -- change this:
   and qg.grades_type = 'current_year'
   -- to this:
   and qg.grades_type = 'last_year'
   ```

   This routes the grade lookup to `stg_powerschool__storedgrades` (prior-year
   archived quarter grades) instead of `base_powerschool__final_grades` (empty
   until teachers start entering grades for the new year).

3. In `int_powerschool__u_expectations_qtd_unpivot` — change both occurrences
   (one filters `int_powerschool__calendar_week`, marked
   `-- summer toggle: see skill`; one stamps the output `academic_year` column,
   marked `/* summer toggle: see skill */`):

   ```sql
   -- change this (appears 2 times):
   {{ var("current_academic_year") }}
   -- to this:
   {{ var("current_academic_year") - 1 }}
   ```

   This model has no `academic_year` column upstream (`U_EXPECTATIONS` reflects
   whatever's currently live in PowerSchool, not a specific year) — its
   `academic_year` is a literal stamped on every row.
   `rpt_tableau__gradebook_audit` joins to it on `academic_year` among other
   keys; leaving this model at `current_academic_year` while
   `rpt_tableau__gradebook_audit` is toggled to `- 1` breaks that join and
   silently drops all `category_summary`/ `assignment_detail` rows.

4. In `rpt_tableau__gradebook_es_comments` — change the year filter (1
   occurrence, marked `-- summer toggle: see skill`):

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

   **No `grades_type`/`storedgrades` fallback here, unlike the other three
   files** — this was tried and reverted. The other files audit MS/HS grades
   (or, for `u_expectations_qtd_unpivot`, aren't grade-sourced at all), and
   `stg_powerschool__storedgrades` genuinely has MS/HS archived Q-term data for
   the prior year, so a union+fallback pattern gives correct results there.
   `es_comments` only needs comments for ES schools, and
   `stg_powerschool__storedgrades` has **no Q-term data at all for ES schools in
   academic years 2021, 2024, or 2025** (confirmed empty via direct query — only
   2020/2022/2023 exist). Adding the same union pattern here doesn't add safety;
   it silently shows every comment as missing instead of falling back to real
   data, because the fallback source has nothing to fall back to. The
   single-source join works today because `base_powerschool__final_grades` still
   holds live prior-year data even after the academic-year var rolls over
   (confirmed empirically: AY2025 rows were still present after the var bumped
   to 2026).

   If this toggle ever stops returning real comments (i.e.
   `base_powerschool__final_grades` gets cleared for the prior year before the
   new year's data is ready), do NOT reflexively re-add a
   `stg_powerschool__storedgrades` union to fix it — first confirm whether the
   ES archival gap has actually been backfilled:

   ```sql
   select schoolid, academic_year, count(*) as n
   from `teamster-332318`.kipptaf_powerschool.stg_powerschool__storedgrades
   where storecode_type = 'Q'
     and schoolid in (73255, 73257, 73259, 179901, 73256, 73254) -- non-Sumner ES schools
   group by 1, 2
   order by 1, 2 desc
   ```

   If the target prior year is still missing from the results, there is no real
   fallback data source available; escalate instead of shipping a change that
   silently reports every comment as missing.

5. In `rpt_gsheets__gradebook_audit_template` — the expectations upload template
   T&L uses to build the PowerSchool CSV. Change all THREE occurrences, each
   marked `-- summer toggle: see skill` except the last: one filters
   `int_students__school_directory` in the `school_levels` CTE, one filters
   `int_students__calendar_week` in the `week_school_levels` CTE, and one stamps
   the output `academic_year` column, marked `/* summer toggle: see skill */`:

   ```sql
   -- change this (appears 3 times):
   {{ var("current_academic_year") }}
   -- to this:
   {{ var("current_academic_year") - 1 }}
   ```

   The `school_levels` filter is easy to miss and matters: it resolves
   `school_level_alt`, so leaving it at the current year while the calendar
   filter is toggled back resolves prior-year weeks against current-year school
   levels. Today that only moves Sumner, but it is silent when wrong.

   **While toggled, this model shows the PRIOR year's week grid.** It is the
   sheet T&L exports to upload the NEW year's expectations, so do not hand it
   over as the new-year grid until the toggle is reverted — they would be
   editing last year's weeks.

6. In `rpt_gsheets__gradebook_audit_all_weeks` — the full-year companion grid on
   the same spreadsheet. Change both occurrences, both marked
   `-- summer toggle: see skill`: one filters `int_students__school_directory`
   in the `school_levels` CTE, one filters `int_students__calendar_week` in the
   `week_school_levels` CTE:

   ```sql
   -- change this (appears 2 times):
   {{ var("current_academic_year") }}
   -- to this:
   {{ var("current_academic_year") - 1 }}
   ```

   Unlike the template, this model projects `academic_year` straight from
   `int_students__calendar_week` rather than stamping it as a literal, so there
   is no third occurrence to change — the column follows the filter.

Build and verify after all six changes:

```bash
uv run dbt build \
  --select int_powerschool__u_expectations_qtd_unpivot \
    int_extracts__gradebook_audit_student_flags \
    rpt_gsheets__gradebook_audit_student_flags rpt_tableau__gradebook_audit \
    rpt_tableau__gradebook_es_comments \
    rpt_gsheets__gradebook_audit_template \
    rpt_gsheets__gradebook_audit_all_weeks \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state target/prod
```

`int_extracts__gradebook_audit_student_flags` must be in the `--select` list
(not just the two reports) — it now holds the student toggle, and `--defer`
would otherwise read the un-toggled prod copy.

**When to revert:** once the new school year starts and teachers begin entering
grades in PowerSchool (typically Q1), revert all changes:
`current_academic_year - 1` → `current_academic_year` in all six files, and
`'last_year'` → `'current_year'` in
`int_extracts__gradebook_audit_student_flags`.
