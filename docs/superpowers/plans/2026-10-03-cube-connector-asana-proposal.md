# Asana Plan: Dates for Data Marts + Semantic Layer

Refs [#5673](https://github.com/TEAMSchools/teamster/issues/5673). Builds on the
[gap catalog](2026-10-02-cube-gap-catalog.md).

The Asana project was restructured on Oct 8, 2026: workstream sections, one
milestone per plan milestone (M0 to M5.5), dashboard tasks with a subtask per
measure and dimension, and a six-step transition checklist on each key
dashboard. This plan gives every open task in that structure a due date, taken
from the SY26-27 project plan as of Oct 8. Only one milestone (M4.4) has a date
today, so the
[semantic layer status page](https://teamschools.github.io/teamster/launch/semantic-layer/)
shows an empty timeline.

Nothing in Asana changes until this plan is approved.

## Roles

Owners are named by role. The internal project plan maps roles to people.

| Role                 | Owns                                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| Project lead         | Governance; workstreams 3 and 4; the grades/GPA and student-dashboard builds; the key-dashboard rebuilds |
| Cube/mart lead       | Workstream 1 (domain build, permissioning); approves Cube YAML                                           |
| Enablement lead      | Workstream 2 (enablement, communications, support); owns assessments from Dec 18                         |
| Engineering reviewer | Mart code approval; 48-hour pull request reviews                                                         |
| Data director        | Most project calls; the student persistence review                                                       |
| Analysts             | Zendesk, recruitment and surveys                                                                         |
| New analyst          | The FRESH enrollment metric set; the project lead stands in until the hire                               |

## The timeline

Every date is a Friday unless noted. Winter break is assumed to run Dec 21, 2026
to Jan 1, 2027; it has not been checked against the school calendar.

| Domain                          | Data work (marts)                  | Built in Cube | Matches, privacy review, Tableau rebuild | Verified | Pilot run         | Launched |
| ------------------------------- | ---------------------------------- | ------------- | ---------------------------------------- | -------- | ----------------- | -------- |
| Assessments                     | Oct 23 to Nov 20 (see Assessments) | Dec 4         | Dec 11                                   | Dec 18   | Nov 20 (cohort 2) | Jan 15   |
| Ops (attendance, Ops Dashboard) | Jan 15 to Feb 12                   | Feb 19        | Feb 26                                   | Feb 26   | Mar 12            | Mar 26   |
| Ops: FRESH metric set           | Feb 19                             | Feb 19        | No dashboard rebuild                     | Feb 26   | None              | With ops |
| Grades/GPA                      | Mar 12                             | Apr 9         | Apr 16                                   | Apr 16   | May 7             | May 14   |
| Student dashboards              | Apr 30                             | May 14        | May 21                                   | May 21   | None in the plan  | Jun 4    |
| Zendesk                         | Dec 18                             | Jan 15        | Jan 29                                   | Jan 29   | Feb 5             | Feb 12   |
| Recruitment                     | Feb 12                             | Feb 26        | Mar 12                                   | Mar 12   | Mar 19            | Mar 26   |
| Surveys                         | Mar 19                             | Apr 2         | Apr 16                                   | Apr 16   | Apr 23            | Apr 30   |
| Observations                    | Apr 16                             | Apr 30        | May 14                                   | May 14   | May 21            | May 28   |

Recruitment depends on the Oct 16 decision on whether it stays an analyst-built
domain. The four analyst-built domains run their pilot one week before each
launch (decided Oct 9; the project plan has no pilot date for them).

Other anchors: charter sent Oct 16 and signed off Oct 23; usage logging and the
eval loop live Nov 20; org plugin beta Jan 15; midpoint review and
stretch-domain decision Feb 26; project close Jun 25, 2027.

## How dates are assigned

1. **Milestones** take the plan's milestone date.
2. **Tasks a milestone depends on** take the date of the matching plan row, or
   the milestone's date when no row matches.
3. **Dashboard tasks** are due on their domain's verification date. The
   verification milestones depend on the dashboard tasks, so a later date would
   block them. The launch is tracked on the dashboard's `Launched` checklist
   subtask.
4. **Checklist subtasks** on key dashboards take the domain's step dates from
   the timeline table. Asana lists `Pilot run` before
   `Rebuilt in Tableau on Cube`; the dates follow the plan, where the rebuild
   comes first for every domain except assessments.
5. **Measure and dimension subtasks** are due on the domain's `Built in Cube`
   date, except the measures listed under "Measure-level exceptions".
6. **Mart tasks** (`fct_`, `dim_`, `bridge_`) take the date of the plan row that
   names them, or two weeks before the domain's `Built in Cube` date.
7. **No date:** the four stretch sections until the Feb 26 decision, the parking
   lot, the `Open Issues` rollup tasks (their child issues are dated where a
   milestone needs them), the team meeting tasks, and completed tasks.
8. **An existing Asana date that is earlier than the plan stays.** Later ones
   were settled on Oct 9; see "Decisions made on Oct 9".

## Milestones

| Milestone                                                  | GID              | Owner role           | Due                        |
| ---------------------------------------------------------- | ---------------- | -------------------- | -------------------------- |
| M0 Plan approved                                           | 1219235228654243 | Project lead         | Oct 23, 2026               |
| M1.1 Assessments verified, DDI Suite rebuilt               | 1219235308365063 | Cube/mart lead       | Dec 18, 2026               |
| M1.2 Ops verified                                          | 1219235025077769 | Cube/mart lead       | Feb 26, 2027               |
| M1.3 Grades/GPA verified                                   | 1219235025827628 | Project lead         | Apr 16, 2027               |
| M1.4 Student dashboards covered                            | 1219235307785677 | Project lead         | May 21, 2027               |
| M1.5 Analyst-built domains verified                        | 1219235229132440 | Cube/mart lead       | May 14, 2027               |
| M1.6 Stretch-domain decision                               | 1219235058907087 | Cube/mart lead       | Feb 26, 2027               |
| M1.7 Permissioning ready for each launch                   | 1219235308167839 | Cube/mart lead       | Jan 15, 2027               |
| M2.1 Domain owners named                                   | 1219235308627079 | Enablement lead      | Feb 26, 2027               |
| M2.2 Support boundary published                            | 1219234963765039 | Enablement lead      | Nov 13, 2026               |
| M2.3 Standard pilot kit                                    | 1219235025198061 | Enablement lead      | Nov 6, 2026                |
| M2.4 Cohort 2 onboarded                                    | 1219235025704269 | Project lead         | Nov 20, 2026               |
| M2.5 Launch package per domain                             | 1219235025604113 | Enablement lead      | Jun 4, 2027                |
| M2.6 Org-wide engagement plan                              | 1219234963582140 | Enablement lead      | Nov 20, 2026               |
| M2.7 Ongoing onboarding cycle                              | 1219235307438415 | Enablement lead      | Apr 30, 2027               |
| M3.1 Org plugin (beta) replaces project-knowledge delivery | 1219235116996473 | Project lead         | Jan 15, 2027               |
| M3.2 Usage logging and eval loop live                      | 1219235308676955 | Project lead         | Nov 20, 2026               |
| M3.3 Test-question sets                                    | 1219235025703849 | Project lead         | May 14, 2027               |
| M4.1 Build standards written                               | 1219235308629473 | Cube/mart lead       | Jan 8, 2027                |
| M4.2 Data team trained                                     | 1219235329945594 | Cube/mart lead       | Nov 13, 2026               |
| M4.3 Cube/mart creation skill shipped                      | 1219235059624720 | Cube/mart lead       | Jan 15, 2027               |
| M4.4 Review path that scales                               | 1219235024629036 | Engineering reviewer | Dec 18, 2026 (already set) |
| M4.5 Every analyst ships one reviewed view                 | 1219235025270542 | Project lead         | May 28, 2027               |
| M4.6 New analyst onboarded into mart and cube work         | 1219235307683522 | Project lead         | The hire date, once known  |
| M5.1 Drift rule adopted                                    | 1219235228890789 | Not yet decided      | Jan 15, 2027               |
| M5.2 Legacy-vs-Cube checks running                         | 1219235307739161 | Not yet decided      | May 28, 2027               |
| M5.3 Guidance release cadence                              | 1219235308484186 | Not yet decided      | Jan 15, 2027               |
| M5.4 Data-change cadence agreed                            | 1219235330086393 | Not yet decided      | Feb 26, 2027               |
| M5.5 Ownership after June agreed                           | 1219235043141920 | Not yet decided      | May 28, 2027               |

## Task dates by section

### 0 · Governance

| Task                                                | GID              | Due          |
| --------------------------------------------------- | ---------------- | ------------ |
| Size the stretch domains from the gap catalog       | 1219235229404345 | Feb 12, 2027 |
| Review the whole deferral log at the midpoint       | 1219235228892596 | Feb 26, 2027 |
| Schedule or drop every remaining deferral-log entry | 1219235118345654 | Jun 25, 2027 |

M0 also depends on six action items from the Oct 6 meeting; see "Dependencies
outside the sections".

### 1 · Permissioning

| Task                                                                                   | GID              | Due          |
| -------------------------------------------------------------------------------------- | ---------------- | ------------ |
| Open Issues — Access & Security (triage all open issues against launch dates)          | 1219086221167065 | Dec 4, 2026  |
| Check whether shared Claude artifacts respect each viewer's access; set a sharing rule | 1219235025752972 | Dec 11, 2026 |
| #4237 small-cell suppression (child of the rollup)                                     | 1215942398896201 | Jan 8, 2027  |
| #5524 Miami staff with no work-assignment location (child of the rollup)               | 1218824350465422 | Feb 12, 2027 |

The rollup is dated because the plan's triage row maps to it. Small-cell
suppression must land before the assessments launch on Jan 15.

### 1 · Shared dimensions and groupings

| Task                                              | GID              | Due          | Why                                                     |
| ------------------------------------------------- | ---------------- | ------------ | ------------------------------------------------------- |
| NJ student tier / tutoring buckets and 504 status | 1219235117880911 | Nov 6, 2026  | Plan row                                                |
| dim_student_iep_status                            | 1219288375398321 | Nov 20, 2026 | Used by all 7 assessment dashboards                     |
| dim_student_ell_status                            | 1219288212316965 | Nov 20, 2026 | Used by 4 assessment dashboards                         |
| dim_student_meal_eligibility_status               | 1219288550347153 | Nov 20, 2026 | Used by STAT; ops needs it by Feb 12                    |
| dim_student_homeless_status                       | 1219288375213085 | No date      | Only the Behavior stretch domain uses it                |
| dim_student_contact_persons                       | 1219288623977592 | No date      | Only the Staff and certification stretch domains use it |
| dim_staff_grade_levels_taught                     | 1219288623793643 | No date      | No core dashboard uses it yet                           |
| dim_staff_work_assignments                        | 1219288375257808 | No date      | No core dashboard uses it yet                           |

### 1 · Assessments

| Task                                                           | GID              | Due                                           |
| -------------------------------------------------------------- | ---------------- | --------------------------------------------- |
| Lock what "verified" includes; checkpoint                      | 1219235228944467 | Start Oct 16, due Dec 4, 2026                 |
| dim_assessment_goals                                           | 1219235308948092 | Oct 23, 2026                                  |
| dim_college_assessment_goals                                   | 1219235025928051 | Oct 30, 2026                                  |
| fct_assessment_scores_student_scoped (CARAT)                   | 1214075610424619 | Nov 6, 2026                                   |
| fct_iready_lessons                                             | 1219285715506895 | Nov 13, 2026                                  |
| fct_dibels_progress_monitoring                                 | 1219285828933892 | Nov 20, 2026                                  |
| fct_assessment_standard_scores                                 | 1219285828786749 | Nov 20, 2026                                  |
| fct_sight_words                                                | 1219286000584515 | Nov 20, 2026                                  |
| dim_assessment_comparisons                                     | 1219285715581897 | Nov 20, 2026                                  |
| dim_student_testing_accommodations                             | 1219285989040081 | Nov 20, 2026                                  |
| dim_college_assessment_expectations                            | 1219285941380935 | Nov 20, 2026                                  |
| fct_dual_enrollment_grades                                     | 1219285941416926 | Nov 20, 2026                                  |
| fct_student_ap_course_enrollments                              | 1219301358692563 | Nov 20, 2026                                  |
| Matching sign-off and privacy review: assessments              | 1219235059572563 | Dec 11, 2026                                  |
| Review assessment pull requests within 48 hours through Dec 18 | 1219235329948012 | Dec 18, 2026 (already set)                    |
| Check the deferral log for assessments                         | 1219235401039821 | Dec 18, 2026                                  |
| Clear marts V1 for production use                              | 1219235025270362 | Nov 13, 2026 (the plan date; replaces Dec 18) |

Dashboards, all due Dec 18, 2026, with measure and dimension subtasks due Dec 4:

| Dashboard                                               | GID              | Checklist dates                                                                                                |
| ------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------- |
| DDI Suite (key dashboard)                               | 1213823831345180 | Built Dec 4 · Matches Dec 11 · Privacy Dec 11 · Pilot run Nov 20 (cohort 2) · Rebuilt Dec 11 · Launched Jan 15 |
| College Admission Readiness Assessments Tracker (CARAT) | 1213823831141286 | No checklist                                                                                                   |
| Literacy Dashboard                                      | 1213823922716082 | No checklist                                                                                                   |
| State Testing Analysis Tool                             | 1213823789082035 | No checklist                                                                                                   |
| APM Dashboard                                           | 1213823789013913 | No checklist                                                                                                   |
| State Testing Accommodations Tracker                    | 1213823789021563 | No checklist                                                                                                   |
| KIPP Miami FAST & iReady Analysis                       | 1213823922772842 | No checklist                                                                                                   |

The Oct 16 scope lock may move dashboards or measures out of the Dec 18 pass.
Anything moved out goes to the deferral log and loses its date.

### 1 · Ops: attendance

| Task                                      | GID              | Due                                          |
| ----------------------------------------- | ---------------- | -------------------------------------------- |
| fct_student_attendance_enrollment_daily   | 1219283938698833 | Jan 15, 2027 (attendance matching)           |
| fct_student_attendance_interventions      | 1214609542482047 | Jan 22, 2027                                 |
| fct_student_attendance_streaks            | 1214609542482049 | Jan 22, 2027                                 |
| fct_family_communications                 | 1214609542482057 | Jan 22, 2027 (contact rate)                  |
| dim_student_attendance_intervention_types | 1219288212249102 | Jan 22, 2027                                 |
| Attendance Dashboard                      | 1213823788919470 | Feb 26, 2027; subtasks Feb 19 (no checklist) |

### 1 · Ops: enrollment and Ops Dashboard

| Task                                                             | GID              | Due                                              |
| ---------------------------------------------------------------- | ---------------- | ------------------------------------------------ |
| Confirm the chronic-absence definition with the ops domain owner | 1219235308564768 | Jan 8, 2027                                      |
| fct_enrollment_targets                                           | 1219288211760729 | Feb 5, 2027                                      |
| fct_student_retention                                            | 1219288212230774 | Feb 12, 2027                                     |
| Privacy reviews: ops and grades/GPA                              | 1219234963895516 | Split: ops Feb 26, 2027; grades/GPA Apr 16, 2027 |
| Check the deferral log for ops                                   | 1219235330710931 | Feb 26, 2027                                     |
| Ops Dashboard (key dashboard)                                    | 1213823788795999 | Feb 26, 2027; subtasks Feb 19                    |

Ops Dashboard checklist: Built Feb 19 · Matches Feb 26 · Privacy Feb 26 ·
Rebuilt Feb 26 · Pilot run Mar 12 · Launched Mar 26.

### 1 · Ops: student recruitment (FRESH)

| Task                                 | GID              | Due                           |
| ------------------------------------ | ---------------- | ----------------------------- |
| fct_student_recruitment_applications | 1214740334762451 | Feb 19, 2027                  |
| FRESH Dashboard (metric set only)    | 1213823831350808 | Feb 19, 2027; subtasks Feb 19 |

The FRESH dashboard itself is not rebuilt or launched this year.

### 1 · Grades/GPA

| Task                                                                         | GID                                | Due                          |
| ---------------------------------------------------------------------------- | ---------------------------------- | ---------------------------- |
| fct_grades_assignments, fct_grades_category, fct_grades_term, fct_grades_gpa | 1214075447593627, …628, …629, …630 | Mar 12, 2027                 |
| fct_gradebook_audit                                                          | 1219288390836604                   | Mar 12, 2027                 |
| fct_grades_gpa_weekly_snapshots                                              | 1219288360755341                   | Mar 12, 2027                 |
| dim_gpa_goals (the GPA goals mart)                                           | 1219288623996935                   | Apr 9, 2027                  |
| Check the deferral log for grades/GPA                                        | 1219235329814415                   | Apr 16, 2027                 |
| Gradebook and GPA Dashboard (key dashboard)                                  | 1213823907731242                   | Apr 16, 2027; subtasks Apr 9 |

The grade cubes are due Mar 26 and the GPA goal measures Apr 9. Checklist: Built
Apr 9 · Matches Apr 16 · Privacy Apr 16 · Rebuilt Apr 16 · Pilot run May 7 ·
Launched May 14.

### 1 · Student dashboards

| Task                                                                       | GID              | Due                           |
| -------------------------------------------------------------------------- | ---------------- | ----------------------------- |
| Remaining student groupings: MTSS tiers, grade-level bands, on-track flags | 1219235117967724 | Apr 16, 2027                  |
| fct_community_service_hours                                                | 1219288287075287 | Apr 30, 2027                  |
| fct_student_promotional_status                                             | 1219288375300673 | Apr 30, 2027                  |
| fct_graduation_pathways                                                    | 1219288375273814 | Apr 30, 2027                  |
| fct_student_data_quality_flags                                             | 1219288360575038 | Apr 30, 2027                  |
| High School Early Warning Dashboard                                        | 1213823922414217 | May 21, 2027; subtasks May 14 |
| Promotional Status Dashboard                                               | 1213823922758693 | May 21, 2027; subtasks May 14 |
| Data Quality Dashboard                                                     | 1213823788719391 | May 21, 2027; subtasks May 14 |
| Check the deferral log for student dashboards                              | 1219235228433154 | May 21, 2027                  |

None of the three has a checklist, so the Jun 4 launch has no task. See "Plan
rows with no Asana task".

### Analyst-built domains

| Section          | Task                                                                                                                                                                      | GID(s)                                                                                                                                                                             | Due          |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| 1 · Zendesk      | fct_support_tickets                                                                                                                                                       | 1214075447593650                                                                                                                                                                   | Dec 18, 2026 |
| 1 · Zendesk      | Zendesk Reporting (key dashboard); subtasks Jan 15                                                                                                                        | 1213823925649913                                                                                                                                                                   | Jan 29, 2027 |
| 1 · Zendesk      | Check the deferral log for Zendesk                                                                                                                                        | 1219235330390759                                                                                                                                                                   | Jan 29, 2027 |
| 1 · Recruitment  | fct_job_candidate_applications, dim_staffing_positions, dim_job_postings, dim_job_candidates, bridge_job_application_subject_preferences, fct_recruitment_calendar_events | 1214075447593646, 1214609542482108, 1219288375396543, 1219288375396736, 1219288287245566, 1219288211520053                                                                         | Feb 12, 2027 |
| 1 · Recruitment  | Recruitment Dashboard (key dashboard); subtasks Feb 26                                                                                                                    | 1213823789062126                                                                                                                                                                   | Mar 12, 2027 |
| 1 · Recruitment  | Check the deferral log for recruitment                                                                                                                                    | 1219235330316655                                                                                                                                                                   | Mar 12, 2027 |
| 1 · Surveys      | fct_survey_submissions, fct_survey_responses, bridge_survey_expectations, dim_surveys, dim_survey_administrations, dim_survey_questions                                   | 1214075447593633, 1214609542482076, 1214075447593636, 1219288623753612, 1219288623761146, 1219288375291945                                                                         | Mar 19, 2027 |
| 1 · Surveys      | School Community Diagnostic; Avg School Community Diagnostic Student Overall Score                                                                                        | 1214073491303442, 1212532285830519                                                                                                                                                 | Apr 2, 2027  |
| 1 · Surveys      | Survey Dashboard (key dashboard), Personalized Survey Links, Manager Survey Report; subtasks Apr 2                                                                        | 1213823922713816, 1213823831344988, 1219235026691519                                                                                                                               | Apr 16, 2027 |
| 1 · Surveys      | Check the deferral log for surveys                                                                                                                                        | 1219235025704263                                                                                                                                                                   | Apr 16, 2027 |
| 1 · Observations | fct_staff_observations, fct_staff_observation_scores, fct_staff_observation_goals, fct_staff_pm_overall_scores, and the six dim_staff_observation_* tasks                 | 1214075610424631, 1214075610424632, 1214075610424633, 1219288211797010, 1219288375340902, 1219288623995318, 1219288390808758, 1219288212162403, 1219288390824783, 1219288623816519 | Apr 16, 2027 |
| 1 · Observations | SchoolMint Grow Dashboard (key dashboard), Coaching Conversation Tool, Teacher Development Dashboard; subtasks Apr 30                                                     | 1213823788976510, 1213823922720520, 1213823789000345                                                                                                                               | May 14, 2027 |
| 1 · Observations | Check the deferral log for observations                                                                                                                                   | 1219235229650596                                                                                                                                                                   | May 14, 2027 |

Key-dashboard checklists for these four domains follow the timeline table:
`Built in Cube`, `Matches within tolerance`, `Privacy review passed` and
`Rebuilt in Tableau on Cube` on the verification row's dates, `Pilot run` on the
pilot date, and `Launched` on the launch date.

### 2 · Enablement, comms and support

| Task                                                                             | GID              | Due                            |
| -------------------------------------------------------------------------------- | ---------------- | ------------------------------ |
| Write the pilot kit: session agenda, homework, feedback log, exit rule           | 1219235025703875 | Nov 6, 2026                    |
| Draft and publish the support boundary; Zendesk intake and response-time targets | 1219235308192152 | Start Oct 30, due Nov 13, 2026 |
| Run two sessions for cohort 2                                                    | 1219235117254041 | Nov 20, 2026                   |
| Communications calendar, office hours, Slack channel norms                       | 1219235229215922 | Nov 20, 2026                   |
| Take over assessments at verification                                            | 1219235329950613 | Dec 18, 2026                   |
| Onboarding plan for mid-year hires and summer PD                                 | 1219235308563407 | Apr 30, 2027                   |

### 3 · Delivery platform

| Task                                                                                                        | GID              | Due                                                                    |
| ----------------------------------------------------------------------------------------------------------- | ---------------- | ---------------------------------------------------------------------- |
| Log every Cube MCP call, no question text, and count queries per user (#5613 phase 1)                       | 1219235026062092 | Nov 20, 2026                                                           |
| Add question text once People Operations rules on retention; start the fortnightly fix list (#5613 phase 2) | 1219235025052124 | Dec 11, 2026                                                           |
| Confirm what an org plugin can carry; build it; test it; roll it out as a beta                              | 1219235308984528 | Jan 15, 2027 (capability check Oct 23, built Dec 18, pilot test Jan 8) |
| Assessments test-question set; automated reruns; a set per later domain                                     | 1219235025202514 | May 14, 2027 (assessments set Dec 4, automated reruns Jan 29)          |
| Cube Validation Skill                                                                                       | 1219100665726624 | Oct 9, 2026 (already set; earlier than the plan)                       |

### 4 · Team capacity

| Task                                                                               | GID              | Due                                                   |
| ---------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------- |
| Run an intro-to-the-marts session for the data team, with a Cube session to follow | 1218341753451039 | Nov 13, 2026 (unassigned; the cube/mart lead runs it) |
| Write mart and cube build standards                                                | 1219235308774595 | Jan 8, 2027                                           |
| Train a second reviewer for mart and cube pull requests                            | 1219235308278780 | Dec 18, 2026 (already set)                            |
| Assign analyst-built domains; track each analyst's first reviewed view             | 1219235118327118 | Start Dec 4, 2026, due May 28, 2027                   |
| Onboard the new analyst into mart and cube work                                    | 1219235118436193 | The hire date, once known                             |

### 5 · Sustainment

Two tasks each feed several milestones with different dates. Each gets one dated
subtask per milestone, and the parent takes the latest date.

| Task                                                                                    | GID              | Subtask dates                                                                                                        |
| --------------------------------------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| Drift rule; legacy-vs-Cube checks; review flag on legacy models with a mart counterpart | 1219235040139127 | Drift rule Jan 15 · review flag Jan 15 · assessments checks Feb 12 · attendance checks Mar 26 · later domains May 28 |
| Guidance release cadence; data-change cadence; ownership after June                     | 1219235228373629 | Guidance cadence Jan 15 · data-change cadence Feb 26 · ownership after June May 28                                   |

### Dependencies outside the sections

Several milestones depend on Oct 6 meeting action items (subtasks of the meeting
task) and on GitHub issue tasks under the `Open Issues` rollups.

| Task                                                                                 | GID                                | Milestone | Due                                                     |
| ------------------------------------------------------------------------------------ | ---------------------------------- | --------- | ------------------------------------------------------- |
| Capacity conversation at the one-on-one on freeing time for the assessments deadline | 1219229568413562                   | M0        | Oct 13, 2026 (already set); rename "Nov 24" to "Dec 18" |
| Send the charter to the steering committee                                           | 1219229601717095                   | M0        | Oct 16, 2026 (already set)                              |
| Design the keep/retire list process                                                  | 1219229568319144                   | M0        | Oct 16, 2026 (already set)                              |
| Decide whether recruitment stays an analyst-built domain                             | 1219229601712738                   | M0        | Oct 16, 2026 (already set)                              |
| Restructure the Asana project (PR #5703)                                             | 1219229601563438                   | M0        | Mark complete                                           |
| Design how metrics no dashboard shows today get added to Cube                        | 1219229615266410                   | M0        | Oct 20, 2026                                            |
| Propose a usefulness success measure (#5613)                                         | 1219229568285693                   | M2.5      | Oct 20, 2026 (already set)                              |
| Name the ops domain owner after a team discussion                                    | 1219229716957017                   | M2.1      | Oct 30, 2026 (already set)                              |
| Tableau access test                                                                  | 1219229488793468                   | M1.1      | Oct 30, 2026 (already set)                              |
| Review the student persistence charter's data needs before ops starts                | 1219229488451407                   | M1.2      | Dec 18, 2026; rename "Nov 30" to "Jan 4"                |
| Build the CI completeness check on Cube YAML                                         | 1219229488659674                   | M4.4      | Dec 18, 2026 (already set)                              |
| #5692 high school state test scores dropped by Cube                                  | 1219119636524318                   | M1.1      | Oct 16, 2026; stays open                                |
| #5573 performance band set columns; #5574 assessment_family                          | 1218941375989436, 1218941760280452 | M1.1      | Oct 23, 2026                                            |
| #4184 administered dates for state assessments                                       | 1215687069915963                   | M1.1      | Nov 6, 2026                                             |
| #5557 assessment pre-aggregation                                                     | 1218896809936221                   | M1.1      | Oct 9, 2026 (already set; plan says Nov 13)             |
| #5668 match the DDI dashboard in the assessment-scores cube                          | 1219084637402304                   | M1.1      | Dec 4, 2026                                             |
| #5236 drain assessment project knowledge into Cube                                   | 1218364802829876                   | M3.1      | Nov 20, 2026                                            |
| #4314 validation-check skill                                                         | 1216249391243519                   | M4.3      | Oct 9, 2026 (already set; earlier than the plan)        |
| #5517 Miami SQL API emulation                                                        | 1218806460401293                   | M1.2      | Complete; no change                                     |

## Measure-level exceptions

These subtasks are due before their dashboard's `Built in Cube` date because a
plan row names them.

| Dashboard            | Measure subtask                                                                       | GID              | Due          |
| -------------------- | ------------------------------------------------------------------------------------- | ---------------- | ------------ |
| APM Dashboard        | Progress to Stretch Growth (LOD)                                                      | 1214073491303390 | Nov 13, 2026 |
| APM Dashboard        | % Lessons Passed (LOD)                                                                | 1214073491303392 | Nov 13, 2026 |
| APM Dashboard        | LOD Time on Task (minutes)                                                            | 1214073491303394 | Nov 13, 2026 |
| Literacy Dashboard   | PM Internal: Starting Words, Cumulative Growth Words, Goal, Met Admin Benchmark Goal… | 1214073491303396 | Nov 20, 2026 |
| Literacy Dashboard   | % Participation (+ Numerator/Denominator variants)                                    | 1214073491303398 | Nov 20, 2026 |
| Attendance Dashboard | % Successful (comm log contact outcome)                                               | 1214073491303426 | Jan 22, 2027 |
| Attendance Dashboard | Intervention Status Required (Avg/Sum/Count)                                          | 1214073491303428 | Jan 22, 2027 |
| Ops Dashboard        | Lunch status, retention and attrition measures                                        | Resolve by name  | Feb 12, 2027 |

## Decisions made on Oct 9

1. **Clear marts V1 for production use** (1219235025270362) moves from Dec 18 to
   the plan's Nov 13.
2. **Privacy reviews: ops and grades/GPA** (1219234963895516) gets two subtasks:
   `Privacy review: ops` (Feb 26) and `Privacy review: grades/GPA` (Apr 16).
   M1.2 depends on the ops subtask and M1.3 on the grades/GPA subtask; the
   parent comes off both milestones and takes Apr 16. Staff Demographic Explorer
   also depends on the parent, which looks like a mislink; that is left for the
   project owner.
3. **Design how metrics no dashboard shows today get added to Cube**
   (1219229615266410) is due Oct 20.
4. **The two meeting action items follow the plan:** the capacity conversation
   (1219229568413562) is renamed from "Nov 24" to "Dec 18", and the persistence
   review (1219229488451407) is due Dec 18 and renamed from "Nov 30" to "Jan 4".
5. **#5692** (1219119636524318) stays open, due Oct 16. The project plan now
   shows it in progress.
6. **Restructure the Asana project** (1219229601563438) is marked complete.

## Plan rows kept outside Asana

Decided Oct 9: these stay in the project plan only.

- Confirm with the assessments domain owner whether Miami falls back to the raw
  goal (Oct 16).
- Name the steering committee (Oct 16); hold the charter conversation (Oct 23);
  send the first biweekly status update (Oct 23).
- Name the grades/GPA, Zendesk, recruitment, surveys and observations domain
  owners (Dec 18), and the student-dashboard owner (Feb 26). M2.1 depends only
  on the ops owner task.
- Publish the ops start date (Jan 4) to ops leaders (Oct 16); confirm ops pilot
  participants (Jan 29).
- Launch the three student dashboards (Jun 4). They have no checklist.
- Midpoint review (Feb 26) and project close (Jun 25) exist only as deferral-log
  review tasks.

## How it gets applied

Once approved, the project lead applies it through the Asana MCP with
`update_tasks` (`due_on`, and `start_on` where shown), at most 50 tasks per
call:

1. Apply the Oct 9 decisions above.
2. Milestones.
3. Dashboard tasks and their checklist subtasks.
4. Measure and dimension subtasks by the rule, then the exceptions.
5. Mart tasks.
6. Every other task in the section tables, and the dependencies outside the
   sections.

A dry run lists every change first, and nothing is deleted. After the run, the
status page's timeline shows the milestones and dashboard target dates.
