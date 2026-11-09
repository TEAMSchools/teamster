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

No student custom fields in v1. Plan lead, goal, cycle start, "likely why" and
the week-6 Child Study Team recommendation are plan state the Paterson hub
holds. They are open questions for the stakeholder (below). If wanted, each is
one DeansList student custom field plus one line in
`int_deanslist__students__custom_fields__pivot`.

Prerequisite outside this repo: a DeansList administrator creates the RTI roster
set at NCA (Lab already has one) and the Promise Team moves its current list
into the Tier 2 and Tier 3 attendance and behavior rosters.

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
  `promise_team_roster_names`.
- Attendance (daily and periods marts, year to date): `ada`, `ontime_rate`,
  `n_days_absent`, `n_days_absent_unexcused`, `n_days_tardy`, `ada_tier`,
  `is_chronically_absent`, `is_truant`, `days_to_90_pct` (membership days the
  student must attend without an absence to reach 90% ADA; null when already at
  or above), `n_absences_to_credit_loss` (18 minus unexcused absences, floor 0;
  the 18 is the high school credit-loss threshold and is a `var`).
- Discipline (behavioral marts, year to date): `n_referrals` (all DeansList
  incidents), `n_referrals_tier_2_plus` (`category_tier` in T2 and T3),
  `n_iss_days` and `n_oss_days` (DeansList consequences, the same source as
  `rpt_gsheets__suspensions`, not attendance codes), `last_suspension_date`.
- Grades (`fct_grades_gpa`, current term): `gpa_term`, `gpa_ytd`,
  `cumulative_gpa`, `n_failing_ytd`, `credit_hours_earned_cumulative`,
  `credit_hours_attempted_cumulative`, `credit_status`. The GPA the tracker
  pastes each week is term GPA, so `gpa_term` drives the GPA flag.
  `credit_status` is the Newark high school attendance-based credit loss rule
  (the tracker shows "Credit Loss - can earn N credits back" and warns families
  at 18 absences). Its exact definition is an open question below; until it is
  answered the column ships null and `n_absences_to_credit_loss` uses 18 total
  absences.
- Contact (communication log, year to date): `last_contact_date`,
  `last_contact_method`, `last_contact_reason`, `last_contact_outcome`,
  `last_contact_staff_name`, `days_since_last_contact`, `n_contacts_ytd`,
  `n_attendance_contacts_ytd`, `attendance_intervention_status` (from the
  interventions mart: the highest absence threshold crossed and whether its
  required contact exists).
- Flags (booleans, the Lab tracker's thresholds, all year to date):
  `is_flag_4_plus_absences` and `is_flag_8_plus_absences` (all absences, excused
  and unexcused, matching the tracker's "# Days Absent"),
  `is_flag_never_in_school` (zero present days), `is_flag_gpa_below_2`
  (`gpa_term`), `is_flag_no_contact_10_days` (on a Promise Team roster with no
  communication log entry in 10 calendar days).

The free-text communication log `notes` column does not ship. Date, reason,
outcome and staff do. The notes stay in DeansList, one click away, and leaving
them out keeps the sheet's exposure smaller.

### The weekly snapshot

Roster membership and GPA have no history in the warehouse:
`int_deanslist__roster_assignments` is current state with no dates, and
`fct_grades_gpa` holds one row per term. So the weekly tab is a snapshot, not a
recomputation, and its history starts on go-live day. That is accepted.

`rpt_gsheets__promise_team_roster_weekly`: a weekly snapshot of the roster
model, same columns plus `week_start_date`, one row per student per school per
week since go-live. Taken once per week on a fixed day after the nightly
extract; a missed night delays the week's row, it does not drop it. Uniqueness
on `student_number`, `school` and `week_start_date`. The builder picks dbt
snapshot versus incremental append.

`rpt_gsheets__promise_team_roster_changes`: the tab the skill reads. One row per
student per school with this week's figures, last week's, the change, and the
6-week trend as compact columns (for example `ada_6wk` as a comma-separated
string). A few hundred rows per school, so the Sheets connector can read it in
one range. The full weekly tab stays for the one-pager and for analysts.

"Weeks on a Tier 2 or 3 roster", from the first snapshot week the student
appears there, stands in for cycle start until the stakeholder answers open
question 2.

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

One scorer. The person who runs both teams has the Google Sheets and Cube
connectors and the skill. Everyone else reads what the skill produces. The
skill's reference file holds the Lab tracker's outreach script and the flag
thresholds.

Commands, in the order a demo would show them:

1. **Score the week.** Per school and grade: who crossed a flag this week, who
   moved tier or flag since last week, who on a Promise Team roster has no
   contact in 10 days. Reads the changes tab for movement and Cube for
   attendance as of today.
2. **Meeting agenda.** The flag list ordered for the 60-minute meeting: new
   flags, then no-contact students, then students at 6 or more weeks on a Tier 2
   or 3 roster. Each line carries last contact date, staff and outcome.
3. **Call prep card.** The outreach script filled with one student's ADA,
   absences, absences to credit loss and last contact. After the call, the skill
   returns the communication log entry text for the caller to paste into
   DeansList.
4. **Student one-pager.** Trend across the weekly tab, contacts, discipline, GPA
   and credits, laid out for printing before a family meeting.
5. **Leadership rollup.** One paragraph per school: counts by tier, contact
   fidelity, movement, for the principal or regional lead.

The skill never stores anything and never writes to the sheet. If a user types a
note into Claude, the skill returns it formatted for DeansList and says so.

The skill is a Claude plugin or skill distributed the way the gradebook
expectations upload skill is. Its home in this repo and its distribution are the
builder's call, following that precedent.

## Open questions for the stakeholder

Carried into the skill and roster design once answered. Only the first blocks a
column; the extract ships without it.

0. The credit loss rule: which absences count (all, unexcused, per course
   period), the day thresholds for "risk" and "loss", and how credits are earned
   back. The Lab tracker:
   https://docs.google.com/spreadsheets/d/1j1pVyClQld93uIHyWFXcxsCozTAoyffuyErhrGO0MKY
1. Plan lead per student: a DeansList custom field, or inferred from who logs
   the contacts?
2. Goal and cycle start date per student: custom fields, or kept in the meeting
   notes?
3. "Likely why" category and the week-6 Child Study Team recommendation: do the
   Newark teams use either?
4. Does NCA's Promise Team run the same thresholds and rhythm as Lab's?
5. Who at each school may be granted the sheet?

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
- The weekly snapshot's implementation (dbt snapshot or incremental append) and
  its weekly tick, after the nightly extract.
- Skill file layout, reference file contents, and distribution.

## Acceptance

- The Newark Lab sheet shows, for every enrolled student, every figure the Lab
  tracker's weekly tabs hold today, refreshed nightly, plus the latest
  communication log entry. Spot-check 5 students against the tracker's most
  recent tab and against DeansList.
- A student placed on `RTI Attendance - Tier 2` in DeansList shows
  `promise_team_tier = 2` the next morning.
- The NCA report sheet contains no Lab students, and the Lab sheet no NCA
  students, checked by comparing each sheet's distinct `school` values after the
  first scheduled extract.
- The weekly tab has one row per student per week since go-live, with no gaps
  for weeks the student was enrolled.
- The changes tab for one school is under 1,000 rows.
- With only the sheet and Cube connectors, the skill returns a flag list for one
  grade with no file upload.
- No column in either sheet holds free text from the communication log.
