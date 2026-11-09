# Intake brief: HS Promise Team data tool (Newark Lab and NCA)

## Sources read

- Meeting "Project scoping: HS Promise Teams" (Wispr Flow summary and full
  transcript), 2026-11-09. Speakers: Anthony Walters, Jabari Bradley, Kevin
  Shaw, Duke Jumah.
- Claude Doc "Promise Team roster: project handoff", 2026-11-09, written by the
  previous Claude session on this project: decisions, data facts, open items,
  repo state. It links the design spec, the stakeholder questions doc, the
  interactive mockup, a sample Slides deck and a walkthrough script.
- GitHub issue #6306 and its two comments, 2026-11-08 and 2026-11-09.

The sample students named in the mockup walkthrough are fake and do not appear
here.

## What we heard

**Who asked, and for whom.** `heard` Duke Jumah, Director, School Support, who
runs the Promise Teams at both Newark high schools, KIPP Newark Lab and KIPP
NCA, and is the pilot champion and project sponsor. `heard` The direct users are
the meeting facilitators: the APCs, the DSOs and the AP of Special Education at
each school, all APs or DSOs who should already hold Claude licenses. `heard`
Case managers (deans, grade-level chairs, social workers) are indirect users who
only log communications in DeansList and need no license.

**The decision they are trying to make.** `heard` Each week, which 5 to 15
students the Promise Team focuses on, who owns each student's follow-up, what
the next action is, and whether a student stays on or graduates off the plan
after six weeks of data. `heard` Before this, teams tried to work hundreds of
students and spent most of their time pulling data and building decks rather
than acting.

**What they described wanting.** `heard` The mockup walked through was well
received as a frame to customize, not a finished design: a Claude skill with
commands for a score of the week, Wednesday's agenda, a slide deck, a call prep,
a weekly log, a student one-pager, a leadership roll-up and plain data tables.
`heard` Flag criteria aligned to Lab's thresholds (4 or more absences, 8 or more
never in school, term GPA under 2.0, no family contact in 10 days) plus NCA's 2
or more suspensions. `heard` The weekly log form's fields (case manager, status,
barrier, intervention, action, due date, evidence, tier change) are adequate for
both schools. `heard` No double entry anywhere: contacts logged once, in
DeansList. `heard` Rosters managed in DeansList by the DSOs and APCs as the
source of truth. `heard` The AP of Special Education wants case scenarios for
students with IEPs or 504s and those in the referral process; the DSO wants
named case managers for chronically absent students.

**What they said about timing.** `heard` Duke shares the mockup and deck with
APCs and DSOs and returns feedback by Tuesday, November 17, end of day. `heard`
The data team is offline the week of November 16 for its step-back. `heard`
Anthony observes two Promise Team meetings on Wednesday, December 2, and turns
around a final draft that week, then approval and a project contract. `heard`
Ready before the end of December.

**What they said they already use.** `heard` Lab keeps a Google Sheet tracker
fed by hand each week; NCA keeps a tracker of 81 focus students with a case
manager, priority and status per student. `heard` Both teams log communications
in DeansList and had also been typing them into the tracker. `heard` Lab has 12
active DeansList RTI rosters; NCA has none yet. `heard` The high schools are not
on Branching Minds. `heard` Paterson runs a different Claude hub on manual
exports; Kevin Shaw built it.

**Decisions made in the meeting.** `heard` Flag criteria as above. `heard` The
10-consecutive-day no-contact cutoff stays. `heard` Case managers log only in
DeansList. `heard` The "likely why" category is deferred as a later enhancement.
`heard` The week-six child study team referral flag waits on Duke confirming a
backing process at both schools, because of the liability of unreferred students
sitting on a plan.

## What exists today

- `found` An approved design spec on branch
  `anthonygwalters/feat/claude-promise-team-roster`, 11 commits, issue #6306,
  with a stakeholder questions Google Doc (unshared), an interactive mockup
  shared with the org, a sample Slides deck (unshared) and a walkthrough script.
  No code yet. From the handoff doc and the issue comments.
