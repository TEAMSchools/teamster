# Preliminary Questions log

Full question/answer/verification log for the Portal's Preliminary Questions
task, referenced from `SKILL.md` Step 4. Question, this cycle's answer, how it
was verified -- carry forward and re-verify each cycle rather than assuming the
answer repeats. Entries 2-6 (the "Academic Profile & Grading" subsection) are
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
   is a real, distinct calculation, not a duplicate of unweighted. This 1,710 is
   against OLD prod (pre-PR-#5059, before `exited_hs`/FDC/`passed_algebra_i`
   fixes); the PR #5059 dev-branch rebuild documented in
   [`known-data-risks.md`](known-data-risks.md) (see "clean build... 1,681
   rows") counts the SAME 3 schools/year on the fixed model -- the 29-row gap is
   from those fixes, not a contradiction. Don't average or reconcile the two
   into one number; use whichever build (prod vs. the PR branch) matches what
   you're verifying against.

6. **"What is the grading scale?"** → KTAF uses a plus/minus-based GPA point
   scale: regular (unweighted) courses cap at **4.33**, advanced/honors
   (weighted) courses cap at **5.33**. **Correction from an earlier pass of this
   log**, which flagged this question as unanswerable from a
   `rpt_gsheets__csgf_*` report -- true, but there's a different verifiable
   source: business-rule documentation, not a CSGF report. Confirmed two ways:
   (a)
   [`src/dbt/kipptaf/models/students/CLAUDE.md`](../../../../src/dbt/kipptaf/models/students/CLAUDE.md)
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
