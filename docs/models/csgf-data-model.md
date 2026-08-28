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
| `csgf_hs_grad_data`        | One row per cohort × school       | **All years** (unfiltered — see [Known risks](#known-risks))                                        |
| `csgf_hs_postsec_pathways` | One row per grade-12 student      | **All years** (unfiltered)                                                                          |

Year anchoring is deliberately inconsistent across these eight models — this was
flagged in [issue #4897](https://github.com/TEAMSchools/teamster/issues/4897)
and confirmed here by reading each model's SQL directly, not by trusting the
issue's description. Practical consequence: a data problem in either the current
or prior year can affect `csgf_enrollment`; a problem in _any_ historical year
can affect the two "all years" models. It also means 7 of the 8 models are
computable as soon as CSGF's Preliminary Questions task is done, without waiting
on anything about the current in-progress year — only `csgf_enrollment`'s
current-year grain needs this year's Oct 1 count day to have happened.

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

### `csgf_enrollment` under-reports Miami

The model is driven by `stg_powerschool__schools`, a frozen PowerSchool-era
Miami school catalog never updated after Miami's cutover to Focus as its SIS. As
of this cycle: two Focus-marked-`(Closed)` schools (Sunrise, Liberty) still
appear with every column null, and three schools with real enrolled Focus
students are silently **missing** entirely (not null — absent rows) because the
join to the stale catalog fails: KIPP Miami Tech (95 HS students), KIPP Legacy
Elementary (173), KIPP Legacy Middle (32) — roughly 300 of Miami's ~1,755
enrolled students. Owner is aware and fixing separately; confirm it's resolved
before trusting this model's Miami rows.

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
current cycle. Confirmed mismatches for 2026-2027: "AP US History" → "AP United
States History," "AP US Government and Politics" → "AP United States Government
and Politics," "AP Pre-Calculus" → "AP Precalculus." Both models now carry an
identical `case` remap for these — **update both together** whenever CSGF's list
changes, or one model silently drifts from the other.

Separately, `csgf_hs_ap_offerings` pivots on a hardcoded list of AP course
names, so a newly-offered course not yet added to the pivot's `IN` list drops
out of the extract silently (no error). Confirm current AY coverage each cycle
per the skill's checklist.

### School names need the same per-cycle check

Raw PowerSchool `school_name` doesn't always match CSGF's expected string —
`csgf_hs_enrollment` and `csgf_hs_ap_offerings` both special-case
`KIPP Cooper Norcross High` → `KIPP Cooper Norcross High School` for this
reason. Confirmed for 2026-2027: both models' full-name output matches CSGF's
expected names for all three current HS schools. **`csgf_hs_grad_data` is an
open question, not yet confirmed** — it outputs abbreviated codes (`KHS`, `NCA`,
`NLH`) instead of full names, and whether that's actually what CSGF's HS Grad
Data tab expects has not been checked against the template.

### `csgf_hs_grad_data`'s cohort scope is an open design question

The model computes a `graduated` CTE with a real year filter
(`cohort = current_academic_year AND academic_year = current_academic_year - 1`)
that is **never referenced** by the final `SELECT` — dead code, confirmed by
reading the whole file. The final output (from `grad_roster`, which has no
year/cohort filter beyond `school_level = 'HS'`) is unfiltered, so it returns
every cohort ever recorded, not just the current one.
[Issue #4897](https://github.com/TEAMSchools/teamster/issues/4897) flagged this
as a decision nobody's made yet — whether the sheet should carry one cohort or
all of them — and documented it rather than changing it. Still open.

!!! warning "SED field definition — unresolved conflict, do not treat either
claim as settled" CSGF's new "Socioeconomically Disadvantaged (SED)" field on
the HS Enrollment tab instructs submitters to "use what is valid for the state."
`csgf_hs_enrollment`'s `student_is_frl` was widened this cycle to include
`lunch_status = 'FDC'` alongside `'F'` and `'R'`, on the understanding that
`FDC` means "Free via Direct Certification" — a federal/nationwide USDA
meal-program category, not state-specific, which most states (including NJ)
incorporate into their own economically-disadvantaged definitions. That reading
is backed by this repo's own documented source (`stg_powerschool__students.yml`:
`"FDC=Free-DC"`).

    A separate claim — first relayed as "Florida Direct Certification," then
    reasserted as "FDC is valid for Florida" — says `FDC` is a
    Florida-specific code, which would make it invalid for NJ's SED
    definition (KTAF's HS-operating regions, Camden and Newark, are both in
    NJ, not Florida). Both claims could be true of *different* things that
    happen to share the abbreviation `FDC`, or one is simply wrong about
    *this specific field*. **This has not been independently verified either
    way** — confirm with whoever owns PowerSchool lunch-status setup, or
    with NJ's own state SED/economically-disadvantaged regulatory
    definition, before trusting `student_is_frl`'s current logic for SED
    purposes specifically. It may be correct for KTAF's general FRL flag
    even if it turns out wrong for the NJ-specific SED field.

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

- Whether `student_is_frl`'s FDC inclusion is correct for the new SED field
  specifically (see the warning above) — unresolved.
- `csgf_hs_grad_data`'s cohort scope (one vs. all) and school-name format
  (abbreviated vs. full) — both unresolved.
- The other five HS-scoped models' Miami/Focus course-data gap for next cycle —
  only verified for `csgf_hs_enrollment` so far.
- None of the eight models currently have a uniqueness test, which this repo's
  convention requires for `rpt_` models — not yet addressed.
