---
name: graduation-pathways
description: >-
  Use when any question or task touches New Jersey graduation pathway codes or
  their lineage. Triggers: adding a cut score after an NJDOE broadcast, a
  student's pathway code looking wrong, NJGPA vs NJGPA-A score scales, entering
  transfer scores in PowerSchool, the graduation pathway fields written back to
  PowerSchool for state reporting, or working on
  int_students__graduation_path_codes,
  stg_google_sheets__student_graduation_path_cutoffs,
  int_pearson__all_assessments or rpt_tableau__graduation_requirements and their
  upstream models.
---

# Graduation Pathway Codes

## Always read first

- Reference doc:
  [`docs/models/hs-early-warning-data-model.md`](../../../docs/models/hs-early-warning-data-model.md)
  — the dashboard these codes feed, and the PowerSchool setup each region needs.
- `src/dbt/kipptaf/models/students/intermediate/int_students__graduation_pathway_scores.sql`
  — pairs every student with every pathway their cohort has a cut score for, and
  decides whether their score cleared it. One row per student, subject, score
  type, assessment version and sitting.
- `src/dbt/kipptaf/models/students/intermediate/int_students__graduation_path_codes.sql`
  — rolls that up into a per-student standing, and computes
  `final_grad_path_code` and `grad_eligibility`.
- `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__student_graduation_path_cutoffs.yml`
  — the cut score contract and its key.
- The NJDOE broadcast for the cohort in question. NJDOE publishes graduation
  requirements per graduating class, not per year, and the cut scores land only
  after the administration is scored. Requirements index --
  <https://www.nj.gov/education/assessment/requirements/>, which links a page
  per graduating class. Test blueprints --
  <https://www.nj.gov/education/assessment/adaptive/gpablueprints.shtml>.

**This model writes to the state.** `final_grad_path_code` flows through
`rpt_powerschool__autocomm_students` into the PowerSchool fields
`s_nj_stu_x__graduation_pathway_ela` and `s_nj_stu_x__graduation_pathway_math`,
dropped daily to `data-team/<district>/powerschool/autocomm` for AutoComm
import. A wrong code is a wrong state submission, not a dashboard cosmetic.
Treat every change here as production-affecting.

Miami is excluded by design (`where e.region != 'Miami'`). NJ pathways do not
apply in Florida.

## Ask the source, not the model

To answer "does X exist in the data", query the staging models the scores come
from, never `int_students__graduation_pathway_scores`. That model only contains
rows where a matching cut score row exists, so a version whose cohort has no cut
score row is structurally invisible in it.

This is not hypothetical. Asking that model whether any student holds both NJGPA
versions returned none. Asking `stg_pearson__njgpa` and `stg_cambium__njgpa`
directly returned eight. The same shape of mistake -- checking the derived thing
instead of the raw thing -- is why the original cut score defect went unnoticed
for months.

---

## Two vendors, two score scales, one testcode

This is the trap. NJGPA is dual-vendor and both vendors report the **same**
`assessment_name` (`NJGPA`) and the **same** `testcode` (`ELAGP` / `MATGP`).
Only the staging relation and the score scale differ.

| Staging model        | Test              | Observed scores | Cut | Administrations          |
| -------------------- | ----------------- | --------------- | --- | ------------------------ |
| `stg_pearson__njgpa` | NJGPA, retired    | 650-850         | 725 | Spring 2021 to Fall 2025 |
| `stg_cambium__njgpa` | NJGPA-A, adaptive | 300-562         | 450 | Spring 2026 onward       |

