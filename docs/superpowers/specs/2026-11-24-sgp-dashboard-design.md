# SGP dashboard: design

Issue: [#6279](https://github.com/TEAMSchools/teamster/issues/6279) (the branch
is not linked; pull requests say `Refs #6279`). Size: a project. Related:
[#6480](https://github.com/TEAMSchools/teamster/issues/6480) (move the dashboard
onto marts), [#6481](https://github.com/TEAMSchools/teamster/issues/6481)
(STAT's multilingual learner definition). Earlier design for the SGP column
itself: `2026-11-05-cambium-sgp-design.md`.

## Intent

School and network leaders keep asking for student growth percentile (SGP)
results. KTAF's educator evaluation does not use SGP, and the requester is
separately making the case that course rosters are not reliable enough to tie
growth to teachers. The network still needs a tool now, so this dashboard
reports SGP by school and by teacher, says plainly that the numbers are
KIPP-calculated, and shows the roster problems instead of hiding them.

A new Tableau workbook, separate from the State Testing Analysis Tool (STAT).
The old static "SGP Analysis" workbook (project TEMP-Walters) is the rough
model; this design replaces it.

## Audience and access

Decided by the requester:

- Workbook permissions go to 3 Tableau groups: `KNJ-SG-Tableau All Staff KTAF`
  (central office only, no school-based staff), `KNJ-SG-Tableau All SL`, and
  `KNJ-SG-Tableau All HOS`.
- `KNJ-SG-Tableau All Staff KTAF`: everything.
- "School leader" means the 1 School Leader per school on the school record
  (`dim_locations.school_leader_staff_key`), not the leadership team.
- Everyone with access to the workbook sees every school on the Schools tab. The
  Schools data source has no row filter, so the network, region, and level
  comparison rows are right for every viewer.
- Teachers tab: heads of school see every school in their region; school leaders
  see their own school only.
- Nobody else. Teachers do not see the Teachers tab, not even their own row.

## Goals

1. A Schools tab: median SGP and growth-level distribution per school, with
   network, region, and level comparison rows and a grade breakdown.
2. A Teachers tab: the same measures per teacher, matched to students the way
   the state matches them for teacher median SGP (mSGP), as closely as the data
   allows.
3. A student-group filter whose groups come from the state score file.
4. Row-level access as above.

## Non-goals

- Years before 2025-26. The state file first carries SGP in Spring 2026
  (`academic_year = 2025`); there is no earlier file in the warehouse.
- i-Ready, NJGPA, end-of-course tests, Pearson years, Florida, Miami.
- Grade 3 and any test code without SGP. Cambium fills SGP for `ELA04`–`ELA08`
  and `MAT04`–`MAT07` only.
- Matching NJDOE's published school or teacher mSGP.
- Fixing rosters, or any change to STAT (STAT's ML definition is #6481).
- Moving the dashboard onto marts (#6480).

## Anti-goals

- Numbers that read as official state mSGP. Every view says "KIPP-calculated".
- Teacher rows visible to a school leader from another school, or to teachers.
- Quietly cleaning up roster problems, for example dropping co-teachers or
  picking one teacher per student. The point is to show what the roster says.
- Filling a blank state-file student group from PowerSchool.

## What the data holds

Checked 2026-11-24 against prod.

- `int_assessments__state_nj_scores` has 6,597 rows with
  `student_growth_percentile` for `academic_year = 2025`, all Cambium, all with
  a `student_number` after the crosswalk. Every one matches a school enrollment
  on its test date (half-open `entrydate <= test_date < exitdate` on
  `int_extracts__student_enrollments`).
- Raw `src_cambium__njsla` (all 3 districts) carries
  `economic_disadvantage_status` (Y/N) and `nj_ml_status` (`Y`, `F1`–`F4`, or
  null). `stg_cambium__njsla` drops both. The staged `multilingual_learner` is
  Y/N and is `N` for 243 of 244 former learners.
- Race, ethnicity, and disability are already staged and carried
  (`aligned_aggregate_ethnicity`, `aligned_iep_status`, and friends). No 2025-26
  row has both `two_or_more_races = 'Y'` and
  `hispanic_or_latino_ethnicity = 'Y'`, so the order of those 2 checks in
  `aligned_aggregate_ethnicity` does not change any student's group.
- Every 2025-26 section an SGP student was enrolled in for the test subject is a
  `ENG` (ELA) or `MATH` (math) credit-type course; none is a Foundations course.
- Rosters: mockup matching with option C below (calendar days, not school days)
  gave 272 teacher-role-subject rows: 138 lead, 134 co-teacher, 52 under 20
  students. Only 22 of the 272 rows have students who count for no other
  teacher. In departmentalized grade 4, every lead teacher at SPARK, and most at
  KURA, LSP, Life, and THRIVE, is listed as lead for both ELA and math.

## Approaches

1. **Read scores from `int_assessments__state_nj_scores`; rosters, staff, and
   schools from marts (chosen).** Smallest change. The score read is an
   architecture rule A2 exception, tracked in #6480.
2. **Marts first.** Add SGP and the state-file student groups to
   `fct_assessment_scores_enrollment_scoped`, then read marts only. Cleanest,
   but the fact is a hub (Cube and several dashboards), and where student groups
   belong in the marts is its own modeling decision. Filed as #6480.
3. **Pre-aggregate in dbt.** dbt computes medians and shares for every school,
   grade, teacher, and student group. Rejected: every slice and group
   combination must be precomputed, and any new view needs a model change.

Teacher matching (decided by the requester, option C of 3):

- A. Lead teacher on test day only. Rejected: not what the state does, and it
  hides co-teachers.
- B. The state's rules: lead and co-teachers, 70% student rule, 60% teacher
  rule, 20-student minimum.
- C. B plus each teacher's role on screen, a Lead / Co-teacher filter that
  defaults to Lead, and a count of other teachers who share the students
  (chosen).

## Design

### Pull request 1: `cambium` package

Same pattern as the SGP column (`2026-11-05-cambium-sgp-design.md`, PR 1):

- `stg_cambium__njsla`: stage `economic_disadvantage_status` and `nj_ml_status`
  as strings, tagged `contains_pii`.
- `int_cambium__all_assessments` (contract-enforced): carry both, null-padded on
  the NJGPA branch if NJGPA lacks them.
- Do not touch `aligned_ml_status` or `lep_status`; that is #6481.

Then wait for the Dagster prod rebuild in Newark, Camden, and Paterson and
refresh the `zz_stg_*` copies before pull request 2
(`.claude/rules/dbt-models.md`, "kipptaf source consumers of district columns").

### Pull request 2: kipptaf models, exposure

`int_assessments__state_nj_scores`: carry both new columns (null on the Pearson
branch) and derive 2 booleans (my call: here, so #6480 and #6481 can reuse
them):

- `is_multilingual_learner_njdoe`: `nj_ml_status` in `Y`, `F1`, `F2`, `F3`,
  `F4`. NJDOE's definition: current learners plus former learners exited within
  4 years. A blank `nj_ml_status` is `false`: in the state file, blank means not
  a learner and not exited within 4 years (my call). Null only on Pearson rows.
- `is_economically_disadvantaged`: `Y` is `true`, `N` is `false`, blank stays
  null.

Never fill a state-file value from PowerSchool.

`rpt_tableau__sgp_dashboard_schools` (names are my call). Grain: one row per SGP
score (student, subject, test). Reads `int_assessments__state_nj_scores` (the A2
exception; link #6480 in the pull request) and the student enrollment and
location marts. Columns, at least:

- academic year, region, school (location), school level, tested grade
  (`grade_level_when_assessed`), subject, test code;
- `student_growth_percentile`, growth level (`Low` below 35, `Typical` 35 to 65,
  `High` above 65, NJDOE's bands; my call to compute it in dbt so both tabs
  agree), `is_proficient`;
- student groups from the state file: race and ethnicity
  (`aligned_aggregate_ethnicity`, with its `Other` value labeled "Two or more
  races" on screen), disability, `is_multilingual_learner_njdoe`,
  `is_economically_disadvantaged`;
- a student surrogate key for counting, not `student_number`.

School is the school the student was enrolled in on the test date. Only test
codes with SGP appear.

`rpt_tableau__sgp_dashboard_teachers`. Grain: one row per SGP score, teacher,
and role, kept only when both rules below pass. Reads the same score rows plus
`dim_student_section_enrollments`, `dim_course_sections`, `dim_courses`,
`bridge_course_section_teachers`, `dim_staff`, and `dim_school_calendars`.

- **Sections:** the student's non-homeroom sections whose course's
  `dim_courses.academic_subject` equals the test subject (ELA or math), the same
  field the mockup matched on. Count sections the student left mid-year;
  `is_dropped_section` marks exactly those, so do not filter on it. A student
  enrolled in the same section twice (dropped and re-added) sums the days.
- **Window:** in-session school days at the student's school from the first
  in-session day of the year through the day before the test date. Section exit
  dates are exclusive.
- **Teacher rule, per section:** the days the teacher's assignment on that
  section covers, inside the window, divided by the window's days, is at least
  0.60, using `bridge_course_section_teachers.effective_start_date` and
  `effective_end_date`.
- **Student rule, per student and teacher:** the student's window days in
  sections where that teacher passed the teacher rule, summed across those
  sections, divided by the window's days, is at least 0.70. My call: summing
  keeps a student moved between 2 sections of the same teacher, which a
  per-section test would drop for everyone. The mockup tested per section.
- **Roles:** `Lead Teacher` and `Co-teacher` count, each with full credit, as in
  the state's file. `Gradebook Access (edit)` and other roles do not.
- **One row per teacher:** Lead wins over Co-teacher when a teacher holds both
  roles across a student's sections in one subject.
- **Per-teacher context, repeated on each row:** for the teacher and subject,
  the number of their students who also count for another teacher, and the
  number of distinct other teachers those students count for ("Also counts
  for"). A "lead in both subjects" flag: lead teacher for at least 10 students
  in ELA and at least 10 in math at the same school (my call; the threshold
  keeps stray one-student rows from setting it).
- Teacher name and staff key from `dim_staff`.

Carry the window's day counts and both shares on the row, so a reviewer can
check a match without rerunning the logic.

`rpt_tableau__sgp_dashboard_access`. One row per Tableau username and location:

- school leader of a location (`dim_locations.school_leader_staff_key`) gets
  that location;
- head of school of any location in a region
  (`dim_locations.head_of_school_staff_key`, `region_key`) gets every location
  in that region.

The Tableau username is `dim_staff.active_directory_username`, the same account
name the gradebook audit models alias as `school_leader_tableau_username`. The
`KNJ-SG-Tableau All Staff KTAF` group is handled in Tableau with `ISMEMBEROF`,
not in this table.

Exposure `sgp_dashboard` in `exposures/tableau.yml`, `depends_on` the 3 report
models, with the workbook's Tableau id under `asset.metadata.id` once it is
published (the repo's convention).

### Tests

- Uniqueness on each report model's grain.
- Unit tests for the matching rules: exactly 70% and 69.9% for the student;
  exactly 60% and 59.9% for the teacher; a mid-year move between 2 sections of
  the same teacher (counts); a mid-year move between 2 teachers where neither
  reaches 70% (counts for nobody); a co-teacher; a `Gradebook Access (edit)`
  assignment; a teacher end-dated mid-year; a dropped and re-added section.
- Unit tests for growth level at 34, 35, 65, and 66; for
  `is_multilingual_learner_njdoe` on `Y`, `F1`, `F4`, and blank (`false`); and
  for `is_economically_disadvantaged` on `Y`, `N`, and blank (null).
- Reconciliation: the Schools model has 1 row per SGP score in
  `int_assessments__state_nj_scores` for 2025-26.

### Workbook

Built from the mockup the requester reviewed:
`/workspaces/teamster/.superpowers/brainstorm/611425-1795483321/content/sgp-dashboard.html`
in the main checkout (gitignored, not committed: it holds small-cell
aggregates). Its teacher rows came from the reference query in the appendix.

Claude builds the workbook as `.twb` XML with the `tableau-workbook-xml` skill
(requester's decision; the `tableau-build` skill is not installed). That skill
edits an existing workbook, so the base is a fresh pull of the old "SGP
Analysis" workbook (luid `7b52baa1-b8bb-46c2-ba0a-41a032752cd3`, project
TEMP-Walters), repointed at the new report models and rebuilt to this spec.
Follow the skill's loop: assertion before each edit, both checkers, repack,
publish to a non-production project the requester names at that point, render
and look. A render cannot show a hover or a click, and Server accepts files
Desktop refuses, so the requester opens the `.twbx` in Desktop and hovers and
clicks before anything reaches production. Row-level access is proven with the
skill's differential probe, not with Claude's own render.

Every view:

- Title "Student growth (SGP), 2025-26" and a caption: which tests, students
  with an SGP only, KIPP-calculated, will not match NJDOE's mSGP.
- A collapsed "How to read this" note: SGP 1 to 99 and 50 as the state middle;
  median SGP; the growth bands; school on test day; small groups; what is not
  here.
- Filters in one row: student group (All, Economically disadvantaged, Students
  with disabilities, Multilingual learners, and the race and ethnicity groups),
  subject (Both, ELA, Math), sort (median SGP or name), and chart or table.
- Anchored bars on every view (requester's decision). The anchor sits where
  typical growth starts: low growth (red) extends left; typical (gray) then high
  (blue) extend right. The share at typical or higher is printed past the right
  end. Segment labels inside segments of 16% or more.
- A median SGP dot on a 1 to 99 track with a dashed line at 50, and the value.
- Number of students. Groups under 20 are faded and tagged, not hidden.
- Hover tooltip: median; low, typical, high, and typical-or-higher as percent
  and count; percent proficient among these students; "Also counts for" on the
  Teachers tab.
- A table view with the same rows and every measure.
- Colors: low `#e34948`, high `#2a78d6`, typical `#c3c2b7` (light); `#e66767`,
  `#3987e5`, `#57564f` (dark). Validated with the dataviz palette checker; the
  gray is under 3:1 contrast, so segment labels and the table view are required.

Schools tab:

- Filters: region and level.
- Comparison rows: all NJ schools; the selected region; all NJ elementary and
  all NJ middle at the top of each level group.
- Schools grouped by level, sorted by median within the group, with region shown
  beside the name. Placements outside ES and MS (for example KHS, 3 students) go
  in an "Other placements" group at the bottom.
- ELA and math side by side. Clicking a school opens its grade rows below it.

Teachers tab:

- A note on who can see the tab, and a collapsed "How students are matched to
  teachers" note: rosters from PowerSchool, the 70% and 60% rules, full credit
  for lead and co-teachers, Gradebook Access excluded, PowerSchool dates may not
  be what the state received, under 20 faded because the state reports no mSGP
  below 20.
- Filters: school (defaults to the viewer's school for a school leader) and role
  (Lead teachers by default, Co-teachers, All).
- Rows grouped by subject, ELA then math, each led by an "All [school] students"
  row. A teacher in both subjects appears in both groups.
- Name, grades taught, role tag (when role is All), and a "Lead in ELA and math"
  tag. An "Also counts for" column.

## Constraints

- `academic_year` is the starting year: Spring 2026 results are
  `academic_year = 2025`.
- Student groups come only from the state file. PowerSchool supplies only the
  school on test day and the rosters.
- Report models are contract-enforced and need a uniqueness test.
- Report rows are student-level: tag `contains_pii` where the PII rule says so,
  and keep `student_number` and student names out of both models.
- `int_assessments__state_nj_scores` also feeds STAT. Adding columns there must
  not change STAT's rows or values.

## Left to the builder

- Model and column names, and whether the matching logic is 1 report model or a
  CTE chain inside it.
- How the Tableau data sources join the access table, as long as a
  `KNJ-SG-Tableau All Staff KTAF` member sees each row once and a school leader
  sees only their own school's teachers. Prove it with the differential probe in
  the `tableau-workbook-xml` skill's build workflow, not with the builder's own
  render.
- Refresh cadence. Scores change only when a state file lands; rosters change
  daily but the window ends at test day.

## Appendix: the mockup's teacher-matching query

Ad hoc, against prod intermediates, for reconciling the build. It differs from
the design on purpose in 2 ways: it counts calendar days, not in-session school
days, and it tests the student rule per section, not per student and teacher.
Expect the build's counts to differ from its 272 rows by those 2 effects only.

```sql
with
    s as (
        select
            _dbt_source_project,
            student_number,
            discipline,
            grade_level_when_assessed as grade,
            student_growth_percentile as sgp,
            test_date,
            is_proficient,
        from `teamster-332318.kipptaf_assessments.int_assessments__state_nj_scores`
        where
            academic_year = 2025
            and student_growth_percentile is not null
            and student_number is not null
    ),

    se as (
        select s.*, e.school, e.school_level,
        from s
        inner join
            `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as e
            on s._dbt_source_project = e._dbt_source_project
            and s.student_number = e.student_number
            and e.academic_year = 2025
            and e.entrydate <= s.test_date
            and e.exitdate > s.test_date
    ),

    stu as (
        select
            se.*,
            ce.sections_id,
            ce.terms_firstday,

            safe_divide(
                date_diff(
                    least(ce.cc_dateleft, se.test_date),
                    greatest(ce.cc_dateenrolled, ce.terms_firstday),
                    day
                ),
                date_diff(se.test_date, ce.terms_firstday, day)
            ) as stu_share,
        from se
        inner join
            `teamster-332318.kipptaf_powerschool.base_powerschool__course_enrollments`
            as ce
            on se._dbt_source_project = ce._dbt_source_project
            and se.student_number = ce.students_student_number
            and se.discipline = ce.discipline
            and ce.cc_academic_year = 2025
            and not ce.is_homeroom
            and ce.cc_dateenrolled < se.test_date
    ),

    link as (
        select
            stu.*,
            t.teachernumber,
            t.role,

            safe_divide(
                date_diff(
                    least(t.effective_end_date, stu.test_date),
                    greatest(t.effective_start_date, stu.terms_firstday),
                    day
                ),
                date_diff(stu.test_date, stu.terms_firstday, day)
            ) as tch_share,
        from stu
        inner join
            `teamster-332318.kipptaf_powerschool.int_powerschool__section_teachers`
            as t
            on stu._dbt_source_project = t._dbt_source_project
            and stu.sections_id = t.sections_id
            and t.role in ('Lead Teacher', 'Co-teacher')
        where stu.stu_share >= 0.7
    )

-- grouped next to 1 row per teacher, student, and subject (max(role) so Lead
-- wins), then per teacher, subject, and role for the medians and band shares
select *,
from link
where tch_share >= 0.6
```
