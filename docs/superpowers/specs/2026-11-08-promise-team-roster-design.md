# Promise Team roster extract and Claude skill — design

Issue: #6306. Follow-on: move behavior, GPA and the communication log into Cube
(no issue yet).

## Intent

Promise Teams are the intervention teams at each school. They work like MTSS
(Multi-Tiered System of Supports) teams, with most of their time on attendance
and behavior. One person runs the teams at both Newark high schools, KIPP Newark
Lab High School and KIPP Newark Collegiate Academy (NCA), and has asked for
better access to the data the teams use each week.

Today the Lab team keeps a Google Sheet. Someone pastes attendance, discipline
and GPA figures into a new tab each week, and plan leads type call notes into
cells next to each student. A Paterson elementary school has a Claude artifact
for the same work that runs on DeansList exports uploaded by hand each week and
logs contacts inside the artifact.

The outcome: the person who runs the Newark teams opens Claude on Monday, says
"score the week", and gets the week's flags, the meeting agenda and call prep
for each school, from data that refreshed overnight. Nothing is uploaded. Every
family contact is logged in DeansList and nowhere else.

## Goals

- One nightly Google Sheet per Newark high school with one row per enrolled
  student, holding every figure the Lab tracker's weekly tabs hold today plus
  the latest DeansList communication log entry per student.
- A weekly snapshot tab so week-over-week movement does not need date-stamped
  copies.
- Promise Team membership and tier read from DeansList rosters, so the list is
  reportable and survives staff turnover.
- A Claude skill that reads the sheet and Cube, runs the weekly protocol, and
  writes nothing except text for a human to paste into DeansList.
- Drive sharing on each report sheet is the access boundary, with the school
  filter set on each school's Connected Sheets extract. The NCA sheet shows no
  Lab students.

## Non-goals

- Caseload-level access (a plan lead seeing only their own students). Drive
  sharing is school-level.
- Behavior, GPA or communication log in Cube. That is the follow-on.
- Other regions or the Newark middle schools. The model takes a school filter,
  so adding a school is a new exposure, not a new model.
- Replacing the Tableau attendance and chronic absenteeism dashboards.
- A fidelity ("was the plan run this week") field. The communication log stands
  in for it.

## Anti-goals

- Any place other than DeansList where a family contact can be recorded: no
  notes column in the sheet, no notes field in the skill, no artifact storage.
- A manual export or upload step anywhere in the weekly rhythm.
- A sheet that drifts from the Tableau dashboards. Every figure comes from the
  same marts the dashboards read.

## Constraints

- No student PII in the issue, the PR, commits or agent output. The sheet itself
  holds PII and is shared one person at a time by the Data Team.
- The extract reads marts (`dbt-architecture` A2). Where no mart covers an
  entity, the spec names it and the PR links an issue for the missing mart.
- DeansList behavior rows for this school year: about 5.9 million for Newark.
  Nothing in the design moves raw behavior rows anywhere.
- The `rpt_gsheets__*` pattern: a kipptaf model under
  `models/extracts/google/sheets/`, contract enforced, a uniqueness test, and an
  exposure in `models/exposures/google-sheets.yml` with `kinds: [googlesheets]`.
  Extraction is a Connected Sheets schedule on the source sheet; the exposure
  only tracks it.

## What exists today

Verified in the warehouse on 2026-11-08.

- Marts: `fct_student_attendance_enrollment_daily` (daily presence, `is_tardy`,
  `is_ontime`, `is_absent`), `fct_student_attendance_enrollment_periods` (ADA
  tier, `is_chronically_absent`, `is_truant` as of a period),
  `fct_behavioral_incidents` and `fct_behavioral_consequences` (referrals,
  suspensions), `fct_family_communications` (the DeansList communication log:
  method, topic, reason, outcome, notes, timestamp, `is_attendance_call`),
  `fct_student_attendance_interventions` (required attendance contacts by
  absence threshold), `fct_grades_gpa` (term and cumulative GPA, credits earned
  and attempted, failing count), `dim_student_enrollments`, `dim_students`,
  `dim_student_iep_status`, `dim_student_ell_status`.
- DeansList rosters already carry a tier and a focus. Newark Lab has 12 active
  "Intervention Group" rosters named `RTI Attendance - Tier 1` through
  `RTI Math - Tier 3`, with `rti_tier` and `rti_focus_id` set. Tier 1 holds the
  whole school; Tier 2 and Tier 3 are empty. NCA has no RTI rosters yet.
  Paterson has no Intervention Group rosters at all.
