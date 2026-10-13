# High School Data Collection (HSDC) mechanics

Referenced from `SKILL.md`. HSDC is a **separate submission** from the main
Portal collection, gated on signing that cycle's Data Sharing Agreement (DSA).
In exchange, KTAF gets access to cross-network benchmarking and trend analysis
across 85+ charter networks in the CSGF High School Data Collaborative.

**"HSDC looks back one year"** -- CSGF's own wording. The 2026-2027 HSDC
submission covers the 2025-2026 school year: every high school student who
completed that year at a KTAF high school. This is the CSGF-sourced explanation
for the year-anchoring inconsistency across the `rpt_gsheets__csgf_*` models
that [issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) flags --
worth citing verbatim in `docs/models/csgf-data-model.md`.

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
anchoring in [`known-data-risks.md`](known-data-risks.md): 5 of the 8
`rpt_gsheets__csgf_*` models (Enrollment, SAT, ACT, AP Offerings, AP Scores)
read only `current_academic_year - 1` -- last cycle's finalized school year,
which cannot change. HS Grad Data is scoped to the current cohort (a fixed
number known well in advance, not something that becomes true only after a
future date), so it's computable now too. Postsecondary Pathways is unfiltered
and already correctly reflects every completed cohort. That's 7 of 8 tabs
computable the moment Preliminary Questions is done and the Sheet is accessible,
with no need to wait for the internal deadline crunch. Only the main Portal
`csgf_enrollment` model (current-year enrollment counts, and the current-year
side of its retention calc) is genuinely blocked -- it needs this year's Oct 1
count day to happen first.

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
  are the same values as the "grading scale" Preliminary Question (Q6 in
  [`preliminary-questions-log.md`](preliminary-questions-log.md)): **unweighted
  max = 4.33, weighted max = 5.33**. Confirm these haven't changed each cycle
  rather than assuming they carry forward.
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
   is the opposite of the main Portal grids' Excel export/import workflow in
   [`portal-mechanics.md`](portal-mechanics.md). Downloading/copying breaks the
   template's built-in validation and formulas.
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
