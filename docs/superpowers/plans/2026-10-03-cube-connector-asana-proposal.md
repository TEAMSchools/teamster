# Asana Restructure Proposal: Data Marts + Semantic Layer

Refs [#5673](https://github.com/TEAMSchools/teamster/issues/5673). Builds on the
[gap catalog](2026-10-02-cube-gap-catalog.md).

This is a proposal for the Asana project's owner to approve. Nothing in Asana
changes until it is approved. Dates come from the SY26-27 project plan and go in
only after that plan is approved too.

## What changes

- Sections are grouped by the plan's five workstreams. Asana has no nested
  sections, so a numeric prefix does the nesting: the per-domain sections stay,
  renamed to sit under workstream 1 (`1 · Assessments`, `1 · Grades/GPA`).
- Each plan milestone gets an Asana milestone task.
- Work outside workstream 1 (enablement, the plugin, team capacity, sustainment)
  gets tasks. Most of it has none today.
- Key-dashboard tasks get the same six done-gate subtasks.
- Per-dashboard tasks are backfilled and corrected from the gap catalog.
- Nothing is deleted. Completed tasks keep their history, and the `Open Issues`
  rollups (one subtask per GitHub issue) stay as they are.

## Roles

Owners are named by role here. The internal project plan maps roles to people.

| Role                 | Owns                                                |
| -------------------- | --------------------------------------------------- |
| Project lead         | Governance; workstream 3 (platform); 4 (capacity)   |
| Cube/mart lead       | Workstream 1 (domain build, permissioning)          |
| Enablement lead      | Workstream 2 (enablement, communications, support)  |
| Engineering reviewer | Code approval; clearing marts V1 for production use |
| Analysts             | The four analyst-built domains                      |
| Sustainment owner    | Workstream 5; not yet decided                       |

## Current state (2026-10-03)

The project has 18 sections and 152 tasks: 64 complete, 88 open.

- `Untitled section`: 11 tasks, all complete (spring and summer setup work).
- `Training & Pilots`: 1 open task (intro-to-the-marts session).
- `Platform & Tooling`: 1 rollup with 6 GitHub issues.
- `Access & Security`: 3 complete tasks and 1 rollup with 12 GitHub issues.
- `Conformed Dimensions`: 5 complete cubes and 1 rollup.
- 13 domain sections. Each mixes three kinds of task: planned cube names
  (`attendance_interventions`), measure names
  (`assessments.dibels_pm_mastery_rate`), and per-dashboard tasks with subtasks.

## Proposed sections

Renames keep the section's GID, so no task moves unless the table says so.

| Proposed section                        | From (current GID)                                           | Owner role      |
| --------------------------------------- | ------------------------------------------------------------ | --------------- |
| `0 · Governance`                        | New                                                          | Project lead    |
| `1 · Shared dimensions and groupings`   | Rename `Conformed Dimensions` (1214075447592585)             | Cube/mart lead  |
| `1 · Permissioning`                     | Rename `Access & Security` (1216570201249194)                | Cube/mart lead  |
| `1 · Assessments`                       | Rename `Assessments` (1214075610424617)                      | Cube/mart lead  |
| `1 · Ops: attendance`                   | Rename `Attendance` (1214075610424635)                       | Cube/mart lead  |
| `1 · Ops: enrollment and Ops Dashboard` | Rename `Students` (1214075447592591)                         | Cube/mart lead  |
| `1 · Student dashboards`                | New; receives 3 dashboard tasks from `Students`              | Cube/mart lead  |
| `1 · Grades/GPA`                        | Rename `Grades` (1214075447593626)                           | Cube/mart lead  |
| `1 · Zendesk`                           | Rename `Support` (1214073246940447)                          | Analysts        |
| `1 · Recruitment`                       | Rename `Talent` (1214075447593645)                           | Analysts        |
| `1 · Surveys`                           | Rename `Surveys` (1214075447593632)                          | Analysts        |
| `1 · Observations`                      | Rename `Observations` (1214075610424625)                     | Analysts        |
| `1 · Stretch: Behavior`                 | Rename `Behavior` (1214075610424641)                         | Cube/mart lead  |
| `1 · Stretch: Staff`                    | Rename `Staff` (1214075447592604)                            | Cube/mart lead  |
| `1 · Stretch: Postsecondary`            | Rename `Postsecondary` (1214075447593641)                    | Cube/mart lead  |
| `1 · Stretch: Student recruitment`      | Rename `Student Recruitment & Enrollment` (1214073246940448) | Cube/mart lead  |
| `1 · Stretch: Stipends and cert`        | Rename `Stipends and Cert` (1214073491303334)                | Cube/mart lead  |
| `2 · Enablement, comms and support`     | Rename `Training & Pilots` (1219071017452217)                | Enablement lead |
| `3 · Delivery platform`                 | Rename `Platform & Tooling` (1219071017452190)               | Project lead    |
| `4 · Team capacity`                     | New                                                          | Project lead    |
| `5 · Sustainment`                       | New                                                          | Not yet decided |
| `Parking lot and outside the core set`  | New                                                          | Project lead    |
| `Archive: before SY26-27`               | Rename `Untitled section` (1213735218595735)                 | Project lead    |

The stretch sections keep their tasks as they are until the midpoint review on
the stretch domains. A domain that is not picked stays in its stretch section.

### Task moves

| Task (GID)                                             | From              | To                                     | Why                                    |
| ------------------------------------------------------ | ----------------- | -------------------------------------- | -------------------------------------- |
| High School Early Warning Dashboard (1213823922414217) | Students          | `1 · Student dashboards`               | Needs ops and grades first             |
| Promotional Status Dashboard (1213823922758693)        | Students          | `1 · Student dashboards`               | Needs ops and grades first             |
| Data Quality Dashboard (1213823788719391)              | Students          | `1 · Student dashboards`               | Same group in the plan                 |
| Newark Home Instruction Tracker (1213823922719414)     | Students          | `Parking lot and outside the core set` | Not a verified launch-page dashboard   |
| Miami Instructional Rubrics (1213823907851094)         | Observations      | `Parking lot and outside the core set` | Not a verified launch-page dashboard   |
| Intro-to-the-marts session (1218341753451039)          | Training & Pilots | `4 · Team capacity`                    | Training the data team is workstream 4 |

## Size of each section

From the gap catalog. "Buildable" measure rows exclude the 36 Tableau-only
calculations the catalog marks `workbook-only`. Cube covers 59 of the 347
buildable rows today (about 17%).

| Section                                 | Dashboards | Buildable rows | In Cube | Mart ready | Mart missing |
| --------------------------------------- | ---------: | -------------: | ------: | ---------: | -----------: |
| `1 · Assessments`                       |          7 |             96 |      30 |         36 |           30 |
| `1 · Ops: attendance`                   |          1 |             18 |       9 |          5 |            4 |
| `1 · Ops: enrollment and Ops Dashboard` |          1 |             16 |       6 |          0 |           10 |
| `1 · Student dashboards`                |          3 |             42 |       8 |         13 |           21 |
| `1 · Grades/GPA`                        |          1 |             20 |       0 |          8 |           12 |
| `1 · Zendesk`                           |          1 |              4 |       0 |          4 |            0 |
| `1 · Recruitment`                       |          1 |             14 |       0 |         11 |            3 |
| `1 · Surveys`                           |          3 |             18 |       0 |         17 |            1 |
| `1 · Observations`                      |          4 |             39 |       0 |         27 |           12 |
| `1 · Stretch: Behavior`                 |          1 |             19 |       0 |          7 |           12 |
| `1 · Stretch: Staff`                    |          4 |             23 |       6 |         10 |            7 |
| `1 · Stretch: Postsecondary`            |          1 |             12 |       0 |          1 |           11 |
| `1 · Stretch: Student recruitment`      |          1 |              9 |       0 |          0 |            9 |
| `1 · Stretch: Stipends and cert`        |          2 |             17 |       0 |          3 |           14 |
| **Total**                               |     **31** |        **347** |  **59** |    **142** |      **146** |

The priority sections (assessments, both ops sections, student dashboards and
grades/GPA) hold 192 rows, 55% of the total. The four analyst-built sections add
75 rows, which brings the total to 77%. The plan's coverage target of 75% rests
on those two groups. Observations includes the Leader PM Dashboard's 3 rows;
that dashboard moved to Lattice and is out of scope.

## Milestone tasks to add

One Asana milestone per plan milestone, in the section shown. Target dates are
the plan's proposed dates.

| Section                                 | Milestone                                                         | Owner role                              | Target               |
| --------------------------------------- | ----------------------------------------------------------------- | --------------------------------------- | -------------------- |
| `0 · Governance`                        | M0 Plan approved                                                  | Project lead                            | Oct 16, 2026         |
| `1 · Assessments`                       | M1.1 Assessment cube confirmed, DDI Suite rebuilt                 | Cube/mart lead                          | Nov 24, 2026         |
| `1 · Ops: enrollment and Ops Dashboard` | M1.2 Ops verified                                                 | Cube/mart lead                          | Jan 29, 2027         |
| `1 · Grades/GPA`                        | M1.3 Grades/GPA verified                                          | Cube/mart lead                          | Mar 19, 2027         |
| `1 · Student dashboards`                | M1.4 Student dashboards covered                                   | Cube/mart lead                          | May 7, 2027          |
| `1 · Observations`                      | M1.5 Analyst-built domains verified                               | Cube/mart lead                          | May 14, 2027         |
| `0 · Governance`                        | M1.6 Stretch-domain decision                                      | Cube/mart lead                          | Feb 26, 2027         |
| `1 · Permissioning`                     | M1.7 Permissioning ready for each launch                          | Cube/mart lead                          | Jan 15, 2027         |
| `1 · Assessments`                       | M1.8 Assessments follow-on: growth and DIBELS progress monitoring | Cube/mart lead                          | May 28, 2027         |
| `2 · Enablement, comms and support`     | M2.1 Domain owners named                                          | Enablement lead                         | Feb 26, 2027         |
| `2 · Enablement, comms and support`     | M2.2 Support boundary published                                   | Enablement lead                         | Nov 13, 2026         |
| `2 · Enablement, comms and support`     | M2.3 Standard pilot kit                                           | Enablement lead                         | Nov 6, 2026          |
| `2 · Enablement, comms and support`     | M2.4 Cohort 2 onboarded                                           | Project lead                            | Nov 20, 2026         |
| `2 · Enablement, comms and support`     | M2.5 Launch package per domain                                    | Enablement lead                         | May 28, 2027         |
| `2 · Enablement, comms and support`     | M2.6 Org-wide engagement plan                                     | Enablement lead                         | Nov 20, 2026         |
| `2 · Enablement, comms and support`     | M2.7 Ongoing onboarding cycle                                     | Enablement lead                         | Apr 30, 2027         |
| `3 · Delivery platform`                 | M3.1 Org plugin replaces project-knowledge delivery               | Project lead                            | Jan 15, 2027         |
| `3 · Delivery platform`                 | M3.2 Usage logging live                                           | Project lead                            | Dec 11, 2026         |
| `3 · Delivery platform`                 | M3.3 Test-question sets                                           | Project lead                            | May 14, 2027         |
| `4 · Team capacity`                     | M4.1 Build standards written                                      | Cube/mart lead                          | Dec 11, 2026         |
| `4 · Team capacity`                     | M4.2 Data team trained                                            | Engineering reviewer                    | Nov 13, 2026         |
| `4 · Team capacity`                     | M4.3 Cube/mart creation skill shipped                             | Cube/mart lead                          | Dec 18, 2026         |
| `4 · Team capacity`                     | M4.4 Review path that scales                                      | Engineering reviewer                    | Dec 18, 2026         |
| `4 · Team capacity`                     | M4.5 Every analyst ships one reviewed mart or cube                | Project lead                            | May 28, 2027         |
| `4 · Team capacity`                     | M4.6 New analyst onboarded into mart and cube work                | Project lead (stands in until the hire) | Depends on hire date |
| `5 · Sustainment`                       | M5.1 Drift rule adopted                                           | Not yet decided                         | Dec 11, 2026         |
| `5 · Sustainment`                       | M5.2 Legacy-vs-Cube checks running                                | Not yet decided                         | May 28, 2027         |
| `5 · Sustainment`                       | M5.3 Guidance release cadence                                     | Not yet decided                         | Jan 15, 2027         |
| `5 · Sustainment`                       | M5.4 Data-change cadence agreed                                   | Not yet decided                         | Feb 26, 2027         |
| `5 · Sustainment`                       | M5.5 Ownership after June agreed                                  | Not yet decided                         | May 28, 2027         |

The assessment dates reflect a hard deadline: the assessment cube is confirmed,
and the DDI Suite rebuilt on Cube, by Tuesday, Nov 24, 2026, the last working
day before Thanksgiving break. Ops then starts Nov 30.

If workstream 5 folds into the others (the plan recommends it), M5.1 and M5.2
move to `4 · Team capacity`, M5.4 and M5.5 to workstream 1, and M5.3 to
workstream 2.

## Tasks to add or link

Where an Asana task or GitHub issue already covers the work, the plan links it
to the milestone as a dependency instead of creating a duplicate.

### Workstream 1

| Task                                                                                               | Milestone | Owner role                                                                                            | Existing item                         |
| -------------------------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------- |
| Fix high school state test scores that Cube drops                                                  | M1.1      | Cube/mart lead                                                                                        | #5692 (Assessments `Open Issues`)     |
| Test that a Tableau dashboard reading from Cube keeps each viewer's access                         | M1.1      | Engineering reviewer (pending decision; assumed for planning)                                         | None                                  |
| Band numbers and band set columns for state and vendor tests                                       | M1.1      | Cube/mart lead                                                                                        | #5573, #5574                          |
| Internal assessment goals in Cube (`dim_assessment_goals`)                                         | M1.1      | Cube/mart lead                                                                                        | None                                  |
| State test goals and SAT/ACT/PSAT goals in Cube                                                    | M1.1      | Cube/mart lead                                                                                        | None                                  |
| Connect CARAT's student-scoped scores fact to Cube                                                 | M1.1      | Cube/mart lead                                                                                        | `assessment_scores_student_scoped`    |
| NJ student tier / tutoring buckets and 504 status                                                  | M1.1      | Cube/mart lead                                                                                        | None                                  |
| Administered dates for state tests; governed administrations count                                 | M1.1      | Cube/mart lead                                                                                        | #4184                                 |
| Match the DDI dashboard in Cube; fix the pre-aggregation                                           | M1.1      | Cube/mart lead; engineering reviewer for the pre-aggregation (pending decision; assumed for planning) | #5668, #5557; DDI Suite task          |
| Clear marts V1 for production use                                                                  | M1.1      | Engineering reviewer                                                                                  | Intro-to-the-marts task notes         |
| Matching sign-off and privacy review: assessments                                                  | M1.1      | Cube/mart lead                                                                                        | None                                  |
| Rebuild the DDI Suite (8 dashboards) in Tableau on Cube; the rebuild doubles as the matching check | M1.1      | Project lead                                                                                          | DDI Suite task                        |
| Confirm the chronic-absence definition with the ops domain owner                                   | M1.2      | Cube/mart lead                                                                                        | None                                  |
| Attendance interventions, contact rate, intervention completion, streaks                           | M1.2      | Cube/mart lead                                                                                        | 4 open tasks in `Attendance`          |
| Enrollment and enrollment-target marts for the Ops Dashboard                                       | M1.2      | Cube/mart lead                                                                                        | Ops Dashboard task                    |
| Fix the open Miami access gaps                                                                     | M1.2      | Cube/mart lead                                                                                        | #5517, #5524                          |
| Lunch status and retention/attrition measures                                                      | M1.2      | Cube/mart lead                                                                                        | Ops Dashboard task                    |
| Rebuild the Ops Dashboard in Tableau on Cube                                                       | M1.2      | Analysts                                                                                              | Ops Dashboard task                    |
| Course-grade and GPA cubes on the existing grade marts                                             | M1.3      | Cube/mart lead                                                                                        | 4 cube tasks in `Grades`              |
| GPA goals mart; GPA bands and cusp bands                                                           | M1.3      | Cube/mart lead                                                                                        | 2 GPA on-track measure tasks          |
| Rebuild the Academic & Gradebook Health Suite in Tableau on Cube                                   | M1.3      | Analysts                                                                                              | Gradebook and GPA Dashboard task      |
| Remaining student groupings: MTSS tiers, grade-level bands, on-track flags                         | M1.4      | Cube/mart lead                                                                                        | None                                  |
| Zendesk, recruitment, surveys and observations: cubes, views, matching, privacy review             | M1.5      | Analysts                                                                                              | Cube and measure tasks per section    |
| Size the stretch domains from the gap catalog                                                      | M1.6      | Cube/mart lead                                                                                        | None                                  |
| Triage the 12 open access and security issues against launch dates                                 | M1.7      | Cube/mart lead                                                                                        | Access & Security `Open Issues`       |
| Check whether shared Claude artifacts respect each viewer's access; set a sharing rule             | M1.7      | Cube/mart lead                                                                                        | None                                  |
| Small-cell suppression decision                                                                    | M1.7      | Cube/mart lead                                                                                        | #4237                                 |
| i-Ready growth, lessons passed, time on task; DIBELS PM mastery and completion                     | M1.8      | Cube/mart lead                                                                                        | 5 open measure tasks in `Assessments` |

### Workstreams 2 to 5 and governance

| Task                                                                                       | Milestone  | Owner role           |
| ------------------------------------------------------------------------------------------ | ---------- | -------------------- |
| Send the revised charter; hold the sign-off conversation                                   | M0         | Project lead         |
| Approve this proposal; apply it                                                            | M0         | Project lead         |
| Name domain owners: assessments and ops; then the rest                                     | M2.1       | Enablement lead      |
| Draft and publish the support boundary; Zendesk intake and response-time targets           | M2.2       | Enablement lead      |
| Write the pilot kit: session agenda, homework, feedback log, exit rule                     | M2.3       | Enablement lead      |
| Run two sessions for cohort 2                                                              | M2.4       | Project lead         |
| One launch task per domain (pilot, help article, training, announcement)                   | M2.5       | Enablement lead      |
| Communications calendar, office hours, Slack channel norms                                 | M2.6       | Enablement lead      |
| Onboarding plan for mid-year hires and summer PD                                           | M2.7       | Enablement lead      |
| Confirm what an org plugin can carry; build it; test it; roll it out                       | M3.1       | Project lead         |
| Move assessment project knowledge into Cube descriptions and skills (#5236)                | M3.1       | Project lead         |
| Per-user query counts for the adoption measure                                             | M3.2       | Project lead         |
| Assessments test-question set; automated reruns; a set per later domain                    | M3.3       | Project lead         |
| Write mart and cube build standards                                                        | M4.1       | Cube/mart lead       |
| Intro-to-the-marts session, then the Cube session (existing task)                          | M4.2       | Engineering reviewer |
| Finish the cube/mart skill with the validation checks (#4314)                              | M4.3       | Cube/mart lead       |
| Train a second reviewer for mart and cube pull requests                                    | M4.4       | Engineering reviewer |
| Assign analyst-built domains; track each analyst's first merged mart or cube               | M4.5       | Project lead         |
| Onboard the new analyst into mart and cube work; the project lead stands in until the hire | M4.6       | Project lead         |
| Drift rule; legacy-vs-Cube checks; review flag on legacy models with a mart counterpart    | M5.1, M5.2 | Not yet decided      |
| Guidance release cadence; data-change cadence; ownership after June                        | M5.3–M5.5  | Not yet decided      |

The analysis-limits skill goes in `Parking lot and outside the core set`, with
no date.

## Key-dashboard tasks

Each domain has one key dashboard. Its task gets six done-gate subtasks: Built
in Cube, Matches within tolerance, Privacy review passed, Rebuilt in Tableau on
Cube, Pilot run, Launched. Other dashboard tasks keep their current subtasks.

| Section                                 | Key dashboard task (GID)                       |
| --------------------------------------- | ---------------------------------------------- |
| `1 · Assessments`                       | DDI Suite (1213823831345180)                   |
| `1 · Ops: enrollment and Ops Dashboard` | Ops Dashboard (1213823788795999)               |
| `1 · Grades/GPA`                        | Gradebook and GPA Dashboard (1213823907731242) |
| `1 · Zendesk`                           | Zendesk Reporting (1213823925649913)           |
| `1 · Recruitment`                       | Recruitment Dashboard (1213823789062126)       |
| `1 · Surveys`                           | Survey Dashboard (1213823922713816)            |
| `1 · Observations`                      | SchoolMint Grow Dashboard (1213823788976510)   |
| `1 · Stretch: Behavior`                 | OKRTS Dashboard (1213823831158360), if picked  |

## Corrections from the gap catalog

These come from the catalog's
[Asana reconciliation](2026-10-02-cube-gap-catalog.md#asana-reconciliation-report-only).
The domain files hold the exact values to backfill.

- Add a task for the Manager Survey Report in `1 · Surveys`. It is a verified
  dashboard with no task.
- Do not add a task for the Leader PM Dashboard. Its source model is disabled
  and the work moved to Lattice.
- Backfill the workbook LUID and `rpt_` models on the four tasks with empty
  notes: Staff Roster, Staff Demographic Explorer, Attrition Dashboard, Finance
  Tools.
- Gradebook and GPA Dashboard: replace the stale workbook LUID and `rpt_` list.
  The live workbook reads `rpt_tableau__gradebook_audit`,
  `rpt_tableau__student_course_grades`, `rpt_tableau__gpa_cumulative_year`,
  `rpt_tableau__gpa_goals` and `rpt_tableau__gpa_goal_progress`.
- NJ Certification Dashboard: remove the `rpt_tableau__staff_roster` claim as
  the cert source. Note that the cert content comes from a Google Sheet outside
  dbt.
- KIPP Forward Data Suite: add `rpt_tableau__kfwd_aid_report` and
  `rpt_gsheets__kfwd_rem_roster`.
- Recruitment Dashboard: the datasource is `rpt_tableau__seat_tracker_snapshot`,
  not `rpt_tableau__seat_tracker`.
- High School Early Warning: `rpt_tableau__grad_plan_tracking` does not exist.
  Remove it.
- Personalized Survey Links: the relation is `rpt_tableau__survey_links`, not
  `survey_completion`.
- Zendesk Reporting: blocker `fct_tableau_usage` should be
  `fct_support_tickets`, which exists.
- Rename stale blockers across tasks: `fct_observations` to
  `fct_staff_observations`; `fct_incidents` and `fct_behaviors` to
  `fct_behavioral_incidents` and `fct_behavioral_consequences`;
  `fct_course_grades` to `fct_grades_term` and `fct_grades_gpa`;
  `dim_observation_rubrics` to `dim_staff_observation_rubrics`. Remove
  `dim_students`, `dim_locations` and `dim_terms` as blockers; they exist.

## Decisions for the project owner

- [ ] Workstream prefixes on section names. The alternative is a `Workstream`
      single-select custom field, which keeps current section names but makes
      the grouping invisible in the list view.
- [ ] Split `Students` into `1 · Ops: enrollment and Ops Dashboard` and
      `1 · Student dashboards`.
- [ ] Add milestone tasks with the plan's dates, once the plan is approved.
- [ ] Done-gate subtasks on key-dashboard tasks only.
- [ ] Keep measure tasks as tasks, linked to their milestone. The alternative is
      to turn them into subtasks of their dashboard task.
- [ ] Rename `Untitled section` to `Archive: before SY26-27`.
- [ ] Apply the corrections from the gap catalog.

## How it gets applied

Once approved, the project lead applies it through the Asana MCP in this order:
rename sections, add the new sections, move the six tasks, create milestone
tasks, create or link the remaining tasks, then backfill and correct notes. No
task is deleted. Dates go in after the project plan is approved.
