# Rollover and preliminary scores

## Procedure: Academic year rollover

After `current_academic_year` bumps in July:

- `rpt_tableau__state_assessments_dashboard` keeps
  `academic_year >= current_academic_year - 7` on official rows (the enrollment
  join applies it to Florida too), so history rolls off the back automatically.
  No toggle to flip.
- The `schedules_current` CTE reads `current_academic_year` for teacher
  attribution. Before the new year's PowerSchool sections exist,
  `school_current` / `teacher_name_current` come back null on the roster.
  Expected, not a bug.
- Comparison data for the new year does not exist yet. Comps stay empty for it
  until interim figures or the official file land
  ([comps-sheet.md](comps-sheet.md)).

## Procedure: Spring preliminary scores

The preliminary branch reads only Pearson's student list report
(`int_pearson__student_list_report`), in both the score view and
`int_tableau__state_assessments_demographic_comps`. Nothing from Cambium feeds
it, so from Spring 2026 it is dormant. Before promising preliminary results, say
so; whether Cambium publishes an equivalent early file is unknown.

When a preliminary file does exist, the branch gates itself: it is joined to
`valid_prelim_assessments`, which keeps a year and test only while
`int_assessments__state_nj_scores` has no Spring row with that
`assessment_name`. Do not comment it in or out by hand.

The workbook lives in the Tableau project `Production`. A version showing
preliminary results is published to a restricted folder, never to `Production`.
The rest of the procedure is in doc _Spring: preliminary scores_, which marks it
unverified against current practice; confirm with the owner.