- Roster assignments reach the warehouse through
  `int_deanslist__roster_assignments` (a DeansList source intermediate). No mart
  covers roster membership.
- Student custom fields in Newark DeansList are all mechanical (asset tags,
  lockers, graduation date, community service hours). None hold plan state.
- The Lab tracker already consumes `rpt_gsheets__gpa_roster` as its "GPA Feed"
  tab, so the team already trusts a nightly extract.
- The NCA tracker is a different tool from Lab's: a case-management sheet with
  81 focus students, each carrying a case manager, a computed primary risk and
  priority letter, a primary barrier, an intervention, this week's action, a due
  date, evidence, a Promise Status (Active, Monitor, Exit) and a level-up
  request to leadership. Risk indicators (GPA under 2.5, chronic absence, 2 or
  more suspensions, 5 or more referrals, ADA under 75%) are computed in-sheet
  from pasted DATA tabs; referrals and suspensions are matched by student name.
  A Student History Archive keeps entry and exit baselines. Many cells read
  "Needs Update".
- The communication log at the two high schools is mostly daily absence-reason
  notes (`Att: Unknown`, `Att: Illness`, `Att: Other`, one per absence), plus
  mass messages (the same topic text sent to 20 or more students on one day),
  the tiered `Chronic Absence: N` letters, and one-to-one case work logged under
  ordinary attendance reasons. Call type is blank on about 70% of Lab entries;
  call status (Completed, Left Message, Unreachable) is populated. No reason
  marks a Promise Team contact.

## Approaches

1. **One extract per school plus a Claude skill (chosen).** A new
   `rpt_gsheets__promise_team_roster` over the marts, one exposure per school,
   and a Claude skill that reads the sheet and Cube. About 2 days for the
   extract and 1 day for the skill. Chosen because it reuses what is built,
   matches how the team already consumes data, and gives the stakeholder the
   Paterson experience without uploads.
2. **Cube first.** Add behavior, communication log and GPA cubes and views, and
   let the Claude Cube connector do everything with row-level security. The
   right end state, about 2 to 3 weeks, and it needs the 5.9 million behavior
   rows pre-aggregated to student-week. Deferred to the follow-on.
3. **Fork the Paterson hub for Newark.** Swap uploads for the extract and delete
   in-hub contact logging. Rejected: the hub is hand-written JavaScript bound to
   one browser's storage with no access control, and it keeps a second UI to
   maintain.
4. **Monday brief only.** A scheduled Claude routine posts flags to Slack or a
   Doc with no interactive skill. Kept as a possible add-on to approach 1, not a
   replacement, because the team asked for the meeting-time tools.

## Decisions

### Where Promise Team state lives

DeansList's own RTI rosters. A student on a Promise Team plan is a member of
`RTI Attendance - Tier 2`, `RTI Attendance - Tier 3`, `RTI Behavior - Tier 2` or
`RTI Behavior - Tier 3` at their school. Tier and focus come from the roster's
`rti_tier` and roster name, not from a custom field. Moving a student between
rosters is the tier change; the weekly snapshot records it.

Plan state beyond membership and tier lives in a weekly Google Form, not in
DeansList custom fields and not in the sheet. NCA already records 8 plan fields
per student each week; the form carries the same ones: Promise Status (Active,
Monitor, Exit), primary barrier, intervention, this week's action, due date,
evidence from last week, level-up needed and level-up request, plus a case
manager dropdown of the school's staff. The case manager is the dropdown value
on the latest response, not the respondent, so a dean can log a week for a
student without becoming the owner. The student and the current case manager are
prefilled through the form's prefilled-link feature; the roster sheet and the
skill carry a "Log this week" link per student with the student number and
latest case manager filled in, so no one types a name, and a changed case
manager carries forward from the next morning's links. One form per school,
frozen once the roster ships, because the prefilled links depend on the question
ids; adding a dropdown option for a new staff member does not change them. Setup
seeds the first links from each school's current assignment list (Lab's
"Assigned Teammate" column), since no response exists yet. About 100 to 120
submissions a week across both schools.

Responses land in a Data-Team-owned linked sheet and reach the warehouse as
`stg_google_sheets__promise_team__weekly_updates`, following the Google Form
source steps in `docs/guides/google-sheets.md`. Responses are append-only, so
plan history comes free. The form is for internal case notes only; its first
line says family contacts go in DeansList.

