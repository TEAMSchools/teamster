# Leader intent to return survey: design

Issue: [#6251](https://github.com/TEAMSchools/teamster/issues/6251)

## Why

Recruitment runs a separate intent to return survey for leaders. Until now the
only intent to return survey went to every active staff member outside the KTAF
business unit, and who got it was written into the code. Last year that left out
Teaching and Learning, a KTAF department whose leaders wanted to take it. They
filled in a different form offline, and those answers never reached the
warehouse.

This year recruitment chose the leader population themselves, through a setup
page, and sent their rules on 2026-11-17. The build turns those rules into
survey assignments, completion tracking, a reminder list, and a follow-up
export.

## Goals

- Leaders get the leader survey and only the leader survey. Nobody gets both
  intent to return surveys, and nobody gets both sets of reminders.
- Leader completion shows on the existing survey dashboard, separate from staff
  intent to return completion.
- Recruitment gets a Google Sheet listing leaders who haven't finished, with
  each leader's manager. Their Zapier reminder reads it, and recruitment's
  follow-up owner works from it to follow up one at a time.
- The leader rule lives in one model that every consumer reads.

## Non-goals

- A config sheet for the population. The rules change once a year and are
  hard-coded from recruitment's submission.
- Adding intent to return to `bridge_survey_expectations` (Asana task
  1219288212398597). The Survey Dashboard tracks completion from
  `rpt_tableau__survey_links` and `rpt_tableau__survey_completion`; only Cube
  reads the bridge.
- Building or editing the Google Form, the `reporting__terms` row, or the Zap in
  code. Those are setup steps (below).

## Anti-goals

These would make the build a failure even if it runs:

- A leader appears in both the leader and the staff intent to return
  populations.
- Anyone outside the leader population drops out of, or newly enters, the staff
  intent to return population.
- The existing general reminder feed changes shape. Its Sheet feeds a live Zap.
- A leader response counts as a staff intent to return response, or the reverse.

## Recruitment's rules (decided, from the setup page)

A person gets the leader survey when their job title, department, and business
unit are all in these lists, and they meet the same eligibility every survey
uses (active, primary assignment, hired or rehired at least 3 weeks ago).

Job titles (22):

- Achievement Director
- Assistant School Leader
- Assistant School Leader, SPED
- Assistant School Leader, School Culture
- Associate Director
- Associate Director of Academic Operations
- Associate Director of School Operations
- Dean of Students
- Deputy Chief
- Deputy Head of Schools
- Director
- Director Campus Operations
- Director Math Achievement
- Director of Social Work
- Director School Operations
- Head of Schools
- Managing Director
- Managing Director of Operations
- Managing Director of School Operations
- Managing Director of Teaching & Learning
- School Leader
- School Leader in Residence

Departments (8): KIPP Forward; Marketing, Comms, and Enrollment; Operations;
School Leadership; School Support; Special Education; Student Support; Teaching
and Learning.

Business units (5): TEAM Academy Charter School; KIPP Cooper Norcross Academy;
KIPP Miami; KIPP Paterson; KIPP TEAM and Family Schools Inc.

The setup page also listed Managing Director of Talent Acquisition. Recruitment
confirmed on 2026-11-20 that it was a mistake, so it is left out.

On the 2026-11-20 roster this is 239 people: Newark 113, Camden 44, Miami 35,
KTAF 29, Paterson 18.

33 people hold a listed title in a department that is not listed, 32 of them at
KTAF (Directors and Managing Directors in Teacher Development, Talent
Acquisition, HR, Data, and similar). Recruitment confirmed on 2026-11-20 that
they stay out. Because KTAF also gets no staff intent to return survey, they get
no intent to return survey at all. That is intended.

The staff intent to return population stays as it is today, everyone eligible
outside KTAF, minus anyone in the leader population.

## Setup outside the code (owner: data team, before the build is verified)

1. Create the leader Google Form as a copy of the staff intent to return form.
   Title it exactly `Leader Intent to Return Survey`. Replace the main intent to
   return question with recruitment's leader question and its 4 answers, with
   the "LEADERS:" prefix removed from the question. Save it in the surveys Drive
   folder that `google_forms_responses_sensor` scans.
2. Add a `reporting__terms` row: academic year 2026, name
   `Leader Intent to Return Survey`, code `LITR`, type `SURVEY`, start
   2026-11-30, end 2026-12-11.
3. Create the follow-up Google Sheet connected to the new extract, and share it
   with recruitment.
4. Recruitment points their Zap at that Sheet. Recruitment's reminder text is in
   the setup page's store, with "[deadline]" replaced by Friday, December 11.

The form title must equal the terms row name: `int_surveys__survey_submissions`
attributes a response to a round only when the form title matches the terms row
name and the submit date falls inside its dates. The `LITR` code keeps leader
responses apart from staff responses, which use `ITR`, because completion joins
on the round code.

## The build (decided)

1. New domain model `int_surveys__leader_intent_to_return_population` in
   `models/surveys/intermediate/`, at one row per employee. It applies the
   survey eligibility and recruitment's 3 lists. This is the only place the rule
   lives.
2. `rpt_tableau__survey_links`:
   - New union branch, survey `Leader Intent to Return Survey`, joined to the
     `reporting__terms` row by that name, reading its people from the new
     population model. The link is the new form's responder URL.
   - The staff `Intent to Return Survey` branch excludes anyone in the
     population model, for academic year 2026 and later only. Past rounds keep
     their original populations, so historic completion does not change.
3. `rpt_tableau__survey_completion` needs no change. It picks up the new branch
   and matches responses on `survey_round = survey_code`.
4. `rpt_extracts__survey_reminder` leaves out rows for
   `Leader Intent to Return Survey`. Leaders still get general reminders for
   their other surveys. Its output stays one `email` column.
5. New extract in `models/extracts/google/sheets/`: one row per leader in the
   current leader round who has not submitted. Columns: name, job title,
   department, business unit, location, work email, manager name, manager email.
   It reads the population model and `int_surveys__survey_submissions`, not
   another `rpt_` (A1). Staff name and email columns carry `contains_pii: true`.
   A submission counts when it matches the current academic year and term code
   `LITR`, which means inside the terms row's dates. A late answer counts only
   if the end date is extended. The Sheet is a full refresh: the Zap reads every
   row, and recruitment keeps its own notes outside it.
6. A Google Sheets exposure for the new extract, with the Sheet's URL.
7. `rpt_appsheet__seat_tracker_roster.itr_response` reads leader answers too, so
   leaders don't show blank in the seat tracker. It maps the leader question (by
   its `question_shortname` on the new form) like this:
   - "This is my last school year in my current role…" → Not Returning
   - "Committed through SY 27-28…" → Returning 1 Year
   - "Committed through SY 28-29…" → Returning 2 Years
   - "Committed for the next 2+ years" → Returning 2+ Years

   The 3 Returning values are new to `itr_response`. Check the AppSheet column
   and anything else that reads it for a fixed list of allowed values.

