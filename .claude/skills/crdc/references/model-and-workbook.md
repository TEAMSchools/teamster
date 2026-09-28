# Running the model and the workbook

For the model-fed tabs of the collection sheet. What each branch of
`rpt_tableau__crdc_roster` computes is in the reference doc's "What each branch
computes" table; this file is the procedure.

## Before the workbook

1. Confirm the year. Prod `current_academic_year` must be the year after the
   submission year (2026 for SY2025-26). Check it from the data:

   ```sql
   select academic_year, count(*) as n_rows,
   from `teamster-332318`.kipptaf_tableau.rpt_tableau__crdc_roster
   group by academic_year
   ```

   One `academic_year`, equal to the submission year. Retention flags come from
   the year after.

2. Confirm the fall snapshot line at the top of the SQL matches OCR's definition
   for this cycle ([rollover.md](rollover.md) → Fall snapshot).
3. Rebuild the `src_crdc__student_numbers` tab of the `CRDC` sheet: one row per
   student per section the warehouse cannot derive. Columns
   `crdc_question_section`, `student_number`. Sections read by the model:
   `DSED-2` (distance education), `ATHL-3` (athletics), `ARRS-1` to `ARRS-6`
   (referrals and arrests). Build the rows from the owners' lists as a
   tab-separated file in the session scratchpad and hand the user the path and
   the tab name; never paste student numbers into chat, a commit, or an issue.
   Replace the whole tab each cycle; last cycle's tags are for a different year.
4. Check the tab has no repeated student and section pair: a repeat counts that
   student twice in the section (reference doc → Known issue 1). A student
   tagged to two different sections is fine; they appear once per tag.

   ```sql
   select
       countif(n_rows > 1) as repeated_pairs,
   from
       (
           select student_number, crdc_question_section, count(*) as n_rows,
           from
               `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__crdc__student_numbers
           group by student_number, crdc_question_section
       )
   ```

5. Check the SCED crosswalk for new course codes. The crosswalk lists only the
   codes OCR asks about, so most unmatched codes (electives, advisory,
   elementary subjects) are expected. A math, science, computer science, data
   science, or AP code with no row drops out of `COUR`, `COUR-7`, the science
   branches, and AP. List the unmatched codes with their course names (no
   student data) and review them with the user:

   ```sql
   select
       concat(c.nces_subject_area, c.nces_course_id) as sced_code,
       c.courses_course_name,
       count(distinct c.sections_id) as n_sections,
   from `teamster-332318`.kipptaf_students.int_students__course_enrollments as c
   left join
       `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__crdc__sced_code_crosswalk
       as x
       on concat(c.nces_subject_area, c.nces_course_id) = x.sced_code
   where
       c.cc_academic_year = 2025
       and c._dbt_source_project != 'kippmiami'
       and x.sced_code is null
   group by sced_code, c.courses_course_name
   ```

   Set the year to the submission year. Add each code OCR asks about to the
   `src_crdc__sced_code_crosswalk` tab with its OCR course group, subject group,
   AP group (blank when OCR does not count it as AP), and `ap_tag`. Hand the
   rows over as a tab-separated file, as above.

## The workbook

`CRDC Dashboard.twb` in the CRDC folder is the known copy; it reads
`rpt_tableau__crdc_roster` (the `crdc_dashboard` exposure). Whether a published
copy exists on Tableau Server is an open question; ask the user before looking,
and ask before any Tableau MCP call.

1. The user opens the `.twb` in Tableau Desktop and refreshes the data source.
2. Each sheet in the workbook matches one OCR section, split by region and by
   the form's breakdowns. The user copies each count into the matching
   collection-sheet cell, in the form's order.
3. For any count that looks off, check it in the warehouse before changing
   anything (below).

## A count looks wrong

Count distinct students, never rows: several branches carry one row per course.

```sql
select
    region,
    crdc_question_section,
    count(distinct student_number) as students,
    count(*) as n_rows,
from `teamster-332318`.kipptaf_tableau.rpt_tableau__crdc_roster
group by region, crdc_question_section
```

| What you see                              | Most likely cause                                                            |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| Rows well above distinct students         | A student in several courses (expected), or a student tagged to two sections |
| A course section near zero                | Missing SCED crosswalk rows, or the course is coded dual enrollment          |
| AP lower than the course catalog suggests | The crosswalk has no AP group for that course, so OCR does not count it      |
| `DSED-2`, `ATHL-3`, or `ARRS` empty       | The student-numbers tab has not been rebuilt for this year                   |
| Nonbinary counts present                  | OCR removed the category for SY2025-26; the decision is open (reference doc) |
| Paterson missing                          | Check `region` values; the model includes Paterson, so a gap is upstream     |

Student-level follow-up queries stay in the terminal. Report counts to the user
by region and section, with any cell under 10 shown as "under 10".

## Changing the SQL

Code changes (a new element, a filter fix) follow [rollover.md](rollover.md) →
Update the code. Read the model SQL in full with the Read tool before editing.