Prerequisite outside this repo: a DeansList administrator creates the RTI roster
set at NCA (Lab already has one) and the Promise Team moves its current list
into the Tier 2 and Tier 3 attendance and behavior rosters.

### What counts as a Promise Team contact

Every communication log entry for a student while on a Tier 2 or 3 roster
counts, except mass messages. A mass message is an entry whose user, date and
topic text match 10 or more students' entries that day. Daily absence-reason
notes count. Letters count. No new log type, no topic convention, no filter on
who logged it. `is_flag_no_contact_10_days`, `n_contacts_ytd`, the no-contact
list and contact fidelity all use this definition. The one-pager and the
contacts tab show every non-mass entry and mark the mass ones out.

### The roster model

`rpt_gsheets__promise_team_roster`, kipptaf, `models/extracts/google/sheets/`.
Grain: one row per currently enrolled student per school, Newark high schools
only in v1 (`school_level = 'HS'`, `region = 'Newark'`). A student who transfers
between Lab and NCA mid-year appears once, at the current school. Uniqueness
test on `student_number` and `school`.

Figures are year to date unless a column name says otherwise. Where the
tracker's pasted figure and the mart disagree, the mart is right; the acceptance
spot-check explains the difference, it does not fail on it.

Columns, grouped by source:

- Identity and context: `academic_year`, `region`, `school`, `school_name`,
  `student_number`, `student_name`, `grade_level`, `advisory` or `team`,
  `iep_status`, `is_504`, `ml_status`, `enroll_status`.
- Promise Team state (rosters): `promise_team_tier` (2, 3 or null),
  `promise_team_focus` (`Attendance`, `Behavior`, both, or null),
  `promise_team_roster_names`, `weeks_on_roster` (from the roster snapshot).
- Plan (latest weekly form response): `case_manager`, `promise_status`,
  `primary_barrier`, `intervention`, `this_week_action`, `action_due_date`,
  `last_form_date`, `is_level_up_requested`, `weekly_form_url` (the prefilled
  link for this student).
- Attendance (daily and periods marts, year to date): `ada`, `ontime_rate`,
  `n_days_absent`, `n_days_absent_unexcused`, `n_days_tardy`, `ada_tier`,
  `is_chronically_absent`, `is_truant`, `days_to_90_pct` (membership days the
  student must attend without an absence to reach 90% ADA; null when already at
  or above), `n_absences_to_credit_loss` (18 minus
  `n_absences_y1_running_non_susp_no_tardy`, floor 0; both values come from the
  promotion policy, below).
- Discipline (behavioral marts, year to date unless named): `n_referrals` (all
  DeansList incidents), `n_referrals_tier_2_plus` (`category_tier` in T2 and
  T3), `n_referrals_last_7_days`, `n_referrals_last_14_days`,
  `n_referrals_last_30_days`, `last_referral_date`, `last_referral_tier`,
  `last_referral_infraction`, `last_referral_staff_name`,
  `top_referral_category`, `n_iss_events`, `n_iss_days`, `n_oss_events`,
  `n_oss_days` (DeansList consequences, the same source as
  `rpt_gsheets__suspensions`, not attendance codes), `last_suspension_date`,
  `last_suspension_type`, `suspension_return_date` (the consequence end date
  when it is today or later, so the roster shows who is out now and who returns
  this week), `is_referral_spike` (2 or more referrals in the last 7 days).
- Grades (`fct_grades_gpa`, current term): `gpa_term`, `gpa_ytd`,
  `cumulative_gpa`, `n_failing_ytd`, `credit_hours_earned_cumulative`,
  `credit_hours_attempted_cumulative`. The GPA the tracker pastes each week is
  term GPA, so `gpa_term` drives the GPA flag.
- Promotion status (`int_students__promotional_status`, current term; a domain
  intermediate, no mart covers it): `attendance_status`,
  `attendance_status_hs_detail`, `academic_status`, `overall_status`,
  `n_absences_y1_running_non_susp_no_tardy`, `projected_credits_cum`. This is
  the tracker's "credit loss" column. The rule is the Newark high school
  promotion policy, maintained by regional leaders in the promo status policies
  sheet (`stg_google_sheets__reporting__promo_status_policies`), not restated
  here: absences year to date excluding suspension days and tardies, Off-Track
  "Already reached threshold" at 18, "Approaching threshold" at 4.5 in Q1, 9 in
  Q2, 13.5 in Q3 and 18 in Q4; academic Off-Track below 25, 50, 85 and 120
  projected cumulative credits by grade. The roster reads the computed status
  and never re-implements it. How credits are earned back after the threshold is
  a school process and stays an open question.
