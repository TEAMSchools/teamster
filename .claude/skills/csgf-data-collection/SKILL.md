---
name: csgf-data-collection
description: >-
  Use when working on the annual Charter School Growth Fund (CSGF) data
  collection -- confirming participants, tracking the kickoff/training, rolling
  over last year's item-list documentation doc, answering the Salesforce
  Portal's Preliminary Questions, or preparing the Salesforce Portal / Google
  Sheets submissions. Triggers: a CSGF kickoff or data-collection email, the
  CSGF-dedicated Slack channel, the `csgf_data` exposure, `rpt_gsheets__csgf_*`
  models, or "roll over the CSGF collection."
---

# CSGF Annual Data Collection

**Status: draft, in progress.** This skill is being built one step at a time
from the collection owner's walkthrough of the current cycle, written on the
assumption that whoever leads this next cycle may have **no prior exposure** to
CSGF or this process at all. Steps below are confirmed; the procedure continues
to grow as more of the cycle is narrated. Do not treat an absent step as
"doesn't happen" -- it may just not be captured yet.

## Who this skill is for

**Not just the collection owner.** This process involves multiple task owners
across three teams (Data Team, Compliance, and named individuals per item -- see
the
[2026-2027 item-list doc's own Item List table](https://docs.google.com/document/d/1C5xOLrbm4ybiMAfZo9Fd7sHHZ-ncYftjZI0aO5J2o9A/edit?tab=t.0)).
Anyone on any of those teams asking for CSGF help should trigger this skill, not
only the Data Team's collection owner.

**Real per-person split for the 2026-2027 cycle** (from that doc's Item List
table -- re-check it fresh each cycle, this is NOT guaranteed to repeat):

- **Anthony Walters / Casey Gibson**: Postsecondary Pathways (Overgrad/Other
  Application Results tabs; Naviance is struck through/N-A this cycle),
  Discipline Data, the Round 2 NSC file.
- **Anthony Walters / Gaby Rangel**: HS Enrollment, AP Scores, AP Offerings, HS
  Grad Data (the HSDC tabs), plus the main **School Enrollment** Portal task --
  but see Kevin and Laszlo below, who own specific FIELDS on that same shared
  task, not separate tasks.
- **Kevin Verhoff**: School Staffing Data, Org Staffing Summary, Org Chart
  (possibly shared with Laszlo) -- and, on the shared **School Enrollment**
  task, specifically **Teacher Retention, Teacher Count, and the school leader
  info fields** (that's the co-leader row gap noted elsewhere in this file --
  Kevin's, not a dbt gap to chase).
- **Laszlo De Simon**: Schools List, Officer's Certificate, Growth Plans, Data
  Sharing Agreement, and on the shared **School Enrollment** task specifically
  **the budget info fields** (`Total Budgeted Enrollment` and likely
  `Total Seat Capacity`/`Total Seats When Growth Plan Complete` -- this is who
  to escalate the budget-target-sheet gap noted elsewhere in this file to, not a
  generic "Finance" hand-wave).
- **Jeff Fleming / Nadja Salem / Susie Chu**: Key Contacts, School Finance
  (P&L), Org Finance, Bank Info, Budget Upload.
- **Anthony Walters**: ADA% and Chronic Absenteeism% on the School Enrollment
  task, confirmed by the collection owner 2026-09-22 -- not in the item-list
  doc's own table (a real gap in that doc, not a dbt gap), so this line is the
  only place it's written down.

**When helping someone who isn't the collection owner**, don't default to
walking them through the collection owner's full checklist (Steps 1-7 below).
Instead:

1. Identify who's asking. The session's `userEmail` context is the first signal;
   ask directly if it's ambiguous or absent.
2. Check what THEY specifically own -- the per-person split above for this
   cycle, or the current cycle's item-list doc directly if a name isn't listed
   above (ask for its link if you don't have it -- it's a new doc each cycle, so
   don't assume last cycle's link, or even this session's, still applies).
3. Scope help to that item, not the whole collection. A Finance person asking
   about Total Seat Capacity doesn't need the Schools List walkthrough, and vice
   versa.
4. **Before asking them for anything, go read what's already been given.** Don't
   make a task owner re-explain context or re-fetch a link this skill already
   has. For their specific item, check: this cycle's item-list doc (above) for
   dates/notes on that item; `references/field-definitions.md` for CSGF's own
   definition of the field(s) involved; the Portal mechanics / HSDC mechanics
   reference sections below for how that task type actually works;
   `docs/models/csgf-data-model.md` if a `rpt_gsheets__csgf_*` model touches
   their item at all; and this file's Known data risks / Open Items for anything
   already found and verified about it. Only ask them a question once those
   sources genuinely don't answer it -- the point is to make asking for help
   require as little from them as possible, since most of them have far less
   context on this process than the collection owner.

## Overview

[CSGF (Charter School Growth Fund)](https://chartergrowthfund.org/) is a
nonprofit that invests growth capital in high-performing public charter school
networks and provides portfolio-wide organizational support (finance,
facilities, policy, communications). KIPP TEAM & Family is a member of CSGF's
investment portfolio.

**Why this matters, concretely:** participating in the annual Data Collection is
a term of KTAF's grant agreement with CSGF, not a courtesy or CSGF being nosy.
The data submitted directly informs CSGF's own grant-making decisions about KTAF
and lets CSGF report portfolio-wide results to their own funders and donors.
Treat deadlines and data quality accordingly -- this is compliance-adjacent, not
an optional survey.

The collection covers academic, staffing, finance, and org data, submitted
across two systems:

- **Salesforce Portal** -- most items (school info, staffing, finance,
  discipline, contacts, growth plans, etc.).
- **Google Sheets** -- the HS Data Collection (HSDC) workbook (Data Team only)
  and CSGF's Data Definitions reference sheet.

The eight `rpt_gsheets__csgf_*` dbt models feeding the `csgf_data` exposure are
the pipeline that prepares KTAF's HS Data Collection extracts -- see
[issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) for their
documentation work. This skill is the process/ownership side: what the
collection owner (project manager for this collection) does each cycle,
independent of the dbt pipeline. Where the two intersect (e.g. verifying a
Preliminary Question against a `rpt_gsheets__csgf_*` model), that's called out
explicitly below.

Reference doc: `docs/models/csgf-data-model.md` -- not yet published; will be
added as part of #4897. Once it exists, read it first for the dbt-side lineage;
this skill covers the manual/ownership side only.

## Key resources

**Internal (KTAF-owned):**

- [Drive folder holding every cycle's item-list doc](https://drive.google.com/drive/folders/1S_UsLY-B0b4SnI-mFEiXeTgY1EhkUuUG)
  -- see Step 3 below.
- [Data Team tracking folder](https://drive.google.com/drive/folders/129irqLYWIuGhncltuBOSYcL2Lz-IeZ5X)
  -- participants get access to this and are allowed to drop relevant supporting
  docs here if needed. **This does not substitute for submitting data the way
  CSGF actually requires** (Portal / HSDC Sheet) -- it's a convenience/backup
  location, not a submission channel.
- ["CSGF Data" Google Sheet](https://docs.google.com/spreadsheets/d/1rbPI03qTMMv3NVC1_1rjodBq3Cd8mktd5Fwosy2AxuM/edit)
  -- where all eight `rpt_gsheets__csgf_*` dbt models land; see "How the dbt
  models actually reach CSGF" below (including its PII caution).

**CSGF-provided:**

- [CSGF Data Collection Portal User Guide](https://docs.google.com/document/d/1V5LBa--mKLZC2PSd9ptEVSQSoj-4YUHWznPyPu62A6M/edit?tab=t.0)
  (dated August 2026) -- see "Portal mechanics" and "HSDC mechanics" below for
  the extracted contents.
- [CSGF Data Collection Field Definitions](https://docs.google.com/spreadsheets/d/1hpMLqeFcci_Epar3InHRB8UXly7ZLg42vzjgANUpzP8/edit?gid=963005787#gid=963005787)
  -- CSGF's own field-by-field definitions. Full extraction with structural
  gotchas: [`references/field-definitions.md`](references/field-definitions.md).
  **Check this before asking the collection owner what a field means or what a
  task's real column list is** -- it already answers most of that. Don't wait to
  be handed a screenshot of a field name or a pasted header row when this doc
  can resolve it directly; use the pasted/screenshotted ground truth to verify
  what's here, not as the first source.
- This cycle's HS Data Collection Google Sheet ("26-27 HS Data Collection
  Template -- KIPP TEAM & Family," owned by
  `datacollection@chartergrowthfund.org`). **Caution: once populated this is a
  live submission workbook holding real student records.** Don't read its full
  content casually -- see "HSDC mechanics" below for what's safe to check and
  how.

---

## Procedure: Run the annual rollover, start to finish

Follow these steps in order each cycle.

### 1. Confirm collection participants

**Trigger:** CSGF sends the email confirming who is involved in this year's
collection.

- Review the participant list with your manager; update names/roles as needed if
  responsibilities shifted since last cycle.
- **Flag back to CSGF:** the team's communication emails need to go to
  `@teamandfamily.org` addresses, but any Google Docs/Sheets used for the
  submission need to be shared with `@apps.teamschools.org` addresses instead --
  the two domains serve different purposes and CSGF sometimes defaults to one
  for both.

### 2. Wait for the kickoff communication and attend training

**Trigger:** after replying to CSGF on participant confirmation, wait for CSGF's
kickoff email.

- Sign up for and attend whatever session CSGF offers.
- **Don't assume the format repeats.** One cycle had a mandatory kickoff meeting
  with a required training signup; the next cycle replaced that with optional,
  self-serve office hours (multiple slots, attend at your discretion) plus a
  note on when attendance is actually warranted (exhausted self-serve resources
  AND last year's approach no longer works AND a CSGF support ticket has gone
  unanswered 5+ business days). Read the current cycle's kickoff email for the
  actual format rather than repeating last year's steps.
- **Feed Claude the training/kickoff links** (session recording, slides, any new
  CSGF doc mentioned) as soon as you have them -- not just for this step.
  They're what let Claude support the rest of the rollover, including
  double-checking Step 3's item-list doc against what training actually said
  changed this cycle, rather than working from last cycle's doc alone.

### 3. Roll over the item-list documentation doc

Once training/office hours info is in hand, create this cycle's version of the
team's internal item-list doc (the one that lists who owns which CSGF item and
tracks submission status).

**Source material:**

- Folder holding every cycle's doc:
  [Drive folder](https://drive.google.com/drive/folders/1S_UsLY-B0b4SnI-mFEiXeTgY1EhkUuUG)
- Prior cycle's doc, as a worked example of the shape:
  [2025-2026 doc](https://docs.google.com/document/d/1J9x4LvPCRkvWhhwuKt6XVu83xZgaJMWHNSodM0z9BRs/edit)

**Steps:**

1. Create a new folder in the Drive folder above for the new submission cycle.
2. Make a copy of last cycle's doc into the new folder.
3. Adjust the copy -- dates, names, and whatever CSGF changed about the
   submission requirements themselves. Read this cycle's CSGF kickoff
   communication carefully; don't assume the process repeats unchanged.

**What tends to change, by category** (from diffing the 2025-2026 doc against
the 2026-2027 doc -- use this as a checklist of _where to look_, not an
exhaustive list of what will change this cycle):

- **Dates (always change, easy to get wrong):** school year(s) covered,
  collection window, internal pre-work deadline, internal deadline, panic week,
  official deadline. **Gotcha:** the 2025-2026 doc has a stray date typo (a
  deadline reminder stamped with the wrong year) -- double-check every date
  against the current cycle's actual calendar rather than trusting the prior
  doc's arithmetic.
- **Links that regenerate every cycle, not just get new tabs:** CSGF's Loom
  walkthrough videos are new links each cycle. More importantly, the **HS Data
  Collection Google Sheet can get an entirely new spreadsheet ID** cycle to
  cycle -- don't assume "same link, new tabs."
- **Process changes CSGF makes to the portal itself:** e.g. one cycle "revamped"
  the submission process, the next "reused the same systems as last year" -- one
  sentence, easy to skim past. New portal features get called out (task
  assignment to individuals, CSV upload) and change what's possible
  procedurally. New CSGF-provided resources can appear (a submission manual doc,
  video tutorials on the Salesforce Portal home page) that didn't exist before
  -- both of those appeared for the first time in the 2026-2027 cycle.
- **Ownership/assignment table:** names and item groupings shift -- a single
  owner pairing can split into two, with items redistributed between them. Don't
  assume last cycle's owner list is still accurate; confirm with each person.
- **Notes/status column:** prior-cycle submission status notes (e.g. "Submitted
  10/8", "Ready for review") should be cleared, not carried forward -- they're
  per-cycle progress markers, not durable info.

### 4. Complete the Preliminary Questions (unlocks HSDC)

**Trigger:** once you have portal access and the item-list doc is rolled over,
complete the Preliminary Questions task in the Salesforce Portal. This is
deliberately first in CSGF's own task order -- your answers determine which
other tasks get marked "Not Applicable" and gate whether the HS Data Collection
(HSDC) workbook tasks unlock at all.

**This is a task the collection owner can often do solo**, without pulling in
every domain owner, if they have enough context on KTAF's current operations --
but don't answer from memory alone when the data already exists.

**Verification-first rule:** before answering a Preliminary Question, check
whether it's already answered by our own data, in this order of preference:

1. **A `rpt_gsheets__csgf_*` report table**, if one exists for the relevant
   domain -- query it directly (e.g.
   `select ... from teamster-332318.kipptaf_extracts.rpt_gsheets__csgf_hs_enrollment`).
   This is the literal artifact that would feed the submission, already encoding
   CSGF's grain and year-anchoring logic -- more direct and authoritative than
   re-deriving the same filters by hand.
2. If no dedicated CSGF report exists, fall back to a general source model (e.g.
   `int_extracts__student_enrollments`) and apply the same filters CSGF's own
   report models use for that domain.
3. For a policy/rule question rather than a population question (e.g. GPA scale,
   business logic thresholds), check subdirectory `CLAUDE.md` business-rule docs
   (e.g. `src/dbt/kipptaf/models/students/CLAUDE.md`) before assuming no
   verifiable source exists -- "not a CSGF report" and "not verifiable" are not
   the same thing.
4. Only if none of the above exists, answer from institutional knowledge -- and
   flag that as a gap worth documenting.

**Keep every check aggregate-level** (counts, distinct schools/regions) -- never
query for or paste individual student rows into this process. This
question-answering step needs proof the population exists, not who's in it.

**A nonzero row count proves data exists, not that the network administered
it.** A question asking what the network/school _administered_ is asking about
an institutional decision, not a data population -- rows can exist because a
student took a test independently and the score was still recorded. Cross-check
against known network strategy (e.g. the `carat-dashboard` reference doc
documents KTAF's assessment strategy as SAT-based, referring to ACT as
historical/legacy) before reading "rows exist" as "we administered this."

**Check whether a query's scope covers the full population the question is
about, and watch for survivorship.** A report or extract limited to a grade band
(e.g. HS-only, grades 9-12) or a single academic year can structurally miss
where something actually happens (KTAF's gateway math course, Algebra I, is
first offered in **8th grade** -- invisible to any HS-scoped query). Even within
scope, a later-grade count can be inflated by survivorship: students who succeed
early and move on stop appearing, so the population left in a later grade/cohort
is disproportionately non-passers or new arrivals, not a representative sample
of "when this typically happens."

**Preliminary Questions log**: full question/answer/verification history (17
questions across four subsections) lives in
[`references/preliminary-questions-log.md`](references/preliminary-questions-log.md)
-- read it before re-answering any of these, since several answers required a
non-obvious verification path (survivorship bias, checking a `CLAUDE.md`
business-rule doc instead of a report) that's easy to redo wrong from scratch.

**This closes out the Preliminary Questions task for the 2026-2027 cycle.**
**CSGF has reviewed and accepted these answers** -- task status should read
Completed, not just Ready for Review. Re-run the whole log next cycle rather
than assuming answers carry forward -- several entries changed between cycles on
their own (the Naviance N/A flag, the item-list ownership split) even when the
underlying fact didn't.

### 5. Verify the Schools tab

**Trigger:** immediately after Preliminary Questions is done -- per CSGF's
["Data Collection Portal Overview and Navigation"](https://www.loom.com/share/e746a53871c14a918650e34c9c8cecfe)
walkthrough video, this is the next step in their intended task order (matches
the Portal Guide's "complete Preliminary Questions, Schools List, and Growth
Plans first" instruction).

- **Ask the collection owner (or Laz specifically, who has historically owned
  this task) whether there's a working Google Sheet they use to prep Schools
  List data before entering it into the Portal.** One existed last cycle; since
  it's per-cycle like the other CSGF-adjacent docs in this skill, ask for this
  cycle's URL rather than assuming last cycle's link still applies or that no
  such sheet exists this time.
- Review the Schools List task for accuracy (the roster of schools CSGF has on
  file for KTAF).
- **The Schools List task's own in-portal instructions are more specific than
  the walkthrough video, and take priority where they differ** -- the video's
  general "submit a ticket to add/remove a school" framing does NOT match what
  the actual task says:
  - **Missing school** → self-service: edit → "Add Record" to create it. No
    ticket needed. New schools get NCES ID `000000000000` and State ID `0000` as
    placeholders.
  - **Support ticket needed for exactly one case**: CSGF auto-flips every school
    they had on file as "planned" for 26-27 to "operational." If one of those
    isn't actually open yet, that's the ticket-worthy scenario -- not
    additions/removals in general.
  - **Marking a school as closed** → self-service: set the **Academic Year
    Closed** value yourself (see the reference doc's precise definition of that
    field) on any school that's not operational. No ticket for this either.
  - Review CSGF's own "Field Definitions" link inside the task for anything
    field-specific not covered here.

**Working a real missing-school case (2026-2027 cycle: KIPP Legacy Elementary,
KIPP Legacy Middle, KIPP Miami Technical High)**: full export/import mechanics,
what actually worked, and every field-name/formatting gotcha hit along the way
are in
[`references/schools-tab-verification.md`](references/schools-tab-verification.md)
-- read it before attempting an Add Record / Excel export-import cycle on this
task, since the Portal Guide's own wording gets some of the mechanics wrong.

**Status as of 2026-09-11: all 3 bare records added** (KIPP Legacy Elementary,
KIPP Legacy Middle, KIPP Miami Technical High) via Add Record. **Still needs Laz
to review and enter the remaining data** -- specifically the fields confirmed to
have NO source anywhere in the codebase: `Total Seats at Full Scale`,
`School Model` (+ Notes), `Facility Ownership Type`,
`Lease Term Including Extensions`, `Facility Serve Long Term Needs`,
`New Lease/Building in 2 Years`, `Real Estate Financing in Calendar Year` (+
Amount Financed, Lenders). These need direct input from Laz/the schools, not
more codebase digging.

**Schools List doesn't have to fully close before moving on to Step 6.** Once
the bare records exist, tag Laz asynchronously for the remaining fields and
proceed -- don't block the whole collection on his availability. Carry the open
items into Step 6's item-list doc as one of the "open questions" it's meant to
hold before sharing.

### 6. Meet with the team to resolve open questions and share the item-list doc

**Trigger:** after the item-list doc is drafted (Step 3) and Preliminary
Questions are done (Step 4) -- before treating the doc as final.

- The item-list doc is drafted solo first, as working notes -- it will naturally
  contain open questions to yourself (shared-task ownership that isn't settled
  yet, coordination questions between two people covering the same Portal task,
  etc.). Don't share it out with those still unresolved.
- **Data Team members:** resolve open questions in the team's regular Data Team
  meeting, then update the doc with the resolution before sharing further.
- **Teammates outside the Data Team** (Compliance -- Jeff Fleming, Nadja Salem,
  Susie Chu): reach them via the CSGF-dedicated Slack channel, replacing the
  in-person kickoff meeting cycles used to have (alongside CSGF's own optional
  office hours -- see Step 2). Post one message covering: the 3 most important
  dates, what changed this cycle, a link to the item-list doc with an explicit
  prework ask, the Outlook invites they'll get, and per-person specifics called
  out by name (don't make people extract their own action items from the full
  doc). **Template, sent and working for the 2026-2027 cycle:**
  [`references/kickoff-slack-template.md`](references/kickoff-slack-template.md)
  -- reuse the structure, swap the `[ADJUST]` placeholders each cycle.

### 7. Generate and send the Outlook calendar invites

**Trigger:** once this cycle's dates are finalized (Step 3) -- same dates the
Slack message (Step 6) uses.

1. **First, create an Outlook Contact Group** with everyone involved in this
   cycle's collection, if one doesn't already exist -- do this before touching
   the invites. A personal Contact Group can be typed directly into an invite's
   attendee field in the Outlook client and it expands to every member
   automatically, so you add it once per invite instead of typing each person's
   email every time. (A personal Contact Group has no email address of its own,
   so it can't be embedded in a raw `.ics` file -- it only works from inside the
   Outlook client, which is exactly how it's used in step 3 below.)
2. **Generate an `.ics` file** covering this cycle's actual dates: the Data
   Collection Window, Pre-Work Completed Deadline, each Office Hours slot, the
   Internal Deadline, Panic Week, and the Official Deadline (pull the exact
   dates from the item-list doc's Context section -- see Step 3). **Produce this
   fresh each cycle into local scratch (`.claude/scratch/`) -- do not commit the
   generated `.ics` file to the repo.** It's a disposable, per-cycle data
   artifact (real dates/times for that year's collection), not documentation; a
   committed copy from an earlier cycle would also invite reuse of stale dates.
   RFC 5545 structure to follow: `VCALENDAR` wrapping one `VEVENT` per reminder,
   **CRLF line endings** (not bare `\n`), balanced `BEGIN`/`END` pairs for both
   `VEVENT` and any nested `VALARM`, all-day items using
   `DTSTART;VALUE=DATE:YYYYMMDD` / matching `DTEND`, timed items using full
   `DTSTART:YYYYMMDDTHHMMSSZ` UTC timestamps, and a `VALARM` block
   (`ACTION:DISPLAY`, `TRIGGER:-P1D` or `-PT30M` style, its own `DESCRIPTION`)
   for anything that should pop a reminder rather than just sit on the calendar.
   Confirmed working structure (2026-2027 cycle, verified importing cleanly) --
   rebuild an equivalent file with that cycle's real dates rather than looking
   for a checked-in example.
3. **Import it into classic desktop Outlook** via **File → Open & Export →
   Import/Export → "Import an iCalendar (.ics) or vCalendar (.vcs) file."** **Do
   not double-click the file** -- on a machine where Microsoft's newer "New
   Outlook" (or the web client) is the default `.ics` handler, a double-click
   opens that client instead and offers to "add" the file as an entirely
   separate subscribed calendar feed rather than importing individual events --
   confirmed behavior, not a bug in the file. If double-clicking keeps doing
   this, it's a Windows default-app association (Settings → Apps → Default apps
   → `.ics`), not something to fix in the file itself.
4. **Edit each imported invite to add the Contact Group (Step 1) as attendees**,
   then send. The generated `.ics` intentionally has no `ATTENDEE`/`ORGANIZER`
   lines -- recipients get added per-invite, in Outlook, not baked into the
   file.

---

## Reference: Portal mechanics

Extracted from CSGF's Data Collection Portal User Guide (August 2026). Full
detail -- the 15 portal tasks, task statuses/types, Grid bulk-edit via Excel
export/import, task reassignment, support ticketing -- is in
[`references/portal-mechanics.md`](references/portal-mechanics.md). Read the
guide itself for anything not covered there.

---

## Reference: High School Data Collection (HSDC) mechanics

HSDC is a separate, DSA-gated submission that looks back one year. Read
[`references/hsdc-mechanics.md`](references/hsdc-mechanics.md) before any HSDC
work: Sheet vs. Portal split, front-loadable tabs, GPA cells, PII caution, and
the year-anchoring behind
[issue #4897](https://github.com/TEAMSchools/teamster/issues/4897).

---

## 2026-2027 cycle submission status

Tracking what CSGF has actually accepted, so a later reader doesn't re-verify
already-closed items. Update the date whenever a status changes.

- **Accepted by CSGF (confirmed 2026-09-22)**: Preliminary Questions, HS Grad
  Data, AP Scores, AP Offerings, SAT (the last four resubmitted after the
  `enroll_status` and `total_graduates` fixes -- see PR #5275 -- and after the
  studentid `100034` GPA correction was applied to the official sheet), and
  Kevin's Org Staffing Data.
- **Still open**: everything else on the per-person split above (Schools List
  fields still needed from Laz, the shared School Enrollment task, Discipline,
  Finance, etc.) -- check each owner directly rather than assuming acceptance
  carries over between tasks.

---

## Known data risks -- verify before submitting

Full forensic detail (SQL evidence, exact row counts, what was fixed and when,
per-model naming/scope quirks) is in
[`references/known-data-risks.md`](references/known-data-risks.md). Read it
before assuming a fix has landed in prod or that a past finding still applies
unchanged -- a fix landing on a PR branch is only live once that PR merges AND
kipptaf redeploys (confirm via `mcp__dagster__get_location_load_history` before
treating a documented fix as submission-ready).

**Still-open items to check before submitting, as of 2026-09-23:**

- **`total_budgeted_enrollment` is NULL for every row in `csgf_enrollment`** (24
  schools as of 2026-09-23; re-check the row count, it moves) --
  `stg_google_sheets__topline_enrollment_targets` has no 2026 rows yet for any
  district. Not a collection-owner task; escalate to whoever owns the "Topline
  Enrollment Targets" sheet.
- **Miami's first HS (AY2026) is a forward risk for next cycle, not this one**
  -- next cycle's HS-scoped models will need a Focus course/grade source wired
  into two PowerSchool-only CTEs before they can cover Miami.
- **`rpt_gsheets__csgf_hs_ap_offerings`/`hs_ap_scores` need a coverage/naming
  re-check every cycle** against CSGF's current official AP course name list
  (last checked 2026-09-11, clean).
- **`rpt_gsheets__csgf_hs_postsec_pathways` can emit more than one row per
  student per year** -- routed to Casey Gibson to decide, not yet resolved.
- **School names need an ask-and-confirm check every cycle** against CSGF's
  current official school-name list.

## How the dbt models actually reach CSGF (answered)

The eight `rpt_gsheets__csgf_*` models write out to a KTAF-owned Google Sheet
titled
[**"CSGF Data"**](https://docs.google.com/spreadsheets/d/1rbPI03qTMMv3NVC1_1rjodBq3Cd8mktd5Fwosy2AxuM/edit),
one tab per model (`Enrollment`, `HS Grad Data`, `HS Enrollment`, and the
remaining five). **This is not CSGF's HSDC workbook** -- it's an internal
staging sheet the collection owner reads from to fill CSGF's actual systems.
Several HS tabs (e.g. `HS Enrollment`) carry real student-level rows -- same PII
caution as the HSDC workbook: fine to reference structure/column names here,
never row-level content.

**How the transfer from this sheet into CSGF's systems happens has changed cycle
to cycle -- don't assume last year's method still applies:**

- **2025-2026 cycle:** no bulk-import existed in the Salesforce Portal, so the
  collection owner copy-pasted each cell manually from "CSGF Data" into the
  Portal.
- **2026-2027 cycle:** the Portal's new Excel export/import feature (see Portal
  mechanics above) makes bulk upload possible. Plan: reorder "CSGF Data"'s
  columns/tabs to match each Salesforce grid's Excel template column order, so
  the data can be copy-pasted directly into that template and bulk-uploaded,
  instead of cell-by-cell entry. Confirm this reordering is actually completed
  each cycle before relying on it -- it's a manual alignment step, not
  automatic.

## Ad hoc CSGF surveys outside the Portal/HSDC

For a one-off CSGF Google Form survey sent by email, read
[`references/ad-hoc-surveys.md`](references/ad-hoc-surveys.md) (includes the
2026-2027 Florida B.E.S.T. Algebra 1 worked example).

## Open questions for this skill (not yet answered)

- Who is the current collection owner / project manager, for reference the next
  time this skill needs updating?

<!-- Next steps to capture: Salesforce Portal account setup/verification,
working through the rest of the item list, ongoing review / Ready for Review
workflow, internal deadline check-in, panic week, official submission,
audited-data follow-up in January, more Preliminary Questions as they're
pasted. -->