The ranges above are the min and max **observed in our own rows**, not published
scale bounds. NJDOE does not publish the scale range on either the
[requirements page](https://www.nj.gov/education/assessment/requirements/) or
the
[blueprints](https://www.nj.gov/education/assessment/adaptive/gpablueprints.shtml)
-- only the cut score, in the per-class broadcast. Treat the cut as
authoritative and the range as a sanity check that may widen as more scores
arrive.

`assessment_version` tells them apart. It is set as a **literal** in each
vendor's staging model, never inferred — `'NJGPA'` in the Pearson models,
`'NJGPA-A'` in the Cambium model, and the assessment's own name in
`stg_pearson__parcc` / `_njsla` / `_njsla_science` so no relation null-fills the
column. `int_pearson__all_assessments` names it in the `union_relations`
`include` list and passes it through.

**Students hold scores on both versions, and the number will grow.** Eight do
today, and two of them failed the retired test by a handful of points and then
passed the adaptive one. Any logic that picks "the" state assessment score for a
student has to handle that pair, and cannot compare the two raw scores -- 700 on
the retired scale is a fail and 500 on the adaptive scale is a pass.

That is why `rn_highest` in `int_students__graduation_pathway_scores` orders by
`met_pathway_cutoff` and then `points_short`, **not** by `scale_score`.
Consumers filter it to 1 to get one row per score type, so ranking on the raw
score would put the failing 700 first and hide the passing 500. Points short is
measured against each score's own cut score, so it is comparable across scales.
Do not "simplify" that ordering back to the raw score.

Never key a cut score on cohort alone, and never infer the version from a score
value or a date. Confirm both scales independently from the data with
`testperformancelevel` — level 1 tops out one point below the cut, level 2
starts at it.

---

## Cut scores live in a hand-maintained sheet

`stg_google_sheets__student_graduation_path_cutoffs` reads a Google Sheet tab,
keyed on `cohort` + `discipline` + `score_type` + `assessment_version`.
`pathway_option` stays `NJGPA` for **both** versions — that is deliberate, and
it is what keeps the `calcs` roll-up in `int_students__graduation_path_codes`
and the `final_grad_path_code` case untouched when a new version appears.

Two coordination rules:

1. **The staging model is `select *` with an enforced contract.** Adding a sheet
   column breaks the build until the properties YAML declares it, and declaring
   it breaks the build until the sheet has it. The two must land together. The
   failure is benign — downstream simply does not rebuild — but plan the
   sequencing.
2. **Never judge sheet contents from the prod `stg_` table.** It is a table
   frozen at the last build. The BigQuery MCP service account cannot read
   Drive-backed externals at all (403, no Drive scope). Read the live sheet by
   requesting the Drive scope explicitly from a pytest one-off, or rebuild the
   staging model into your dev schema.

---

## `cohort` is frozen at high school entry

`int_students__student_enrollments` computes `cohort_primary` as
`(academic_year + 13) - grade_level`, but for `grade_level >= 9` it uses
`cohort_secondary`, which freezes at the student's first year in the school and
is never recomputed.

That is **correct on purpose** — NJ's 4-year adjusted cohort graduation rate is
defined by first-time grade 9 entry. Do not "fix" it.

The consequence: a retained or accelerated student sits the assessment with a
different class than their cohort, so a cohort can legitimately need cut score
rows for more than one assessment version. When a student's pathway looks wrong,
check this before suspecting a bad score match.

The actionable drift signal is a student **ahead** of their entry cohort
(`(academic_year + 13) - grade_level < cohort`), which means a grade skip or a
missing enrollment year. A student _behind_ their cohort is ordinary retention
and is not a defect — testing the raw inequality flags every retained student in
the network.

---

## Graduation eligibility is derived, not maintained

`grad_eligibility` used to come from a hand-maintained sheet joined on eight
boolean columns. That sheet is retired (`enabled: false`) and the label is now
computed in `int_students__graduation_path_codes`. Do not reinstate it.

Three rules drive the label, and only the first is obvious from the column
names:

1. **A subject only counts if the student sat the NJGPA in it.** `met_ela` with
   `attempted_njgpa_ela` false contributes nothing.
2. **FAFSA is required to graduate**, but it is not counted against a student
   until the January deadline of their senior year. It is tracked before then.
   FAFSA never gates an 11th grader.
3. **An 11th grader holding NJGPA records is treated as a 12th grader**, minus
   FAFSA. Testing ahead of their peers usually means they are behind on credits.
   The grace period belongs only to 11th graders with no records yet, and it
   ends once results land in late June.

---

## Transfer scores are entered by hand in PowerSchool

Users enter them at **PS instance > District Management > Tests > Standardized
Tests**.

User guide, which **must be updated whenever transfer-score entry changes**:
<https://teamschools.zendesk.com/hc/en-us/articles/20823542157463--User-Guide-Adding-NJGPA-Scores-to-PowerSchool-for-Transfer-Students>

Both forms share **one holder**, named `NJGPA/NJGPA-A`, with four score fields:

| Score field | Version | Normalizes to |
| ----------- | ------- | ------------- |
| `ELAGP`     | NJGPA   | `ELAGP`       |
| `MATGP`     | NJGPA   | `MATGP`       |
| `ELAGP-A`   | NJGPA-A | `ELAGP`       |
| `MATGP-A`   | NJGPA-A | `MATGP`       |

`int_powerschool__state_assessments_transfer_scores` reads the version off the
`-A` suffix and strips it back to `ELAGP` / `MATGP` for the cut score join. The
holder name is **not** the version — it names both forms.

Two ways this breaks silently:

- The model filters `where t.name in ('NJGPA', 'NJGPA/NJGPA-A')`. **A holder
  named anything else yields zero rows** — no error, no signal. Both names stay
  matchable because the instances are renamed independently.
- A score field named outside `ELAGP` / `MATGP` / `ELAGP-A` / `MATGP-A` produces
  a testcode that matches no cut score row. The `accepted_values` test on
  `testcode` is what turns that into a failure instead of a dropped score.

**Paterson has no NJGPA data yet and its PowerSchool instance has no holder
configured.** Only Newark and Camden do. When Paterson first receives NJGPA
transfer scores, its instance needs the same setup before any score can flow: a
standardized test named `NJGPA/NJGPA-A`, type State, with all four score fields
above. Until then Paterson simply contributes no rows, which is correct and not
a defect — but a Paterson transfer score entered before the holder exists cannot
be captured at all.

---

## RUNBOOK: portfolio appeals from NJDOE

A portfolio appeal is pathway code `N`. NJDOE grants them and sends PDFs, which
have to be converted and imported into each region's PowerSchool by hand. There
is no pipeline for this and the model only ever reads the resulting
`ps_grad_path_code`.

Working folder, which holds every file below —
<https://drive.google.com/drive/folders/1BakRrY_7tlJ0H6ctsjk8F12VpWWXQGLU>

| Artifact                                            | Where it comes from             |
| --------------------------------------------------- | ------------------------------- |
| Two appeal PDFs, one per region                     | The C3 team, usually over Slack |
| Portfolio Converter, an Excel workbook              | The folder above                |
| NJ Portfolio Appeal Upload Template, a Google Sheet | The folder above                |

Steps:

1. Put both PDFs in the folder, named `Newark` and `Camden`. Replace any
   existing files, and delete last year's TSVs so they cannot be imported by
   mistake.
2. Open the Portfolio Converter **from the desktop Excel app, never from Google
   Sheets or a browser** — opening it in Sheets breaks its PowerQuery
   connection. Then Data, Refresh All, to refresh both worksheets.
3. In the upload template, refresh the Student Numbers tab. It also refreshes
   itself on the first of each month.
4. Copy each region's table from the workbook into its Paste Source tab. Copy
   only three columns; column D pulls the student number by formula.
5. Check all four region-and-subject tabs. Row counts should match the workbook,
   student numbers should line up with the state student identifiers, and
   formulas may need extending.
6. Click EXPORT TSV FILES on the Newark Math tab. Four TSVs appear in the folder
   after about a minute.
7. In each region's PowerSchool, Data and Reporting, Imports, Quick Import.
   Choose the **Students** table, **LF** as the end-of-line marker, and the
   matching TSV. Confirm the column names, tick to exclude the first row, and
   choose the update-the-student's-record option.
8. PowerSchool lists the students it changed. Anything in red is an error;
   Walters owns resolving those.

**Switch PowerSchool instances between the Newark and Camden files.** Importing
a region's file into the other instance is the failure mode this procedure is
most prone to.

---

## RUNBOOK: new cut scores from NJDOE

This is the yearly job. Someone says _"we got new cut scores for NJGPA, we need
to update them."_ Run this start to finish; do not wait to be walked through it.

### Step 1 — Ask for the broadcast URL

Ask one question and stop: **what is the URL of the NJDOE notice?** Do not
proceed on a number quoted from memory or from a meeting. The broadcast is the
authority, and it states which graduating class it covers.

NJDOE posts these at `nj.gov/education/broadcasts/<year>/<mon>/<day>/...`. If
`WebFetch` returns nothing usable, download the PDF and extract the text locally
— these are short PDFs and the scanner sometimes redacts the fetched form.

### Step 2 — Read it and pull out four things

- The cut score, per discipline.
- **Which graduating class** it covers. It will name one class, not a range.
- Whether the assessment is the same form or a **new version** (a rename like
  NJGPA to NJGPA-A signals a new score scale).
- Whether the alternative-assessment menu changed. It usually says "unchanged"
  and you can leave those rows alone.

### Step 3 — Confirm the cut against our own data

Never enter a published number without checking it. Group that administration's
scores by `testperformancelevel`: level 1's max should sit one point below the
published cut, and level 2's min should equal it. If they disagree, stop and
raise it — either the file or the broadcast reading is wrong.

Also sanity-check the scale. A cut of 450 against scores running 650-850 means
you are about to key a new-scale cut onto old-scale rows.

### Step 4 — Generate the full replacement rows

The sheet is small, so replace it wholesale rather than hand-editing rows.

Read the live tab — the BigQuery MCP service account **cannot** (403, no Drive
scope) and the prod `stg_` table is frozen at the last build. Use a throwaway
`tests/test_zz_*.py` with `google.auth.default(scopes=[".../drive.readonly"])`
and the Sheets API, then delete it. The named range in `sources-external.yml`
`sheet_range` tells you which tab.

Build the replacement as TSV into `.claude/scratch/` and hand the analyst the
file to paste. Rules:

- Keep every existing row. Old cohorts still score students who sat the old
  test.
- **Add** the new version's rows; never overwrite the old cut. A cohort can hold
  rows for both versions at once, and some of its students will have sat each.
- Fill `assessment_version` on every row. Non-NJGPA rows repeat
  `pathway_option`.
- `pathway_option` stays `NJGPA` even for a new version.

### Step 5 — Code changes, only if the version is new

- Add the version literal to the vendor's staging model, and to
  `int_pearson__all_assessments`'s `union_relations` `include` list.
- Add the value to the `accepted_values` lists on `assessment_version` in both
  `int_pearson__all_assessments` and the cut score properties YAML.
- Add the PowerSchool score field names to the transfer-scores model, and check
  whether the holder name changed.
- Update the transfer-score user guide and this skill.

### Step 6 — Verify additively

A cut score fix should only ever **add** met pathways. Compare before and after
and confirm no student loses one. If any student flips from met to not met, the
join is wrong — usually a new-scale cut applied to old-scale scores.

A cohort with scores but no cut score row produces `final_grad_path_code = 'R'`,
which reads as "no pathway met". That is indistinguishable from a genuine
failure on the dashboard, so a missing row is a silent wrong answer, not a gap.

---

## pathway codes

| Code | Meaning                   | Label               | Source                           |
| ---- | ------------------------- | ------------------- | -------------------------------- |
| `S`  | State assessment          | NJGPA               | NJGPA or NJGPA-A at or above cut |
| `E`  | ACT                       | ACT                 | cut score sheet                  |
| `D`  | SAT                       | SAT                 | cut score sheet                  |
| `J`  | PSAT10                    | PSAT10              | cut score sheet                  |
| `K`  | PSAT/NMSQT                | PSAT NMSQT          | cut score sheet                  |
| `M`  | IEP                       | DLM                 | `ps_grad_path_code`              |
| `N`  | Portfolio appeal          | Portfolio           | `ps_grad_path_code`              |
| `O`  | Attempted, passed nothing | Met No Requirements | `ps_grad_path_code`              |
| `P`  | Incomplete credits        | Incomplete Credits  | `ps_grad_path_code`              |
| `R`  | Nothing met               | Default             | computed fallback                |

The Label column is `final_grad_path_name`, decoded in
`int_students__graduation_path_codes`. It used to be a calculated field in the
Tableau workbook; it was moved into the model so every consumer reads one
definition. A new code letter therefore needs a branch in TWO places -- that
decode and the `pathway_option` decode in
`int_students__graduation_pathway_scores` -- and
`int_students__graduation_path_codes__labels_agree` fails the build if the two
disagree.

Codes `M`, `N`, `O`, `P` come straight from PowerSchool and bypass the cut score
join entirely — the second branch of the `matched` union in
`int_students__graduation_pathway_scores` handles them, with a null `cutoff` and
a `scale_score` of 0. The zero is not a score: the graduation requirements
extract filters on `scale_score is not null`, so these students would drop off
the dashboard without it. Grades 10 and below pass `ps_grad_path_code` through
unchanged.

The state assessment wins when met: `met_njgpa` is tested first, so a student
who cleared NJGPA reports `S` even if they also cleared SAT.

NJDOE's alternative menu also includes four Accuplacer options (WritePlacer 5,
WritePlacer ESL 4, Elementary Algebra 49, Next-Generation QAS 250). **KTAF does
not use Accuplacer and does not intend to.** Do not add cut score rows for them.
We ingest no Accuplacer scores, we hold no NJDOE pathway code letter for them,
and `final_grad_path_code` has no branch to emit one — so a row would be
decorative and a guessed code letter would go to the state. If a student ever
does present an Accuplacer score, the scores_have_cutoffs test names them rather
than silently coding them R.