- Contact (communication log, year to date): `last_contact_date`,
  `last_contact_method`, `last_contact_reason`, `last_contact_outcome`,
  `last_contact_staff_name`, `days_since_last_contact`, `n_contacts_ytd`,
  `n_attendance_contacts_ytd`, `attendance_intervention_status` (from the
  interventions mart: the highest absence threshold crossed and whether its
  required contact exists), `deanslist_communication_url`: the direct link to
  the student's DeansList communication page, where the history is read and a
  new entry is created. Pattern:
  `https://kippnj.deanslistsoftware.com/student/<dl student id>/<name slug>/communication`.
  The id is DeansList's own student id from `stg_deanslist__students`
  (`student_id`), not the PowerSchool student number. The builder confirms
  whether the name slug is required or decorative before choosing how to build
  it.
- Flags (booleans, the Lab tracker's thresholds, all year to date):
  `is_flag_4_plus_absences` and `is_flag_8_plus_absences` (all absences, excused
  and unexcused, matching the tracker's "# Days Absent"),
  `is_flag_never_in_school` (zero present days), `is_flag_gpa_below_2`
  (`gpa_term`), `is_flag_no_contact_10_days` (on a Promise Team roster with no
  communication log entry in 10 calendar days). The tracker's 4+ and 8+ lines
  sit close to the promotion policy's Q1 and Q2 approaching thresholds (4.5 and
  9, on the non-suspension, no-tardy count). The skill shows both; whether the
  team retires its own thresholds for the policy's is open question 10 in the
  stakeholder doc.

The free-text communication log `notes` column does not ship. Date, reason,
outcome and staff do. The notes stay in DeansList, one click away, and leaving
them out keeps the sheet's exposure smaller.

### The weekly snapshot

Attendance, discipline, contacts and GPA all have week-level history already.
Attendance and discipline recompute from the daily and incident facts. GPA comes
from `snapshot_powerschool__gpa_term` through `int_topline__gpa_term_weekly`,
which carries the term GPA in effect at each week's close onto the
enrollment-week spine (`int_extracts__student_enrollments_weeks`). The weekly
tab is built on that same spine, so every figure except tier goes back to the
start of the year.

Roster membership is the one gap: `int_deanslist__roster_assignments` is current
state with no dates. Add `snapshot_deanslist__roster_assignments` to
`src/dbt/kipptaf/snapshots/`, a check-strategy snapshot like
`snapshot_powerschool__gpa_term`, keyed on student, roster and source relation.
Tier history starts the day the snapshot first runs; earlier weeks show tier as
null.

`rpt_gsheets__promise_team_roster_weekly`: the roster model's columns plus
`week_start_date`, one row per student per school per enrolled week of the
current year, each figure as of the week's close. Uniqueness on
`student_number`, `school` and `week_start_date`. It depends on the nightly runs
only through the snapshots, which already carry that dependency.

`rpt_gsheets__promise_team_roster_changes`: the tab the skill reads. One row per
student per school with this week's figures, last week's, the change, and the
6-week trend as compact columns (for example `ada_6wk` as a comma-separated
string). A few hundred rows per school, so the Sheets connector can read it in
one range. The full weekly tab stays for the one-pager and for analysts.

`weeks_on_roster`, from the first week the roster snapshot shows the student on
a Tier 2 or 3 roster, is the cycle clock; the form's first "Active" response for
the student is the fallback where the snapshot predates nothing.

`rpt_gsheets__promise_team_contacts`: one row per non-mass communication log
entry this year for a student currently at the school: date, staff, method,
status, reason, topic, `is_mass_message`, `is_while_on_roster`. No `notes`
column. Sorted by student then date, so the skill can read one student's block
for the one-pager without pulling the tab. About 4,000 rows per school so far
this year, 8,000 to 10,000 by June.

`rpt_gsheets__promise_team_incidents`: one row per incident consequence this
year (an incident with no consequence still gets one row) for a student
currently at the school, from `fct_behavioral_incidents` and
`fct_behavioral_consequences`: incident date, category, tier, infraction,
referring staff, status, consequence type, suspension type, days assigned, start
and end dates, `is_suspension`, `is_reportable`. No free-text context. Sorted by
student then date, like the contacts tab, so the one-pager reads one student's
block. Tier 1 referrals are included, since the roster's `n_referrals` counts
them. Vocabulary: every DeansList incident is a "referral" in the models, the
sheets, the skill and its reference file, whatever tier it carries. No other
term, including the Paterson hub's, is used.

The weekly tab also carries `n_referrals_week`, `n_referrals_tier_2_plus_week`
and `n_oss_days_week`, so referral and suspension trends draw from it.

`rpt_gsheets__promise_team_form_responses`: every form response this year, one
row per submission, for the weekly history and the replacement of NCA's Student
History Archive (entry week, baseline ADA and GPA, exit week, exit figures come
from joining responses to the weekly tab).

### Delivery

The repo's sheet pattern (`docs/guides/google-sheets.md`, "Publishing a
warehouse view"): a Connected Sheets source sheet in the IMPORTRANGE Sources
folder does the extraction on a schedule, a Reports sheet pulls from it with
`IMPORTRANGE` only, and the dbt exposure is a marker that writes nothing and
points at the source sheet.

So the models stay school-agnostic with a `school` column, and the school split
happens in the Connected Sheets extract. One source sheet per school
(`rpt_gsheets__promise_team_roster [Newark Lab]`, `[NCA]`), each with a tab per
model and each extract filtered to its school in Connected Sheets. One Reports
sheet per school, shared one person at a time by the Data Team on the
stakeholder's request. The exposure description names the filter each source
sheet applies, since the access boundary is a sheet setting and not code. The
acceptance check below is what guards it. A new school is a new source and
report sheet pair plus an exposure, not a new model.

### The Claude skill

One scorer. The person who runs both teams has the Google Sheets, Google Slides
and Cube connectors and the skill. Everyone else reads what the skill produces.
The skill's reference file holds the Lab tracker's outreach script, the flag
thresholds, and NCA's intervention menu.

Every student name the skill prints carries two links from the roster sheet: the
DeansList communication page and the prefilled weekly form.

Commands, in the order a demo would show them (the mockup at
https://claude.ai/artifact/M7BCEbYf7kehbXdZgSHS4h shows each one):

1. **Score the week.** Per school and grade: who crossed a flag this week, who
   moved tier or flag since last week, who on a Promise Team roster has no
   contact in 10 days (with the DeansList link per row), and which active plans
   have no form entry since the last meeting. A behavior block: new suspensions
   with infraction, referring staff, days and return date; students returning
   from OSS this week, with the re-entry meeting due; anyone with 2 or more
   referrals in the week, listing who referred them. A six-week trend row for
   the school: flagged students, contact fidelity against the 100% goal, chronic
   absence rate, Tier 2+ referrals per week, OSS days per week. Reads the
   changes tab and Cube for attendance as of today.
2. **Meeting agenda.** The flag list ordered for the 60-minute meeting: new
   flags, then no-contact students, then students at 6 or more weeks on a Tier 2
   or 3 roster. Each line carries last contact date, staff and outcome, and this
   week's action from the form.
3. **Meeting deck.** The agenda as a Google Slides deck through the Slides
   connector: title, four numbers, one slide per agenda block, commitments,
   "before you leave". Saved to the Promise Team folder. "Regenerate" rebuilds
   it in place; "no names" produces the leadership version.
4. **Call prep card.** The outreach script filled with one student's ADA,
   absences, promotion status and last contact, with the barrier from the form.
   After the call, the skill returns the communication log entry text and the
   DeansList link.
5. **Log this week.** Returns the student's prefilled form link, or drafts the
   answers from a sentence the case manager types, for them to paste. Scribe
   mode is the same command for the whole meeting: the scorer types one line per
   decision as it is made ("Baptiste: bus pass by Wed, Ortiz owns") and, at
   "wrap up", the skill returns one prefilled form link per student with action,
   owner and due date drafted, plus DeansList text for any agreed family
   contact. The case manager clicks, checks and submits. Nothing is stored in
   Claude; the form response is the record, and an unsubmitted link is a lost
   commitment, which is why Monday's score lists active students with no entry
   since the last meeting. Recording or transcribing the meeting is not part of
   this design (see Open questions).
6. **Student one-pager.** Trend across the weekly tab, plan from the form, every
   non-mass contact from the contacts tab, every incident this year from the
   incidents tab with tier, infraction, referring staff and consequence, GPA and
   credits, laid out for printing before a family meeting.
7. **Leadership rollup.** One paragraph per school: counts by tier, contact
   fidelity, movement, open level-up requests, with six-week trend cards (on a
   plan, contact fidelity, share of plan students above their starting ADA,
   school ADA against 90%).
8. **Just the table.** Any grade or filter as one wide table of roster columns
   with no commentary, and a copy that pastes into a Sheet or Doc.

The skill never stores anything and never writes to the roster sheet. If a user
types a family-contact note into Claude, the skill returns it formatted for
DeansList and says so; a case note becomes form answers.

The skill is a Claude plugin or skill distributed the way the gradebook
expectations upload skill is. Its home in this repo and its distribution are the
builder's call, following that precedent.

## Open questions for the stakeholder

Carried into the skill and roster design once answered. None blocks the extract.

0. Credit recovery: how a student past the 18-absence threshold earns credits
   back, and where that is recorded today. The threshold itself comes from the
   promotion policy and is not a question. The Lab tracker:
   https://docs.google.com/spreadsheets/d/1j1pVyClQld93uIHyWFXcxsCozTAoyffuyErhrGO0MKY
1. Do the weekly form's 9 fields cover what each team records today? NCA's
   tracker has them all; Lab has an "Assigned Teammate" and a strategy column.
2. "Likely why" category and the week-6 Child Study Team recommendation (from
   the Paterson hub): do the Newark teams want either on the form?
3. Does NCA keep its own risk thresholds (GPA under 2.5, ADA under 75%, 5 or
   more referrals, 2 or more suspensions) alongside Lab's, and does it run the
   same weekly rhythm?
4. Who at each school may be granted the sheet, and who are the case managers
   who get the form?
5. Does either team record or transcribe the Wednesday meeting today? A
   transcript that names students and family situations is a student record held
   by a vendor, so the skill does not read one until Compliance names the
   approved tool and its consent and retention rules. Until then, follow-ups are
   captured by typing them into "Log this week" during the meeting.

## Left to the builder

- Reading roster membership without an A1 violation.
  `int_deanslist__roster_assignments` is a source intermediate. Either add a
  thin domain intermediate or mart for intervention roster membership
  (preferred, one row per student x roster x academic year) and link the issue,
  or baseline the edge with a reason.
- `rti_tier` and the focus live on `stg_deanslist__rosters`, not on the
  roster-assignments model. Carrying them through is a cross-project column
  change (`dbt-models` rules, two PRs or the single-PR clone pattern).
- `days_to_90_pct` is not modeled anywhere today; derive it from year-to-date
  membership and present days.
- The roster snapshot's `check_cols` (membership has no attributes that change,
  so the check is on presence of the row) and its tick, aligned with the GPA
  snapshot.
- The mass-message rule's exact threshold and matching (topic text equality
  versus a normalized prefix), checked against last year's data so the known
  blasts of 26 to 29 students are caught and the `Att: Social Services` case
  work is not.
