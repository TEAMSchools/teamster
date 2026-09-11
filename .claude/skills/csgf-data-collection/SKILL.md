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
  -- where all eight `rpt_gsheets__csgf_*` dbt models land, one tab per model.
  This is KTAF's internal staging sheet, not CSGF's own HSDC workbook -- see
  "How the dbt models actually reach CSGF" below for how data moves from here
  into CSGF's actual systems. Several tabs carry real student-level rows -- same
  PII caution as the HSDC workbook.

**CSGF-provided:**

- [CSGF Data Collection Portal User Guide](https://docs.google.com/document/d/1V5LBa--mKLZC2PSd9ptEVSQSoj-4YUHWznPyPu62A6M/edit?tab=t.0)
  (dated August 2026) -- see "Portal mechanics" and "HSDC mechanics" below for
  the extracted contents.
- [CSGF Data Collection Field Definitions](https://docs.google.com/spreadsheets/d/1hpMLqeFcci_Epar3InHRB8UXly7ZLg42vzjgANUpzP8/edit?gid=963005787#gid=963005787)
  -- CSGF's own field-by-field definitions. Full extraction with structural
  gotchas: [`reference/field-definitions.md`](reference/field-definitions.md).
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

**Preliminary Questions log** (question, this cycle's answer, how it was
verified -- carry forward and re-verify each cycle rather than assuming the
answer repeats). Entries 2-6 (the "Academic Profile & Grading" subsection) are
marked **[final -- confirmed against the collection owner's actual portal
submission]**; entry 1 is unconfirmed against the portal but derived the same
way.

1. **"Did you operate high schools last year?"** → **Yes** (2026-2027 cycle).
   Verified via `rpt_gsheets__csgf_hs_enrollment` (prod, schema
   `kipptaf_extracts`): KIPP Cooper Norcross High (Camden, 444 students), KIPP
   Newark Collegiate Academy (770), KIPP Newark Lab High School (496), all for
   AY2025 (the 2025-2026 school year). Miami and Paterson have no HS enrollment
   and are correctly absent.

2. **"Did your school or network administer the SAT, ACT, or both to any
   students last year?"** → **SAT**. `rpt_gsheets__csgf_hs_sat` has 1,590 rows
   for AY2025; `rpt_gsheets__csgf_hs_act` also has 15 rows, but per the
   `carat-dashboard` reference doc, KTAF's assessment strategy is SAT-based --
   those 15 ACT scores are students who took the ACT independently and had the
   score recorded, not something the network administered. The question asks
   what _we_ administered, not what data exists -- don't answer "Both" just
   because both tables have rows.

3. **"Did any of your schools offer AP courses last year?"** → **Yes**.
   `rpt_gsheets__csgf_hs_ap_offerings` has one row per school with a column per
   AP course, valued with the grade level(s) it's offered to (not a boolean) --
   all three HS schools have at least one non-null AP course column for AY2025
   (e.g. KIPP Newark Collegiate Academy offers AP Biology, AP Calculus AB, AP US
   History, and AP Computer Science Principles).

4. **"Did any of your schools offer AP tests last year?"** → **Yes**.
   `rpt_gsheets__csgf_hs_ap_scores` has 1,221 rows for AY2025.

5. **"Are GPAs weighted?"** → **Yes**. In `rpt_gsheets__csgf_hs_enrollment`, 680
   of 1,710 AY2025 students have
   `weighted_cumulative_gpa != unweighted_cumulative_gpa` -- the weighted column
   is a real, distinct calculation, not a duplicate of unweighted.

6. **"What is the grading scale?"** → KTAF uses a plus/minus-based GPA point
   scale: regular (unweighted) courses cap at **4.33**, advanced/honors
   (weighted) courses cap at **5.33**. **Correction from an earlier pass of this
   log**, which flagged this question as unanswerable from a
   `rpt_gsheets__csgf_*` report -- true, but there's a different verifiable
   source: business-rule documentation, not a CSGF report. Confirmed two ways:
   (a)
   [`src/dbt/kipptaf/models/students/CLAUDE.md`](../../../src/dbt/kipptaf/models/students/CLAUDE.md)
   documents these exact caps for the KTAF GPA Band rules; (b)
   `stg_powerschool__storedgrades.gpa_points` for AY2025 Y1 grades has
   `max = 5.33, min = 0`, matching. **Lesson for this skill's verification-first
   rule**: "not a CSGF report" and "not verifiable" are not the same thing --
   check subdirectory `CLAUDE.md` business-rule docs (e.g.
   `models/students/CLAUDE.md`) before concluding a question is
   institutional-knowledge-only.

**"Alumni Data" subsection** -- paid-subscription questions are procurement
facts, not data-population facts. dbt integration presence/absence is
corroborating evidence at best, never proof -- confirm with whoever manages each
vendor contract rather than answering from data alone:

**7.** **"Does your organization have a paid subscription for Overgrad?"** →
**Yes** [confirmed]. Matches the data lead: a full dedicated `overgrad` dbt
package with a live API integration, wired into both Camden's and Newark's
`packages.yml`.

**8.** **"Does your organization have a paid subscription for National Student
Clearinghouse (NSC)?"** → **Yes** [confirmed]. The data lead
(`stg_google_sheets__kippadb__nsc_crosswalk`, a maintained college-to-NSC-code
reference sheet) pointed the right direction but wasn't proof by itself --
confirmed by the collection owner.

**9.** **"Does your organization have a paid subscription for Naviance?"** →
**No** [confirmed, per last cycle]. Matches the data lead (zero Naviance
integration anywhere in the dbt codebase) -- but note this cycle's item-list doc
dropped the "N/A" flag on the Naviance HSDC tab that last cycle's doc had. That
flip is still unresolved; re-confirm for the current cycle rather than assuming
"No" carries forward automatically.

**10.** **"What is your means of collecting the post-high school plans of your
graduating seniors?"** (multi-select) → **[confirmed]** Selected: **Senior
Seminar/Class Requirement, Overgrad, Other**. Confirmed NOT selected:
**Naviance** (item 9's no-subscription answer). The remaining options on the
full 10-item list (1:1 Counseling/Advising Meetings, Cialfo, Internal
Tracker/Spreadsheet, National Student Clearinghouse (NSC), Scoir, Student
Information System (SIS)) were not called out as selected, so treat them as not
selected unless told otherwise.

**11.** **"If you have NSC/Naviance/Overgrad AND ALSO utilize additional
mechanisms for keeping track of alumni, what are they?"** → **Salesforce**
[confirmed]. Free text, no dbt data source -- this is exactly the kind of
question the verification-first rule can't help with; it was answered directly
by the item owners.

**"Gateway Math Information" subsection** (gateway math = Algebra I at KTAF --
no `rpt_gsheets__csgf_*` report covers this domain, so every answer here came
from raw PowerSchool course-enrollment/NJSLA queries, not a CSGF report):

**12.** **"What gateway math course(s) do you offer?"** → **Algebra 1**
[confirmed]. The course catalog only has Algebra I variants; "Integrated
Mathematics I" / "NC Math 1" only appear in the CSGF HS enrollment model's
_transfer-student_ course-name catch list (matching incoming credits from other
states) -- not something KTAF itself teaches. Don't let that list suggest
Integrated Math is offered.

**13.** **"In what grade is gateway math typically first offered to students?"**
→ **8th** [confirmed] -- **my first answer here was wrong ("10th"), and the
reason is a durable lesson, not a one-off mistake.** I queried HS-scoped (grades
9-12) AY2025 course enrollment and saw ~114 students in Algebra I variants at
grade 9 vs. ~479 at grade 10, and concluded "10th." Two compounding errors: (a)
the query never looked at grade 8 at all, so it structurally couldn't see the
actual first-offered grade; (b) even within 9-12, the 9th-grade Algebra I count
is not the "first attempt" population -- students who pass Algebra I in 8th
grade and stay at KTAF never re-enroll in it in 9th, so the students left
showing up as 9th-grade Algebra I are disproportionately non-passers and
new-to-KTAF transfers, not a representative first-attempt cohort. **Lesson for
the verification-first rule**: before answering "what grade/when does X
typically happen," check whether the query's scope (a report or extract limited
to HS, or to one academic year) actually covers the full population the question
is about, and whether an observed count could be skewed by survivorship (people
who succeed early leave the population you're counting) rather than reflecting
the typical pathway.

**14.** **"What math course do most students take immediately before gateway
math?"** → **Math 8** [confirmed] -- matches the "Math Gr8" course found in the
data (two name variants, one with a trailing space -- still worth flagging as a
catalog cleanup item separately from this submission).

**15.** **"How does your organization define a student as having passed gateway
math?"** → **Earning Course Credit** [confirmed] -- a passing course grade, not
a separate proficiency exam or standardized cut score. (The dbt-side
`passed_algebra_i` field that used to compute this inference was later removed
as dead code -- see the AP/Algebra cleanup in `rpt_gsheets__csgf_hs_enrollment`
-- so this answer stands on the underlying course-credit definition, not on that
column's continued existence.)

**16.** **"Does your organization use a state-administered end-of-course exam
for gateway math?"** → **Yes** [confirmed]. Matches `stg_pearson__njsla`'s
dedicated "Algebra I" subject rows.

**17.** **"Does your organization use credit recovery or summer school to
support gateway math passage?"** → **Yes** [confirmed] -- the data lead (a
generic, subject-untagged "Summer School" course) was suggestive but not proof
by itself; confirmed by the item owners.

**This closes out the Preliminary Questions task for the 2026-2027 cycle** -- 17
questions total across four subsections (base, Academic Profile & Grading,
Alumni Data, Gateway Math Information). **CSGF has reviewed and accepted these
answers** -- task status should read Completed, not just Ready for Review.
Re-run this whole log next cycle rather than assuming answers carry forward --
several entries above changed between cycles on their own (the Naviance N/A
flag, the item-list ownership split) even when the underlying fact didn't.

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

**Lesson: a walkthrough video is a generic/dated overview; the task's own
in-portal instructions are the live, specific source.** When the two disagree,
trust the task text open in front of you, not what a linked video said it would
say. Don't assume a video accurately describes current-cycle behavior just
because it's linked from this cycle's Portal User Guide.

**Working a real missing-school case (2026-2027 cycle: KIPP Legacy Elementary,
KIPP Legacy Middle, KIPP Miami Technical High), what actually worked:**

- **Export mechanics, confirmed live.** Click **Export** on the grid toolbar
  (next to Reload/Freeze/Import/Edit/Update/Reset) -> a dialog offers CSV, Excel
  File, or Formatted Excel File. Pick **Excel File**. Leave both toggles off
  (**"Do not export record Id(s)"** and **"Export only selected records"**) --
  you need the record Ids for reimport to update rather than duplicate, and you
  need every row, not a subset. Rename away from the default `List Export`
  filename, then click Export.
- **`State/Province` displays as the full state name in the live grid**
  (`New Jersey`, `Florida`), not the two-letter abbreviation -- match that in
  any row you add or edit, not `NJ`/`FL`.
- **The working loop with Claude**: export the file, open it, copy the entire
  sheet (header row plus every data row), and paste that as plain text into the
  chat -- pasting straight from Excel without "paste as plain text"
  (`Ctrl+Shift+V`/`Cmd+Shift+V`) often inserts an image instead of usable text.
  Claude appends the new schools' rows and rewrites the header row to the real
  import-mapping field names (see below), leaving every existing row's data
  untouched. Paste that back into the same Excel file (replacing its contents),
  format the NCES ID and ZIP/Postal Code columns as Text first (Excel mangles
  long digit strings and leading zeros otherwise), then Import.
- **Import cannot create the new rows -- confirmed twice.** Per the Portal
  Guide's own Export/Import section: "You cannot add any new rows as the import
  is only to update the records." A real submission attempt using CSGF's own
  "Schools List Mapping" import template proved this isn't just the Guide's
  wording -- it failed all 3 new-school rows with
  `MISSING_ARGUMENT:Id not specified in an update call`. That template's
  underlying operation is update-only regardless of what the Validation screen's
  `Operation` field displays (it showed `Insert` in an earlier, different
  attempt). **Sequence has to be Add Record (creates the bare row with a real
  Id) first, then export the now-larger grid, fill in field values, reimport.**
- **Add Record works, but it's manual, one school at a time, and slow** --
  confirmed live for the 2026-2027 cycle (KIPP Legacy Elementary added this
  way). Click **Add Record** on the grid toolbar, hand-enter values into the new
  blank row's fields (it accepts pasted text per field, not a pasted
  multi-column row), then repeat per school. There's no bulk-create path; budget
  time for this per missing school.
- **In the grid's edit mode, a copied value can be pasted down multiple rows of
  the same column at once** -- select the rows for that column and paste; this
  is real and confirmed, distinct from the field-by-field entry Add Record
  itself requires. Useful for values every new-school row shares
  (`Country/Territory`, `Geographic District`, etc.) once the bare records exist
  and you're filling in the rest of their fields.
- **Schools List doesn't have to fully close before moving on to Step 6.** Once
  the bare records exist, tag Laz asynchronously for the remaining fields and
  proceed -- don't block the whole collection on his availability. Carry the
  open items into Step 6's item-list doc as one of the "open questions" it's
  meant to hold before sharing.
- **Status as of 2026-09-11: all 3 bare records added** (KIPP Legacy Elementary,
  KIPP Legacy Middle, KIPP Miami Technical High) via Add Record. **Still needs
  Laz to review and enter the remaining data** -- specifically the fields this
  session confirmed have NO source anywhere in the codebase (checked
  `int_finance__enrollment_targets` and `int_tableau__fresh_goals_scaffold`,
  both ruled out for seat capacity): `Total Seats at Full Scale`, `School Model`
  (+ Notes), `Facility Ownership Type`, `Lease Term Including Extensions`,
  `Facility Serve Long Term Needs`, `New Lease/Building in 2 Years`,
  `Real Estate Financing in Calendar Year` (+ Amount Financed, Lenders). These
  need direct input from Laz/the schools, not more codebase digging.
- **`int_students__schools` is the source of truth for whether a school exists**
  -- not `int_extracts__student_enrollments`'s year range. A school having no
  enrollment history before the current year does NOT mean it's newly opened;
  Miami's Focus cutover already destroys history for reasons unrelated to when a
  school actually opened. Don't infer "new vs. long- standing" from
  enrollment-extract year ranges -- check `int_students__schools` for existence,
  and check the school's own public page (below) for its actual founding year.
- **State School ID encodes a shared charter number, not a per-school code.**
  Format is `[FL district code]-[charter number]` (e.g. `13-2332`). Focus's own
  `school_number` (`custom_327`, e.g. `2332C`) reveals the grouping: the letter
  suffix is the campus, the number prefix is the charter. KIPP Miami runs (at
  least) two charters -- `2332` (Royalty, Courage, Miami Tech, and the closed
  Liberty) and `2008` (Legacy Elementary, Legacy Middle, and the closed
  Sunrise). Confirmed against CSGF's existing Portal record: Royalty and Courage
  (both charter `2332`) share the exact same `13-2332` code.
- **`stg_google_sheets__people__locations.address`/`postal_code` are null for
  every Miami row**, not just newly-added ones -- confirmed by checking Royalty
  and Courage, which have real known addresses. This is a real gap in that sheet
  for the whole region, not something to keep re-checking per school. **The real
  source is Focus's own raw dlt table**, under custom-field codes, not yet
  staged into any dbt model:
  `dagster_kippmiami_dlt_focus.schools.custom_200000319` (Address) and
  `custom_200000322` (Zipcode). Decode any other missing school attribute the
  same way: `dagster_<district>_dlt_focus.custom_fields` filtered
  `source_class = 'SISSchool'`, matched on `title`.
- **Cross-check against the school's own public page**
  (`kippmiami.org/kipp- <slug>/`) before trusting either internal source alone
  -- it independently confirmed both the Focus addresses AND surfaced a real
  typo in CSGF's existing Portal record for Royalty/Courage
  (`300 NW 110th Street`, missing a digit vs. the real `3000 NW 110th Street`).
  The same pages also carry each school's founding year ("20XX FOUNDED" in their
  key-facts section), which answers "did this school open this cycle" -- but
  that's not the same as having a value for the `Academic Year Opened` column
  itself.
- **`Academic Year Opened`/`Academic Year Closed` are Salesforce lookup IDs, not
  text.** The column holds an opaque record ID (`9TPa5000000FbZvGAK` style).
  There's no way to derive the right ID for a school year that isn't already
  used by an existing row (the sheet only goes up to `2025-2026`), so leave the
  ID column itself blank and pick the year from the Portal's own dropdown --
  don't fill in the literal year text there, that's an invalid value for an ID
  field. The adjacent `* Name` column, despite reading as a calculated display
  value, DOES accept the literal year text directly (`2026-2027`) -- fill that
  one in.
- **Excel silently mangles NCES ID / State School ID / ZIP on paste** if the
  destination column isn't formatted as Text first -- large all-digit strings
  and leading zeros get eaten by Excel's automatic number conversion. Fix is
  formatting the destination cells as Text before pasting, not a leading
  apostrophe in the value itself.
- **Excel does the same thing to date-looking values, and it's a real
  submission-breaking error, not just a cosmetic one.** Confirmed from an actual
  error-report CSV: pasting `2026-07-01` into `Next Charter Renewal Date` and
  `2025-07-01` into `Date of Takeover, Merger, or Turnaround` silently became
  the underlying Excel serial-date integers (`46204`, `45839`) on every row that
  had one, and Salesforce rejected every single one on import with
  `INVALID_FIELD:'<serial>' is not a valid value for the type xsd:date`.
  **Format every date column as Text too, before pasting -- not just NCES
  ID/State School ID/ZIP.** Given this hit every row with a date value, the
  safer instruction for next cycle is to format the ENTIRE destination sheet as
  Text before pasting anything back in, rather than trying to enumerate every
  column that needs it.
- **Confirmed live (2026-2027 cycle): the exported file's own header row does
  NOT work for reimport.** The Portal Guide's "columns must appear in the same
  order with the same headings as when you exported it" describes the export
  step only -- it does not mean those header strings are valid import field
  names. Re-uploading a file with the export's own headers unchanged fails to
  map (no interactive prompt catches this -- it just doesn't work, which reads
  as "Salesforce isn't asking for renames" but actually means the mapping
  silently didn't happen). **The header row has to be replaced with the real
  field names from the import screen's own dropdown before reimporting** --
  expect this every cycle, not just once. Several names genuinely differ from
  the exported header:
  - `Administered NWEA MAP?` -- exported header, but the import dropdown only
    offers **`Did school give NWEA MAP?`**
  - `Administered iReady?` -- import dropdown: **`Did school give iReady?`**
  - `Additional Context` -- import dropdown:
    **`Takeover, Merger, or Turnaround Context`**
  - `Id` -- import dropdown: **`Record ID`** (a separate `AIM School Id` also
    exists -- that's a different, external-system id, not this one)
  - `Submission Status` -- ambiguous: the dropdown offers `Data Status`,
    `School Budget Status`, `School List Submission Status`,
    `School List Verification Submit Status`, and `School Status` as separate
    fields. Untested guess: `School List Submission Status` (name-matches the
    task), but this needs confirming against a row you know the true value for.
- **2026-2027 AP course name list, pasted directly from the Portal task
  (2026-09-11) -- diffed against the pivot's 28 columns.** 3 naming-drift hits,
  all College Board's old "AP Studio Art" naming vs the current names: pivot has
  `AP Studio Art: 2-D Design Portfolio` / `3-D Design Portfolio` /
  `Drawing Portfolio`; CSGF's current list says `AP 2-D Art and Design`,
  `AP 3-D Art and Design`, `AP Drawing`. Harmless as-is (the exported column is
  a snake_case alias a human matches by meaning, not exact string, and none of
  the 3 are currently taught anyway) but fix the crosswalk/pivot naming if any
  school ever offers one. Real missing-column gaps (no pivot column exists at
  all): Chinese/German/Italian/Japanese Language and Culture, Latin, European
  History, Music Theory, Physics 2, Physics C (Electricity and Magnetism /
  Mechanics), AP Research -- none currently taught (confirmed against AY2025
  actual course data), so no live impact this cycle, but any of these
  newly-offered in a future cycle would silently drop per the Coverage risk
  above. (Calculus BC: AB Subscore and the two Music subscores are scoring
  artifacts, not real course offerings -- not gaps.)
  - `Street Address` / `City` / `State/Province` / `ZIP/Postal Code` /
    `Country/Territory` -- each of these has TWO candidates in the dropdown: a
    bare legacy field (`Street Address`, `City`, `State`, `Zip Code`) and a
    compound `School Address (...)` field. **`Country/Territory` only has the
    compound option** (`School Address (Country/Territory)`, no bare equivalent)
    -- since Salesforce compound address fields always group
    Street/City/State/Zip/Country/Lat/Long together as one field, that's good
    evidence the compound `School Address (...)` set is the real, current field
    and the bare ones are legacy/deprecated. Untested; confirm by checking which
    one actually holds a value on an existing row before trusting this for a
    real submission.
  - Every other exported header matched its import-dropdown name exactly (School
    Name, State School ID, NCES ID, Geographic District (+`:District Name`),
    Total Seats at Full Scale, School Model (+ Notes), Takeover/
    Merger/Turnaround?, School Operation Type, Date of Takeover..., Academic
    Year Opened/Closed (+ `:Name` each), Next Charter Renewal Date, Authorizing
    District or Entity, Authorizing Entity Type, Facility Ownership Type, Lease
    Term Including Extensions, Facility Serve Long Term Needs, New
    Lease/Building in 2 Years, Real Estate Financing in Calendar Year, Total
    Amount Financed for Real Estate, Lenders of Real Estate Financing) -- don't
    assume a mismatch on those just because of the ones above.
  - **Before trusting any of this next cycle, re-check the live import mapping
    dropdown yourself** -- Salesforce object fields get renamed/added across
    cycles same as everything else CSGF touches, and this list was captured
    against the 2026-2027 Schools List object specifically.

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
  [`reference/kickoff-slack-template.md`](reference/kickoff-slack-template.md)
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
   dates from the item-list doc's Context section -- see Step 3). Worked example
   from the 2026-2027 cycle, with correct RFC 5545 structure (CRLF line endings,
   balanced VEVENT/VALARM blocks) to use as a reference:
   [`reference/outlook-invites-2026-2027.ics`](reference/outlook-invites-2026-2027.ics).
   Regenerate fresh each cycle with that cycle's real dates -- don't just reuse
   the old file's dates.
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

Extracted from CSGF's Data Collection Portal User Guide (August 2026). Read the
guide itself for anything not covered here.

**The 15 portal tasks** (complete Preliminary Questions, Schools List, and
Growth Plans first -- they inform what other tasks prompt for): Preliminary
Questions, Schools List, Key Contacts, Enrollment, Discipline, School Finance,
Org Finance, Growth Plans, Org Staffing Summary, Org Info Questions, Org Chart
Upload, Budget Upload, Bank Info Verification, Officer Cert, Data Summary.

**Task statuses:** Not Started → In Progress → Ready for Review → Completed, or
Further Edits Needed if CSGF finds an error on review. Not Applicable / Not
Available / Canceled are CSGF-only-settable (if one of these looks wrong on your
task, submit a support ticket rather than trying to change it yourself). Moving
to "Ready for Review" happens automatically in most cases once required
fields/errors are cleared -- **except HSDC tasks**, which you set manually.

**Task types:** Grid (spreadsheet-style, per-field validation), Flow (guided
multi-screen), Survey (fixed questions), or a mix.

**Grid bulk-edit via Excel export/import** (this applies to the main Portal
grids -- NOT the HSDC Google Sheet, see the caution in HSDC mechanics below):

- Export defaults to Excel format -- keep it that way (don't switch to CSV);
  keep "Do not export record Id(s)" toggled off (default) since you need the IDs
  to re-import.
- Re-import requires: same column order/headers as the export; the `status`
  column left blank or "In Progress" (changing it to "Submitted" in the file can
  break the upload -- use the portal's Submit button instead); no new rows added
  (import only updates existing records -- request new records via a support
  ticket); file must be `.xlsx`, not `.csv`.
- Some fields (e.g. Academic Year Opened/Closed on Schools List) can't be
  mass-updated via import -- expected, not an error.
- Monitor import results via the "GM - Import Monitor" tab (bottom left); errors
  are downloadable as a CSV.

**Reassigning a task to someone else:** the target person needs "Data Collection
Participant = Yes" on the Key Contacts grid **and** an existing portal login, or
they won't appear in the assignee picker. Reassign from My Tasks → click the
task name → pencil icon next to Assigned To.

**Support:** portal → More → Support → describe the issue and pick a category.
Email confirmation on submission; CSGF typically responds within 1-2 business
days.

**Additional CSGF resources** (all new to the 2026-2027 cycle per the item list
doc): a
[full data-fields list](https://docs.google.com/spreadsheets/d/1yPT8M_2sAHdvlLL6SFM5XZICSjsUiFxJOGYz2tP3CBI)
and a sample all-in-one template; walkthrough videos are linked from the guide
and from the Salesforce Portal home page (bottom left).

---

## Reference: High School Data Collection (HSDC) mechanics

HSDC is a **separate submission** from the main Portal collection, gated on
signing that cycle's Data Sharing Agreement (DSA). In exchange, KTAF gets access
to cross-network benchmarking and trend analysis across 85+ charter networks in
the CSGF High School Data Collaborative.

**"HSDC looks back one year"** -- CSGF's own wording. The 2026-2027 HSDC
submission covers the 2025-2026 school year: every high school student who
completed that year at a KTAF high school. This is the CSGF-sourced explanation
for the year-anchoring inconsistency across the `rpt_gsheets__csgf_*` models
that [issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) flags --
worth citing verbatim in the eventual `docs/models/csgf-data-model.md` ref doc.

**Elements**, split across two systems, but **all task statuses tracked in the
Portal regardless of where the data entry happens**:

- _Google Sheet_ (data entry happens here): Enrollment, ACT, SAT, AP Offerings,
  AP Scores, Intended Postsecondary Pathways, Naviance/Overgrad/ Other
  Application Results, plus two **Round 2 (winter)** tabs -- Verified 2/4-Year
  College Matriculation and the College Data/National Student Clearinghouse
  export, both due "early" the following year, after the main submission window.
- _Portal_ (task tracking + a couple of data-entry tasks): Preliminary
  Questions, High School Grad Data, DSA Signature.

**Front-load the tabs whose underlying data is already closed.** Per the year
anchoring in "Known data risks" below: 5 of the 8 `rpt_gsheets__csgf_*` models
(Enrollment, SAT, ACT, AP Offerings, AP Scores) read only
`current_academic_year - 1` -- last cycle's finalized school year, which cannot
change. HS Grad Data is scoped to the current cohort (a fixed number known well
in advance, not something that becomes true only after a future date), so it's
computable now too. Postsecondary Pathways is unfiltered and already correctly
reflects every completed cohort. That's 7 of 8 tabs computable the moment
Preliminary Questions is done and the Sheet is accessible, with no need to wait
for the internal deadline crunch. Only the main Portal `csgf_enrollment` model
(current-year enrollment counts, and the current-year side of its retention
calc) is genuinely blocked -- it needs this year's Oct 1 count day to happen
first.

**The collection window CSGF actually opens and the date communicated to the
team don't have to match.** It's fine (and was done deliberately this cycle) to
tell the team a later "official" start date than when the Portal/Sheet actually
became accessible, as a buffer so people don't feel rushed. As collection owner,
check actual access yourself rather than trusting the communicated date, and use
the gap to get a head start on the 7 already-closed tabs above.

**Working the Sheet:**

- Start with the **Enrollment tab** -- every student on any other tab must also
  have an Enrollment row, and vice versa (every completer goes on Enrollment
  even if they don't appear elsewhere).
- Fill the min/max weighted and unweighted GPA cells (K4/L4 in CSGF's template,
  labeled "Numeric value between 0 and your max Unweighted/Weighted GPA") --
  leaving them blank flags ALL GPA data as errors, not just those cells. These
  are the same values as the "grading scale" Preliminary Question (Q6 in that
  log, above): **unweighted max = 4.33, weighted max = 5.33**. Confirm these
  haven't changed each cycle rather than assuming they carry forward.
- Tasks marked "Not Applicable" by your Preliminary Questions answers should
  stay that way -- if one looks wrong (e.g. stuck on "Not Started" when it
  should be N/A), file a support ticket rather than editing the status yourself.
- Use the **"Data to Review" tab** to find and fix validation errors before
  moving a task to "Ready for Review" -- it lists student ID, total error count,
  and which tab/column each error is on. Fixes may take a few moments to clear
  (hidden formulas need to recompute).

**Two cautions specific to this cycle's actual sheet:**

1. **Do not download to Excel and do not make a copy.** CSGF's instructions for
   the HSDC workbook explicitly say to edit it in place in Google Sheets -- this
   is the opposite of the main Portal grids' Excel export/import workflow above.
   Downloading/copying breaks the template's built-in validation and formulas.
2. **This sheet's own "Status Key" section looks internally inconsistent** with
   the definitions given in the Portal User Guide -- e.g. it defines "Completed"
   as "unable to complete the College Data template due to not have enough years
   of alumni" and "Not Applicable" as "unable to complete the Graduate and
   Postsecondary-related data sheets" -- neither matches the Portal Guide's
   actual status definitions ("Completed" = reviewed, no errors found). This
   reads like CSGF's own sheet has shifted/mismatched rows in that section. Go
   by the Portal User Guide's status definitions, not this sheet's Status Key,
   and don't silently "correct" the source when citing it.

**PII caution:** once populated, this sheet holds real student-level records
(enrollment, test scores, application results). Don't read its full content into
any process that could put that data somewhere it doesn't belong (a commit, an
issue, a doc, a chat). To check something about the data, prefer querying the
corresponding `rpt_gsheets__csgf_*` dbt model (aggregate-level) over reading the
live CSGF sheet directly.

---

## Known data risks -- verify before submitting

**Year anchoring across the eight `rpt_gsheets__csgf_*` models** (verified by
reading each model's SQL directly, not just taken from prior notes -- see
[issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) for the
original observation this confirms):

| Model                      | Years of data referenced                                                                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `csgf_enrollment`          | **Both** -- grain is this year (`current_academic_year`), but `retention_numerator`/`retention_denominator` pull last year's enrollment too via a self-join |
| `csgf_hs_enrollment`       | Last year only (`current_academic_year - 1`)                                                                                                                |
| `csgf_hs_sat`              | Last year only                                                                                                                                              |
| `csgf_hs_act`              | Last year only                                                                                                                                              |
| `csgf_hs_ap_offerings`     | Last year only                                                                                                                                              |
| `csgf_hs_ap_scores`        | Last year only                                                                                                                                              |
| `csgf_hs_grad_data`        | Current cohort only (`cohort = current_academic_year`) -- fixed this cycle, see below                                                                       |
| `csgf_hs_postsec_pathways` | **All years** (unfiltered) -- `academic_year` is a plain passthrough column with no `WHERE` on it at all                                                    |

Practical consequence: a Miami (or any region) data problem in _either_ the
current or prior year can affect `csgf_enrollment`; a problem in _any_
historical year can affect `csgf_hs_postsec_pathways`, the one remaining
unfiltered model. It also means 7 of the 8 models are computable the moment
Preliminary Questions is done, without waiting on anything about the current
in-progress year -- see "Front-load the tabs" in the HSDC mechanics section
above.

**`csgf_hs_grad_data`'s cohort scope, resolved.** It used to have a real cohort
filter sitting in a dead `graduated` CTE the final `SELECT` never referenced, so
the live query returned every cohort ever recorded -- one school alone had 20
rows (cohorts 2011-2030) instead of one. CSGF's own Salesforce Portal task
purpose settled this: the task calculates the 4-year graduation rate for the
cohort expected to graduate the current year, one row per school, with an
explicit instruction to leave rows blank for a school with no 12th graders that
year -- not one row per cohort ever recorded. Fixed by moving the filter onto
the live query path and removing the dead CTE. See
`docs/models/csgf-data-model.md` for the full writeup. Its `school` output also
used to be abbreviated codes (`KHS`/`NCA`/`NLH`) -- fixed to full names
(`KIPP Newark Lab High School` / etc.), confirmed against CSGF's Portal task
labels.

**Both fixes above are only in PR #5059 (this branch), not yet in prod as of
2026-09-11.** Confirmed live: prod's `rpt_gsheets__csgf_hs_grad_data` (a VIEW,
last recreated 2026-07-17 per `__TABLES__.last_modified_time`) still outputs the
old abbreviated codes -- `git branch --contains` on the fixing commit
(`b7344ed8b`) shows only this PR's branch, and `origin/main`'s copy of the file
is still the pre-fix version from 2025-10-08. A view re-executes live but
against its own STORED definition, which only updates when Dagster recreates it
after a deploy -- so this won't self-correct by waiting. **Don't treat this
model as fixed for the actual submission until #5059 merges and kipptaf
redeploys** (confirm via `mcp__dagster__get_location_load_history` showing a
`LOADED` entry with the merge commit's hash, same check as any prod-deploy
verification).

**`rpt_gsheets__csgf_enrollment` currently under-reports Miami** (as of this
cycle -- owner is aware and fixing separately from this skill; check whether
it's still open before relying on this note). The model is driven by
`stg_powerschool__schools`, a frozen PowerSchool-era Miami school catalog that
was never updated after Miami's cutover to Focus as its SIS. Concretely:

- Two Focus-marked-`(Closed)` schools (Sunrise, Liberty) still appear in the
  catalog and show up in the extract with every enrollment/demographic column
  null.
- Three schools with real, currently-enrolled Focus students are silently
  **missing** from the extract entirely (not null -- absent rows), because the
  join to the stale catalog fails: KIPP Miami Tech (95 HS students), KIPP Legacy
  Elementary (173 students), KIPP Legacy Middle (32 students) -- roughly 300 of
  Miami's ~1,755 enrolled students, about 17% of Miami, invisible to this
  report.
- This is unrelated to the placeholder-row/Focus-cutover issue documented in
  `src/dbt/kipptaf/CLAUDE.md`'s "Known Upstream Issues" (that one is about the
  enrollment spine correctly losing synthetic continuity rows) -- this is a
  stale school directory, a distinct problem.
- **Before submitting Miami's enrollment numbers to CSGF**, cross-check the
  extract's Miami school list against Focus's actual current roster (5 active
  buildings as of this cycle: Courage, Royalty, Miami Tech, Legacy ES, Legacy
  MS) rather than trusting the extract's row count at face value.

**Fixed (2026-09-11, this branch): `rpt_gsheets__csgf_enrollment` now sources
Miami from Focus instead of the frozen PowerSchool catalog.** Added a
`focus_schools` CTE (`int_focus__schools` joined to
`stg_google_sheets__people__locations`, filtered `school_level is not null` --
confirmed this correctly excludes Sunrise/Liberty, since Focus itself nulls
their level on closure, and also excludes 2 non-school placeholder Focus records
that happen to share the same null). Rebuilt in dev and confirmed all 5 real
Miami schools now appear with real enrollment counts and real principal
demographics -- no more missing rows, no more null-column ghost rows for the
closed schools. Not yet merged (same PR #5059 as the other fixes above).

**Corrected, confirmed against the real Portal task instructions (2026-09-11):
`total_budgeted_enrollment` is NULL for EVERY school network-wide, not just
Miami** -- `stg_google_sheets__topline_enrollment_targets` has rows for
academic_year 2025 only (checked directly: even Royalty/Courage, which DO have a
2025 row, have none for 2026); no district has this year's targets entered yet.
The Portal task's own instructions say **"do not leave any cells blank,"** so
this will fail validation for all 26 schools as-is, not just Miami's. No dbt fix
possible without real source data -- likely just means this year's budget-target
sheet hasn't been populated yet (a normal seasonal lag, not a Miami-specific
gap), but confirm with whoever owns it before assuming it'll be ready in time
for submission. **Not something the collection owner can add themselves** -- the
source is the
["Topline Enrollment Targets" Google Sheet](https://docs.google.com/spreadsheets/d/1as2rMlr8Z6r9-aI3auBLQ-g79-l-NNarHphGN14_IV0)
(external source `src_google_sheets__topline_enrollment_targets`), owned outside
the Data Team. Escalate to whoever owns this year's targets on that sheet rather
than treating it as a collection-owner task; leave the CSGF cell blank and
accept the validation flag until it's populated, same as any other cross-team
dependency in this process.

**Scope check against CSGF's own Field Definitions doc (2026-09-11): this model
deliberately covers only part of the real "Enrollment & School Information"
task.** Diffed column-by-column against `reference/field-definitions.md` section
2 -- Total Seat Capacity 2026-27, Total Seats When Growth Plan Complete, 2024-25
ADA Rate, 2024-25 Chronic Absenteeism Rate, 2025-26 Teacher Counts, Teacher
Retention, and the co-leader row of School Leader Demographics are all real
fields on this task with no column here. **Confirmed not a gap** -- these belong
to other task owners (Walters, Laz, Kevin), entered directly on the Portal, not
sourced through this dbt model. Documented so a future reader doesn't mistake
this for an oversight.

**Forward risk for next cycle, not this one:** Miami opened its first high
school in AY2026 -- KIPP Miami Technical High, ~95 students, mostly grade 9. The
7 HS-scoped `rpt_gsheets__csgf_*` models are correctly Miami-irrelevant _this_
cycle (they read AY2025, when Miami had zero HS students), but next cycle they
roll to AY2026 and will need Miami HS data for the first time ever.

For `rpt_gsheets__csgf_hs_enrollment` specifically (verified and documented on
the model itself -- see its properties YAML `description:` for the authoritative
version): its enrollment/demographic fields come through
`int_extracts__student_enrollments`, which already includes Miami via Focus, so
those will be correct. But its course-tag CTEs (`transfer_course_tags` ->
`stg_powerschool__storedgrades`, `local_course_tags` ->
`base_powerschool__course_enrollments`) are PowerSchool-only with no Focus
equivalent wired in -- Miami HS students will get **NULL, not `'N'`**, for
`has_participated_in_ap_courses` / `_honors_courses` /
`_dual_enrollment_courses` / `_cte_courses`, since the `course_tags` CTE
produces no rows for them at all. A Focus course/grade source needs to be added
to those two CTEs before this model rolls to AY2026. The other 6 HS models
likely have the same PowerSchool-only gap somewhere in their lineage -- not yet
verified per-model.

**`rpt_gsheets__csgf_hs_enrollment`'s fixes are also only on PR #5059, not yet
in prod, same staleness pattern as `hs_grad_data` above.** Confirmed live:
prod's view (last recreated 2026-07-24) still lacks `exited_hs` entirely, still
misses `FDC` in the FRL/SED flag, and still carries the old `passed_algebra_i`
output column with the comma-bug-corrupted IN-list behind it. Rebuilt this
branch's version in dev
(`int_extracts__student_enrollments rpt_gsheets__csgf_hs_enrollment`, since
`exited_hs` is a same-PR addition to the upstream too -- deferring to stale prod
for just the report model fails with `Name exited_hs not found inside e`) --
clean build, unique on `studentid`, 1,681 rows across the 3 schools with HS
enrollment in AY2025 (Cooper Norcross, Newark Collegiate, Newark Lab -- no Miami
rows, correctly, since Miami Tech didn't exist yet that year). One single
null-GPA row (a 9th grader at Newark Lab) -- plausible (late enrollee / no
grades posted) but worth a quick sanity check with the school before submitting,
not treated as a code bug.

**Confirmed against the real Enrollment tab header this cycle (pasted directly
from CSGF's HSDC sheet, 2026-09-11): 16 real columns, and this model's
`passed_integrated_math_1` (hardcoded `'NA (not offered)'`, meant to replace the
old `passed_algebra_i` computed field) matches NEITHER old nor new -- CSGF's tab
asks about neither Algebra I passage timing nor Integrated Math 1 at all this
cycle.** Every other model column has a real destination (`student_is_frl`
reused as-is for the tab's "Socioeconomically Disadvantaged (SED)" field --
already documented on the column, not a new finding). Since data entry is a
manual copy from the internal "CSGF Data" staging sheet
(`kipptaf_extracts.rpt_gsheets__csgf_hs_enrollment`'s Google Sheet tab) into
CSGF's actual HSDC workbook -- not an automated positional load -- an orphan
column like this is harmless to just skip over, not a data-corruption risk.
Worth a follow-up cleanup (drop the column from the model + properties yml) but
not urgent enough to block this cycle's submission.

Whoever runs next cycle's rollover should check this explicitly rather than
assuming the existing HS models will "just work" once Miami has HS enrollees.

**`rpt_gsheets__csgf_hs_ap_offerings` needs two things checked every cycle,
before submitting:**

1. **Coverage** -- it pivots on a hardcoded list of AP course names, so a
   newly-offered course not yet added to the pivot's `IN` list drops out
   silently (no error). Query
   `stg_google_sheets__collegeboard__ap_course_crosswalk` joined through
   `base_powerschool__course_enrollments` for the current cycle's actual AP
   courses taught, and confirm every one is already a pivot column. (Also check
   for a silent drop one step earlier: any `is_ap_course` row whose PowerSchool
   subject code has no match in the crosswalk at all -- that `INNER JOIN` drops
   those rows before they ever reach the pivot.)
2. **Naming** -- separately from coverage, the model's `ap_courses` CTE remaps a
   few College Board crosswalk names to CSGF's own official naming for that
   cycle (confirmed mismatches found in the 2026-2027 cycle: "AP US History" ->
   "AP United States History," "AP US Government and Politics" -> "AP United
   States Government and Politics," "AP Pre-Calculus" -> "AP Precalculus").
   CSGF's exact expected names can change cycle to cycle and don't always match
   the crosswalk's canonical naming. **Ask whoever's completing the AP Offerings
   tab for CSGF's current official AP course name list** (visible on the
   Salesforce Portal's AP Offerings task), diff it against the crosswalk's
   canonical names, and update the `case` statement in
   `rpt_gsheets__csgf_hs_ap_offerings.sql` for any mismatches -- a plain rename,
   not a new external source or staging sheet.

**2026-2027 cycle, checked 2026-09-11: coverage is clean, naming still needs the
human confirm.** Queried `base_powerschool__course_enrollments` joined through
the crosswalk for AY2025 (the year this model actually reads) --12 distinct AP
courses taught network-wide, all 12 already covered by the pivot's `IN` list
(including the 2 that need the existing case-statement remap: `AP Pre-Calculus`,
`AP US History`). Zero rows dropped at the earlier crosswalk join either. Same
clean result cross-checking `int_assessments__ap_assessments` for `hs_ap_scores`
(14 distinct course names for AY2025, all either already plain-matching or
covered by the same case statement) -- no new AP course name needs adding to
either model's `case` statement this cycle. **Still open:** nobody has pasted
CSGF's current official AP course name list from the Portal task yet, so the
"matches CSGF's exact expected string" half of the naming check is unverified --
only "matches what we used last cycle" is confirmed.

**`rpt_gsheets__csgf_hs_ap_scores` has the same naming risk, from a different
upstream.** Its `aptest_name` sources from
`int_assessments__ap_assessments.ap_course_name` (actual AP exam score data),
not the College Board crosswalk `hs_ap_offerings` uses -- but confirmed against
2026-2027 data, it produces the exact same "AP US History" / "AP Pre-Calculus"
values needing the exact same remap. Both models now carry the same `case`
statement. **Update both together** whenever CSGF's official AP name list
changes -- checking one and not the other leaves a silent mismatch in whichever
model you skipped.

**School names need the same ask-and-confirm check every cycle -- don't assume
last cycle's names still match.** Raw PowerSchool `school_name` doesn't always
match CSGF's expected string (`hs_enrollment` and `hs_ap_offerings` both
special-case `KIPP Cooper Norcross High` -> `KIPP Cooper Norcross High School`
for this reason). Confirmed against raw data for the 2026-2027 cycle:
`hs_enrollment` and `hs_ap_offerings` output the full names CSGF expects
(`KIPP Cooper Norcross High School`, `KIPP Newark Collegiate Academy`,
`KIPP Newark Lab High School`) -- Newark's two needed no fix, only Cooper
Norcross did. `hs_grad_data` had the same abbreviated-code gap (`KHS`, `NCA`,
`NLH`); fixed the same way, confirmed against CSGF's Portal task labels.

Separately, `rpt_gsheets__csgf_enrollment`'s Paterson remap was outputting
`KIPP Paterson MS` / `KIPP Paterson ES`, missing "Prep" -- fixed against CSGF's
own Portal school-list export (`KIPP Paterson Prep MS` /
`KIPP Paterson Prep ES`).

Each cycle: **ask the collection owner to paste CSGF's current official school
name list** (same pattern as the AP course name ask above), confirm each model's
school-name output against it, and edit the `if()`/`case` mapping for any model
where they don't already match.

**`rpt_gsheets__csgf_hs_postsec_pathways` can emit more than one row per student
per year -- routed to Casey Gibson (KIPP Forward data owner) to decide, not
resolved here.** The model joins one row per matching
`base_kippadb__application` record where
`matriculation_decision = 'Matriculated (Intent to Enroll)'`, with no dedup/pick
logic. Confirmed in prod: a student can have that flag set on more than one
application in the same year (e.g. intent flagged at two different colleges
before choosing) -- this is apparently real per the collection owner, not a bug
by itself. But at least one case also showed a literal duplicate application
record (same student, same college, same decision, twice) mixed into the same
rows, which is not explained by the legitimate-multiple case. Ask Casey: (1)
does CSGF's Intended Postsecondary Pathways task expect one row per student per
year, or is more than one acceptable when a student has multiple matriculation
intents; (2) should exact-duplicate application records be deduped before they
reach this extract. A `dbt_utils.unique_combination_of_columns` test on
`(academic_year, student_number)` is in place at `severity: warn` so this
surfaces every cycle without blocking a build.

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

## Open questions for this skill (not yet answered)

- Who is the current collection owner / project manager, for reference the next
  time this skill needs updating?

<!-- Next steps to capture: Salesforce Portal account setup/verification,
working through the rest of the item list, ongoing review / Ready for Review
workflow, internal deadline check-in, panic week, official submission,
audited-data follow-up in January, more Preliminary Questions as they're
pasted. -->
