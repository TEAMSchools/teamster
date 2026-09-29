## Procedure: Academic year rollover

After `current_academic_year` bumps in July:

- `rpt_tableau__state_assessments_dashboard` filters scores to
  `current_academic_year - 7`, so history rolls off the back automatically. No
  toggle to flip.
- The **schedules** CTEs read `current_academic_year` for teacher attribution.
  Before the new year's PowerSchool sections exist, `school_current` /
  `teacher_name_current` come back null on the roster views. Expected, not a
  bug.
- The **preliminary-score branch** self-deactivates: it is gated on
  `valid_prelim_assessments`, which drops an assessment once official scores for
  that year land in `int_pearson__all_assessments`. Do not comment it in or out
  by hand; that gating was built specifically to remove that chore.
- Comparison data for the new year will not exist. Expect the comps views to be
  empty for it until either a bootstrap or the official file lands.

---