- The form's question list and prefilled-link construction, and how the roster
  model builds `weekly_form_url` from it.
- Skill file layout, reference file contents, and distribution.

## Acceptance

- The Newark Lab sheet shows, for every enrolled student, every figure the Lab
  tracker's weekly tabs hold today, refreshed nightly, plus the latest
  communication log entry. Spot-check 5 students against the tracker's most
  recent tab and against DeansList.
- A student placed on `RTI Attendance - Tier 2` in DeansList shows
  `promise_team_tier = 2` the next morning.
- A form submitted from a student's prefilled link shows as that student's plan
  columns the next morning, with the dropdown value as `case_manager`, and the
  next morning's prefilled link for that student carries it.
- A mass message to 29 students does not count as a contact for any of them; a
  one-to-one entry under `Att: Social Services` does.
- The one-pager for a student lists every non-mass contact this year, read from
  the contacts tab, matching the count on the student's DeansList page.
- The one-pager lists every incident this year with its consequence, matching
  the student's DeansList incident history, and a student suspended on Friday
  shows a return date and appears in Monday's behavior block.
- The NCA report sheet contains no Lab students, and the Lab sheet no NCA
  students, checked by comparing each sheet's distinct `school` values after the
  first scheduled extract.
- The weekly tab has one row per student per enrolled week of the year, with
  attendance and GPA filled for every week and tier filled from the snapshot's
  first run onward.
- The changes tab for one school is under 1,000 rows.
- With only the sheet and Cube connectors, the skill returns a flag list for one
  grade with no file upload.
- No column in either sheet holds free text from the communication log.