8. Add `Leader Intent to Return Survey` to the survey title filter in
   `rpt_tableau__survey_responses`, so leader answers reach the dashboard.

## Left to the builder

- Model names, apart from the survey title and term code above, which the form
  and the sheet must match.
- Whether the follow-up extract reads `dim_staff` or `int_people__staff_roster`
  for names and managers. Follow A2: use the mart if it has the columns.
- A check before merge: the staff branch of `rpt_tableau__survey_links` on the
  PR matches prod minus the leader population, person for person.
- Tests. At minimum: a uniqueness test on each new model's grain, and a unit
  test on the population rule covering a person who matches all 3 lists, one who
  matches only 2, and a KTAF Teaching and Learning leader.
- Whether the survey dashboard needs any change to show the new survey, for
  example a hard-coded survey filter. Check the workbook.

## Open with recruitment

- Whether removing Chief Academic Officer from the titles was intentional.

## Constraints

- The survey opens 2026-11-30, so the change has to merge and deploy before
  then.
- The form's responder URL exists only after step 1 of the setup. The build can
  start before that, but the link can't be filled in until then.

## Revision 2026-11-20: no new-hire wait for intent to return

Decided during final review. Neither intent to return survey waits 3 weeks after
a hire or rehire; both ask about next year, which a new hire is also planning.
Leader eligibility is active plus primary assignment. The staff intent to return
survey gains recent hires outside KTAF, which supersedes the anti-goal that
nobody newly enters the staff population. Every other survey keeps the 3-week
wait.
