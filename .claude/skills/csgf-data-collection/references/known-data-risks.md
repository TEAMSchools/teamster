# Known data risks -- verify before submitting

Referenced from `SKILL.md`. Full forensic detail behind each risk the router
summarizes; read this before assuming a fix already landed or that a past
finding still applies unchanged.

**Fixed 2026-09-11: SAT/ACT/AP Scores/AP Offerings must scope to the same
population as HS Enrollment, or CSGF flags "ID not on Enrollment Tab."** HS
Enrollment's own instructions say to only include students who completed the
school year (`enroll_status in (0, 3)`); the other four HS-scoped models had no
such filter and included mid-year transfers-out too. Full writeup in
`docs/models/csgf-data-model.md`. If you see this exact error on a future
cycle's HSDC tabs, check whether a newly-added HS-scoped model has the same gap
before assuming it's a data problem.

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
in-progress year -- see "Front-load the tabs" in
[`hsdc-mechanics.md`](hsdc-mechanics.md).

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
verification). PR #5059 has since merged and deployed -- these fixes are live.

**New this cycle (2026-09-11): CSGF added "Total Number of Graduates" to the HS
Grad Data task** -- a real, distinct field from the existing "# Stud in Adj
Cohort Grad w/i 4 Yrs" column (which is `total_4yr_grad`). Its tooltip reads
"Include All Students Who Received a Diploma" -- i.e. every diploma recipient
this year regardless of cohort, not just on-time 4-year grads. Added a new
`all_graduates` CTE / `total_graduates` column to
`rpt_gsheets__csgf_hs_grad_data` (no cohort filter, just
`academic_year + 1 = current_academic_year and exitcode = 'G1'`, grouped by
school) -- see `docs/models/csgf-data-model.md` for the full writeup. Real
values entered for the 2026-2027 cycle: KIPP Cooper Norcross High School 94,
KIPP Newark Collegiate Academy 168, KIPP Newark Lab High School 129. **When a
Portal task adds a column mid-cycle like this, hover its tooltip for CSGF's own
definition before assuming it maps to an existing model column -- two columns
that sound similar (here, "graduates" vs. "4-year cohort grads") can be
genuinely different metrics.**

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
this will fail validation for every school as-is (24 rows as of 2026-09-23;
re-check the row count -- it's moved before), not just Miami's. No dbt fix
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
task.** Diffed column-by-column against
[`field-definitions.md`](field-definitions.md) section 2 -- Total Seat Capacity
2026-27, Total Seats When Growth Plan Complete, 2024-25 ADA Rate, 2024-25
Chronic Absenteeism Rate, 2025-26 Teacher Counts, Teacher Retention, and the
co-leader row of School Leader Demographics are all real fields on this task
with no column here. **Confirmed not a gap** -- per this cycle's item-list doc
(see `SKILL.md`'s "Who this skill is for"), the budget/seat fields are Laszlo's,
and Teacher Count/Retention plus the leader-info fields are Kevin's -- both
entered directly on the Portal, not sourced through this dbt model.
**ADA%/Chronic Absenteeism% belong to Walters** (confirmed by the collection
owner 2026-09-22, after this doc first flagged them as unassigned in the
item-list doc) -- also entered directly on the Portal, not sourced through this
dbt model. Documented so a future reader doesn't mistake any of this for an
oversight.

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