- `found` Decisions already taken in that spec: a dbt extract to Google Sheets
  plus a Claude skill rather than Cube-first; roster membership in DeansList RTI
  rosters, Tier 2 and 3; plan state in one Google Form per school with prefilled
  links; a contact is any non-mass DeansList communication while on a Tier 2 or
  3 roster; every DeansList incident is called a referral and nothing else;
  Connected Sheets per school is the access boundary. From the handoff doc.
- `found` Warehouse pieces the build reads, all existing: the attendance,
  behavioral incident and consequence, family communication and GPA facts;
  `int_students__promotional_status` with the Newark promotion policy; GPA
  history in the term snapshot; `int_deanslist__roster_assignments` and
  `stg_deanslist__rosters` for tier; `int_deanslist__comm_log`. From the handoff
  doc, confirmed by the model list.
- `found` Tableau already covers part of this: the High School Early Warning
  Dashboard (GPA, credits, ADA, IEP and 504, suspension counts; owner Gaby
  Rangel, 106 views last month) and the Attendance Dashboard's CA Intervention
  Tracker and comm log (914 views last month). Neither holds Promise Team
  rosters, plan state or weekly actions. From Tableau search and the exposures
  file.
- `found` Cube has attendance and enrollment views, no behavior, communication
  log or GPA. From the Cube catalog.
- `found` DeansList volume: about 5.9 million Newark behavior rows this year
  against 330 thousand for Paterson, so manual exports do not scale; 3,565
  communication rows for 508 Lab students and 4,140 for 730 NCA students, mostly
  daily absence notes. From the handoff doc.
- `lead` Asana: an ad hoc task to send Duke a Calendly link for this scoping,
  and the TEAMster task for #6306, both assigned to Anthony. No project yet.
- `lead` GitHub #3701, open: attendance interventions domain placement. Touches
  the same models.
- `found` Support history: a handful of tickets since July 2024 mention Promise
  Team or the intervention tracker; no theme. The DeansList category carries the
  volume.

## The gap

- Everything the skill needs exists in the warehouse except roster membership
  over time (a snapshot), the Promise Team form responses (a new Google Sheets
  source), and one domain model to read rosters from a report model without
  breaking the layering rule.
- NCA has no RTI rosters in DeansList; a DeansList admin creates the Tier 2 and
  3 set before anything shows for NCA.
- The form, its prefilled links and the case-manager carry-forward are new, and
  a frozen form is a commitment: fields change only by adding options.
- The skill itself: eight commands, a deck generator, a one-pager, and a
  banned-word check on every output.
- The design spec is an engineering document; there is no charter, stakeholder
  map, RAPID log or risk log yet, and the stakeholder questions sit in an
  unshared doc.
- What the stakeholder may not know is there: the HS Early Warning Dashboard
  already carries the GPA, credit and suspension cuts for both schools today.

## Questions for the stakeholder

1. The week-six child study team flag: is there a referral process at both
   schools to stand behind it? Duke is checking.
2. Roster ownership: are the DSOs at Lab and NCA agreed that DeansList RTI
   rosters are the source of truth they maintain?
3. Who may see each school's sheet, and who are the case managers at each school
   for the week-one seed?
4. Credit recovery: how a student past 18 absences earns credit back, and where
   that is recorded. Open since the spec.
5. Does either team record its meeting today? Compliance owns whether a
   transcript naming students can be kept.
6. The NCA tracker's priority A/B/C: keep it as a form field, or drop it now
   that criteria align to Lab?

## Size

`project`: a defined start (kickoff the week of December 2 after the meeting
observations) and end (live before winter break), several deliverables (seven
dbt models and a snapshot, a form per school, Connected Sheets per school, a
Claude skill, a deck template), and at least four people's work (Anthony on data
and skill, Jabari on DeansList and licenses, Duke on rosters and feedback, a
DeansList admin for NCA). The charter wraps the approved spec rather than
replacing it.
