# Running the grad plan refresh

The full "before you use it" procedure, for a master-scheduling push or any time
Teaching and Learning needs current numbers. Newark and Camden only — Paterson
and Miami have no PowerSchool grad plan data (see the doc's "Decisions").

## 1. Run PowerSchool's Data Capture, every grade, every high school

PowerSchool's grad plan tables do not update on their own as students earn
credits, and nothing recomputes this automatically. Before anyone reads the
sheet, someone has to re-run PowerSchool's own routine:

1. Log in to each region's PowerSchool instance (one per region: Newark and
   Camden).
2. Switch to the high school you want. Do not run it from District Office.
3. From the school's Start Page, click a grade level to select that grade's
   students.
4. Open the student-selection action menu (bottom of the page, the dropdown next
   to "Select By Hand") and choose **Graduation Plan Progress Report Data
   Capture**.
5. Click **Submit** on the page that opens.
6. Repeat for every grade level, at every high school.
7. Check back often. Some grade levels take several minutes; plan on most of a
   day.

## 2. Refresh the source sheet's extract tabs

This step comes from inspecting the sheet, not a confirmed procedure — ask the
data team before relying on it. Refresh the IMPORTRANGE Sources sheet's extract
tabs (one per school and diploma type) so they pick up the new Data Capture
numbers. The dbt models behind them (`rpt_gsheets__grad_plan_tracking` and its
parents) are views and need no separate build step; they read as-is whenever the
sheet's Connected Sheets tab recomputes.

## 3. Check the three trackers

Once the source sheet is refreshed, spot-check each Reports tracker — KHS, NLH,
NCA — that the tabs reflect the new numbers. Each tab reads a fixed row range
from its source tab, so a source tab that has outgrown that range truncates
silently; if a school reports students missing after this refresh, that is the
first thing to rule out, not just a Data Capture gap.

## Known traps

- **Missing rows usually mean Data Capture wasn't run for that grade or school,
  not a pipeline bug.** The doc's "Known issues, need to fix" has the diagnostic
  query: as of the last check, Camden had under half of currently enrolled
  9th-12th graders with any row in `int_powerschool__gpprogress_grades`, and
  Newark had about two-thirds — the gap tracks Data Capture history, not the
  diploma-plan filter.
- **Paterson and Miami never appear.** Paterson's PowerSchool instance has empty
  grad-plan tables; Miami never ran PowerSchool grad plans. Don't troubleshoot a
  "missing" Paterson or Miami row as a pipeline defect.
