# CSGF Data Model

Reference document for the eight `rpt_gsheets__csgf_*` models feeding the
`csgf_data` exposure — the dbt pipeline that prepares KIPP TEAM & Family's
annual Charter School Growth Fund (CSGF) data submission.

!!! tip "Claude Code skill available" The `csgf-data-collection` skill in
`.claude/skills/csgf-data-collection/` covers the manual/ownership side of this
process — confirming participants, the item-list documentation doc rollover,
Salesforce Portal and HSDC mechanics, and a per-cycle checklist for several of
the risks documented below. This page is the dbt-side lineage and model
reference; the skill is the process runbook.

## What is the CSGF data collection?

[CSGF (Charter School Growth Fund)](https://chartergrowthfund.org/) is a
nonprofit that invests growth capital in high-performing charter networks. KIPP
TEAM & Family is a member of CSGF's investment portfolio, and participating in
this annual collection is a term of that grant agreement — the data directly
informs CSGF's grant-making decisions and their own portfolio-wide reporting to
funders.

The collection covers academic, staffing, finance, and org data across two
systems: the Salesforce Portal (most items) and Google Sheets (the High School
Data Collection workbook, "HSDC," plus CSGF's own field-definitions reference).
The eight models on this page prepare KTAF's HSDC extracts — everything else in
the collection (finance, staffing, org info) is either entered directly in the
Portal or sourced from other pipelines not covered here.

All eight write to a KTAF-owned staging Google Sheet, **"CSGF Data"** — one tab
per model — which the collection owner then transfers into CSGF's actual systems
(last cycle by manual cell copy; this cycle via the Portal's new Excel
bulk-upload feature). See the skill's "How the dbt models actually reach CSGF"
section for that mechanism in full.

## The eight models

| Model                      | Grain                             | Years of data referenced                                                                            |
| -------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `csgf_enrollment`          | One row per school                | **This year**, but `retention_numerator`/`retention_denominator` pull last year too via a self-join |
| `csgf_hs_enrollment`       | One row per HS student            | Last year only (`current_academic_year - 1`)                                                        |
| `csgf_hs_sat`              | One row per SAT section score     | Last year only                                                                                      |
| `csgf_hs_act`              | One row per ACT section score     | Last year only                                                                                      |
| `csgf_hs_ap_offerings`     | One row per school (wide-pivoted) | Last year only                                                                                      |
| `csgf_hs_ap_scores`        | One row per AP exam taken         | Last year only                                                                                      |
| `csgf_hs_grad_data`        | One row per school                | Current cohort only (`cohort = current_academic_year`)                                              |
| `csgf_hs_postsec_pathways` | One row per grade-12 student      | **All years** (unfiltered)                                                                          |

Year anchoring is deliberately inconsistent across these eight models — this was
flagged in [issue #4897](https://github.com/TEAMSchools/teamster/issues/4897)
and confirmed here by reading each model's SQL directly, not by trusting the
issue's description. Practical consequence: a data problem in either the current
or prior year can affect `csgf_enrollment`; a problem in _any_ historical year
can affect `csgf_hs_postsec_pathways`, the one remaining unfiltered model. It
also means 7 of the 8 models are computable as soon as CSGF's Preliminary
Questions task is done, without waiting on anything about the current
in-progress year — only `csgf_enrollment`'s current-year grain needs this year's
Oct 1 count day to have happened.

All six HS-scoped models filter to `school_level = 'HS'`, which today means
Camden (KIPP Cooper Norcross High) and Newark (KIPP Newark Collegiate Academy,
KIPP Newark Lab High School) only — Miami and Paterson have no HS enrollment as
of AY2025. See [Known risks](#known-risks) for why that's changing.

### Shared upstream: `int_extracts__student_enrollments`

Every one of the eight models reads
`{{ ref("int_extracts__student_enrollments") }}` (aliased `e` or `co` depending
on the model). Two columns on that model exist specifically to serve CSGF
consumers and should stay promoted there rather than re-duplicated per model:

- **`exited_hs`** (`if(exitcode = 'G1', 'Y', 'N')`) — whether the student
  graduated or completed high school. Added for `csgf_hs_enrollment`'s "did this
  student exit HS at the end of [year]" field, after CSGF clarified via their
  portal comment thread that the field means graduation/completion specifically,
  **not** the broader "didn't return the following year" reading its
  plain-language wording suggests. `csgf_hs_postsec_pathways` already computed
  the identical thing locally (`exited_hs`, same name, same logic) before this
  was promoted — both models now read the one column. Keep them in sync if
  either changes.
- **`enroll_status_string`** — decodes the raw `enroll_status` PowerSchool code.
  Not CSGF-specific, but several models' logic depends on understanding it: `0`
  = Currently Enrolled, `2` = Transferred Out, `3` = Graduated (see the
  exit-code table below for the finer-grained signal).

## Known risks

Verify each of these before trusting a submission — none are hypothetical; all
were found by reading the model SQL or querying prod directly this cycle.

### `csgf_enrollment` under-reported Miami — resolved

The model was driven by `stg_powerschool__schools`, a frozen PowerSchool-era
Miami school catalog never updated after Miami's cutover to Focus as its SIS.
Two Focus-marked-`(Closed)` schools (Sunrise, Liberty) still appeared with every
column null, and three schools with real enrolled Focus students were silently
**missing** entirely (not null — absent rows) because the join to the stale
catalog failed: KIPP Miami Tech (95 HS students), KIPP Legacy Elementary (173),
KIPP Legacy Middle (32) — roughly 300 of Miami's ~1,755 enrolled students. Fixed
by this PR: added a `focus_schools` CTE (`int_focus__schools` filtered to
`school_level is not null`, joined through
`stg_google_sheets__people__locations`) unioned with the PowerSchool-sourced
non-Miami schools. Verified all 5 real Miami schools now appear with correct
enrollment/demographic/principal data, the 2 closed-school ghost rows are gone,
and the 19 non-Miami rows are unchanged.

**Still open, and bigger than Miami**: `total_budgeted_enrollment` is NULL for
all 26 schools network-wide — `stg_google_sheets__topline_enrollment_targets`
has rows for academic_year 2025 only, none yet for 2026, for any district. The
Enrollment task's own instructions require every cell filled; this needs whoever
owns that sheet to add this year's targets before submission, not a dbt fix.

### Miami's first HS is a forward risk for next cycle, not this one

Miami opened its first high school in AY2026 — KIPP Miami Technical High, ~95
students, mostly grade 9. The six HS-scoped models are correctly
Miami-irrelevant _this_ cycle (they read AY2025, when Miami had zero HS
students), but next cycle they roll to AY2026 and will need Miami HS data for
the first time ever.

For `csgf_hs_enrollment` specifically: its enrollment/demographic fields come
through `int_extracts__student_enrollments`, which already includes Miami via
Focus, so those will be correct. But its course-tag CTEs (`transfer_course_tags`
→ `stg_powerschool__storedgrades`, `local_course_tags` →
`base_powerschool__course_enrollments`) are PowerSchool-only with no Focus
equivalent wired in — Miami HS students will get **NULL, not `'N'`**, for
`has_participated_in_ap_courses` / `_honors_courses` /
`_dual_enrollment_courses` / `_cte_courses`, since the `course_tags` CTE
produces no rows for them at all. The other five HS models likely have the same
PowerSchool-only gap somewhere in their lineage — not yet verified per-model.

### AP course naming drifts from CSGF's official list, cycle to cycle

`csgf_hs_ap_offerings` and `csgf_hs_ap_scores` each source AP course names from
a different upstream (`stg_google_sheets__collegeboard__ap_course_crosswalk` and
`int_assessments__ap_assessments.ap_course_name` respectively), and neither
upstream's naming is guaranteed to match CSGF's official picklist for the
current cycle. Confirmed mismatches for 2026-2027, diffed against CSGF's real
current AP course list pasted from the Portal task: "AP US History" → "AP United
States History," "AP US Government and Politics" → "AP United States Government
and Politics," "AP Pre-Calculus" → "AP Precalculus," and 3 College Board "Studio
Art" names → CSGF's current "Art and Design" naming ("AP Studio Art: 2-D Design
Portfolio" → "AP 2-D Art and Design," "3-D Design Portfolio" → "3-D Art and
Design," "Drawing Portfolio" → "AP Drawing"). Both models now carry an identical
`case` remap for all 6 — **update both together** whenever CSGF's list changes,
or one model silently drifts from the other. This duplication is a known,
deliberate scope decision (flagged by `claude-review`, not centralized) — see
Open Items.

`csgf_hs_ap_offerings` used to pivot on only 28 of CSGF's 43 real AP course
columns, so a newly-offered course not on that list would drop out of the
extract silently (no error). Fixed this cycle: the pivot now emits all 43
columns, in CSGF's exact column order (confirmed against the live Portal task),
so a straight copy/paste needs no reordering. The 11 courses/3 subscore columns
KTAF has never offered or tested pivot to NULL for every row by construction —
confirmed via direct query, not assumed. Still confirm current-AY coverage each
cycle per the skill's checklist, since CSGF's list itself can change.

### School names need the same per-cycle check

Raw PowerSchool `school_name` doesn't always match CSGF's expected string —
`csgf_hs_enrollment` and `csgf_hs_ap_offerings` both special-case
`KIPP Cooper Norcross High` → `KIPP Cooper Norcross High School` for this
reason. Confirmed for 2026-2027: both models' full-name output matches CSGF's
expected names for all three current HS schools.

`csgf_hs_grad_data` had the same gap — it output abbreviated codes (`KHS`,
`NCA`, `NLH`) instead of full names. Fixed by switching from
`school_abbreviation` to `school_name` (with the same Cooper Norcross remap),
confirmed against CSGF's Portal task labels (`KIPP Newark Lab High School` /
`KIPP Newark Collegiate Academy` / `KIPP Cooper Norcross High School`).

`csgf_enrollment`'s Paterson remap had the inverse problem — it was outputting
`KIPP Paterson MS` / `KIPP Paterson ES`, missing "Prep." Fixed against CSGF's
own Portal school-list export, which has `KIPP Paterson Prep MS` /
`KIPP Paterson Prep ES` on file.

### `csgf_hs_grad_data`'s cohort scope — resolved

[Issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) originally
flagged this as an open design question: the model had a `graduated` CTE with a
real cohort filter
(`cohort = current_academic_year AND academic_year = current_academic_year - 1`)
that was **never referenced** by the final `SELECT` — dead code. The live query
path (`grad_roster`, filtered only by `school_level = 'HS'`) was unfiltered by
cohort, so it returned every cohort ever recorded — confirmed in prod: one
school alone had 20 rows, spanning cohorts 2011-2030, instead of one.

CSGF's own Salesforce Portal task purpose settles this: the task explicitly
calculates the 4-year graduation rate for the cohort that entered 9th grade four
years prior and is expected to graduate this year, with the instruction "if the
school did not have 12th graders in [year], leave all rows blank" — i.e. one row
per school for the current cohort, not one row per cohort ever recorded. Fixed
by moving the dead CTE's cohort filter onto the live `grad_roster` query path
and removing the dead `graduated` CTE entirely. Confirmed against prod: three
schools, three rows, all cohort 2026.

!!! note "SED field uses the same FRL definition" CSGF's new "Socioeconomically
Disadvantaged (SED)" field on the HS Enrollment tab instructs submitters to "use
what is valid for the state." `csgf_hs_enrollment`'s `student_is_frl` was
widened this cycle to include `lunch_status = 'FDC'` alongside `'F'` and `'R'` —
`FDC` means "Free via Direct Certification" (automatic free-meal eligibility via
SNAP/TANF/Medicaid), a federal mechanism valid in every state's own
economically-disadvantaged definition, NJ included. This reading is backed by
this repo's own documented source (`stg_powerschool__students.yml`:
`"FDC=Free-DC"`) and matches CSGF's own "FRL or Direct Cert" framing elsewhere
in their field definitions. The SED field reuses this same `student_is_frl`
value rather than a separate column.

## Exit-code reference

`enroll_status`/`exitcode` combinations that look similar can have very
different real-world meaning. Confirmed against AY2025 data by checking what
fraction of students carrying each code actually returned the following year (a
real return, not a proxy):

| exitcode | Meaning (PowerSchool Gen Table 6)                  | Returned next year |
| -------- | -------------------------------------------------- | ------------------ |
| T1       | Transfer within the same school                    | 93.9%              |
| W01      | Promoted/Retained/Transferred, Same Sch            | 99.1%              |
| T2       | Transfer to another public school within district  | 93.9%              |
| T4       | Transfer to another public school outside district | 0.7%               |
| T8       | Transfer out of state or country                   | 0.6%               |
| TC       | Transfer to charter school                         | 0%                 |
| T9       | Transfer to parental instruction                   | 12.5%              |
| W02      | Promoted/Retained/Transferred, Diff Sch            | 8.4%               |
| W06      | Graduated - Std Diploma                            | 9.5%               |
| G1       | Graduated from a KIPP NJ school                    | 0%                 |

T1, W01, and T2 aren't real exits — they're PowerSchool's codes for internal
moves (same school, or between schools within the same district, which for KTAF
includes moving between two KTAF schools). That's why they still return 93-99%
of the time. Everything else above is a genuine departure.

## Open items

- The other five HS-scoped models' Miami/Focus course-data gap for next cycle —
  only verified for `csgf_hs_enrollment` so far.
- All eight models now have a uniqueness test (resolved by this PR).
- CSGF's own Portal school-list was missing three real Miami schools (KIPP Miami
  Technical High, KIPP Legacy Elementary, KIPP Legacy Middle) — confirmed via
  CSGF's school-list CSV export. Not a dbt fix; the collection owner has since
  added all three via the Portal's "Add Record" (self-service, since import
  can't create new rows -- see the csgf-data-collection skill), so this is
  resolved for the 2026-2027 cycle. The remaining Schools List fields for those
  3 schools (seat capacity, facility/real-estate questions) still need direct
  input from the task owner; tracked in the skill, not here.
- `rpt_gsheets__csgf_enrollment.total_budgeted_enrollment` is NULL for all 26
  schools network-wide, not just Miami -- the target sheet has no 2026 rows for
  any district yet. Needs whoever owns that budget-target sheet to add this
  year's targets, not a dbt fix. Violates the Enrollment task's own "do not
  leave any cells blank" instruction as of 2026-09-11.
- `csgf_hs_ap_offerings` and `csgf_hs_ap_scores` carry an identical AP
  course-name remap `CASE` statement, kept in sync by convention (documented in
  both properties files) rather than centralized. Flagged by `claude-review` as
  low-severity reuse/duplication; not fixed here, since it doesn't affect
  correctness as long as both are updated together each cycle.
- `rpt_gsheets__csgf_hs_enrollment`'s `transfer_course_tags` CTE still filters
  transfer grades through a ~100-entry Algebra-I-course-name allowlist that
  predates this PR, even though the CTE's only surviving outputs
  (`is_ap_course`, `is_honors_course`) don't need that specific allowlist at all
  -- a transfer student's AP or Honors course not on this historical list is
  silently excluded from `has_participated_in_ap_courses` / `_honors_courses`.
  Flagged by `claude-review`; worth a deliberate decision (drop the filter, or
  confirm/document why it should stay) in a follow-up, not resolved here.
- Column-level `description:` coverage across the eight models' properties YAML
  is uneven -- only columns whose logic changed this cycle are documented; most
  pre-existing columns (all of `csgf_hs_act`/`csgf_hs_sat`/
  `csgf_hs_postsec_pathways`, most of `csgf_enrollment`/`csgf_hs_grad_data`)
  still have none. Flagged by `claude-review`; left as incremental scope rather
  than backfilled in this PR.
