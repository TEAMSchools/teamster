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

**CSGF-provided:**

- [CSGF Data Collection Portal User Guide](https://docs.google.com/document/d/1V5LBa--mKLZC2PSd9ptEVSQSoj-4YUHWznPyPu62A6M/edit?tab=t.0)
  (dated August 2026) -- see "Portal mechanics" and "HSDC mechanics" below for
  the extracted contents.
- [CSGF Data Collection Field Definitions](https://docs.google.com/spreadsheets/d/1hpMLqeFcci_Epar3InHRB8UXly7ZLg42vzjgANUpzP8/edit?gid=963005787#gid=963005787)
  -- CSGF's own field-by-field definitions. Full extraction with structural
  gotchas: [`reference/field-definitions.md`](reference/field-definitions.md).
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
3. Only if neither exists, answer from institutional knowledge -- and flag that
   as a gap worth building a report for.

**Keep every check aggregate-level** (counts, distinct schools/regions) -- never
query for or paste individual student rows into this process. This
question-answering step needs proof the population exists, not who's in it.

**Preliminary Questions log** (question, this cycle's answer, how it was
verified -- carry forward and re-verify each cycle rather than assuming the
answer repeats):

1. **"Did you operate high schools last year?"** → **Yes** (2026-2027 cycle).
   Verified via `rpt_gsheets__csgf_hs_enrollment` (prod, schema
   `kipptaf_extracts`): KIPP Cooper Norcross High (Camden, 444 students), KIPP
   Newark Collegiate Academy (770), KIPP Newark Lab High School (496), all for
   AY2025 (the 2025-2026 school year). Miami and Paterson have no HS enrollment
   and are correctly absent.

<!-- More Preliminary Questions to capture as they're pasted. -->

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

**Working the Sheet:**

- Start with the **Enrollment tab** -- every student on any other tab must also
  have an Enrollment row, and vice versa (every completer goes on Enrollment
  even if they don't appear elsewhere).
- Fill the min/max weighted and unweighted GPA cells (K4/L4 in CSGF's template)
  -- leaving them blank flags ALL GPA data as errors, not just those cells.
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

## Open questions for this skill (not yet answered)

- Exactly how does data move from the `rpt_gsheets__csgf_*` dbt models into the
  actual CSGF-owned HSDC Google Sheet -- an automated push, or a manual
  copy/paste step by the collection owner? Confirm and document once known.
- Who is the current collection owner / project manager, for reference the next
  time this skill needs updating?

<!-- Next steps to capture: Salesforce Portal account setup/verification,
working through the rest of the item list, ongoing review / Ready for Review
workflow, internal deadline check-in, panic week, official submission,
audited-data follow-up in January, more Preliminary Questions as they're
pasted. -->
