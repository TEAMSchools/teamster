# Ad hoc CSGF surveys outside the Portal/HSDC

Referenced from `SKILL.md`. Not everything CSGF asks for comes through the
Portal or the HSDC sheet. CSGF's Analytics team
(`datacollection@chartergrowthfund.org`) can also send a one-off email with a
short Google Form survey, separate from the main collection, with its own
deadline tied to the same cycle. Treat one of these the same way as any other
CSGF item -- verify against real data, don't guess.

**Worked example: Florida B.E.S.T. Algebra 1 Participation & EOC Performance
Survey (2026-2027 cycle).** Org-level, one response per org (coordinate via Key
Contacts so two people don't duplicate it), 4 questions: % of 8th graders and %
of 9th graders enrolled in Algebra 1 (or equivalent) in 2025-2026, and among
each group, % who scored Level 3+ on the 25-26 B.E.S.T. Algebra 1 EOC. Since
KTAF's only Florida schools are in Miami, this is a Miami-only survey in
practice even though it's asked at the org level.

- **For Algebra 1 course enrollment, use the district-specific `kippmiami`
  project's data, not kipptaf's cross-district extracts.** Charlie's guidance,
  confirmed correct: `kipptaf`'s Focus-based models have no course- enrollment
  staging built yet for Miami (the same gap already documented in
  `known-data-risks.md`'s forward-risk note for AP/Honors course tags), so
  there's no way to get a real Algebra 1 enrollment count from there. But Miami
  was still on PowerSchool through the end of the 2025-2026 school year (the
  archive `kippmiami_powerschool`, frozen at the final ODBC pull 2026-07-01 --
  see `src/dbt/kippmiami/CLAUDE.md`) -- for any historical Miami question, check
  that project's own `base_powerschool__course_enrollments` /
  `base_powerschool__student_enrollments` / `stg_powerschool__courses` first,
  not kipptaf's Focus-sourced tables.
- **The 2025-2026 real numbers (Miami, confirmed 2026-09-11):** grade 8 -- 157
  total 8th graders (all at Courage Academy; Royalty is K-4 only), 87 of them
  actually enrolled in `Algebra I` or `Algebra I Honors`
  (`stg_powerschool__courses.course_name`) per real course-enrollment records --
  **55.4% enrolled**. Of those 87, 84 have a matched EOC record in
  `kippmiami_fldoe.int_fldoe__all_assessments`
  (`assessment_subject = 'Algebra I'`, `academic_year = 2025`) and 74 scored
  `is_proficient` (Level 3+). **Decision: used test-takers as the denominator
  (74/84 = 88.1%)**, not all enrollees (74/87 = 85.1%) -- both are defensible
  reads of "among the 8th graders who took Algebra 1," but the collection owner
  chose test-takers.
- **Grade 9 is genuinely N/A for the 2025-2026 school year, not a data gap.**
  Miami had **zero 9th graders enrolled anywhere in 2025-2026** -- confirmed via
  `int_extracts__student_enrollments`: Legacy Elementary, Legacy Middle, and
  Miami Technical High (Miami's only HS) all first appear at
  `academic_year = 2026`, not `2025`. Miami Tech, the network's first Florida
  high school, opened for the 2026-2027 school year, after the year this survey
  asks about. The collection owner entered N/A for both grade-9 questions on
  this basis.
- **Don't proxy course enrollment from EOC test-taking counts if a real
  enrollment source exists.** An earlier pass on this same question used EOC
  test-taker counts as a stand-in for Algebra 1 enrollment (assuming Florida's
  EOC-for-enrolled-students requirement made them equivalent) before the
  `kippmiami_powerschool` archive was checked -- that produced a different, less
  accurate number (84/181 = 46.4%) than the real course-enrollment count (87/157
  = 55.4%). The two aren't identical: 3 of the 87 real Algebra 1 enrollees have
  no matched EOC score at all (absence, exemption, etc.).
- **Forward risk, flagged by the collection owner: `kippmiami_powerschool` is a
  one-time, frozen resource, not a repeatable source.** It's the archive of
  Miami's retired PowerSchool SIS, frozen at the final ODBC pull (2026-07-01) --
  it will never gain a 2026-2027 school year. Next cycle's version of this same
  survey (or anything else needing Miami course enrollment/schedule data for
  2026-2027 onward) can't reuse this approach -- Miami is fully on Focus by
  then, and Focus course/schedule data has no dbt staging model yet (the same
  gap already noted for AP/Honors course tags in `known-data-risks.md`). Expect
  to have to ask where Focus actually stores schedule/course data (the raw
  `dagster_kippmiami_dlt_focus` tables, almost certainly, per the Focus
  custom-field/table conventions in `src/dbt/focus/CLAUDE.md`) and build the
  join fresh, rather than looking for a `kippmiami_powerschool` equivalent that
  won't exist.
