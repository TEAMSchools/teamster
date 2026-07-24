# Assessment Cube — Data-Usage Reference

Settled mechanics and true field meanings for `student_assessment_scores_view`,
the single Cube view covering KIPP internal (Illuminate) interims, vendor normed
diagnostics (i-Ready, DIBELS, STAR), and NJ/FL state assessments. This file
documents how the cube behaves. It does not decide undecided policy defaults —
the `Flag, don't invent` rule in `assessment-cube-orchestrator.md` governs
those.

## Shared conventions

Apply to every assessment source unless a source section overrides them.

- **Pick the source with `assessment_type`, not `is_internal_assessment`.**
  `is_internal_assessment` is TRUE only for Illuminate (KIPP-authored interims);
  i-Ready, DIBELS, and STAR are FALSE despite being used internally. To select a
  source, filter `assessment_type`. The full value list: `illuminate`, `iready`,
  `dibels`, `star`, `state_nj_njsla`, `state_nj_njsla_science`,
  `state_nj_njgpa`, `state_fl_fast`, `state_fl_science`, `state_fl_eoc`.
  - The field's own description lists coarser values (`state_nj` / `state_fl` /
    `college` / `ap`) that are NOT the real values — trust this list (verified
    against the live connector 2026-07-24).
- **`response_type` — always filter it explicitly.** Values: `overall`,
  `standard`, `group`, `null` (singular `standard` / `group`, not the older
  `standards` / `groups`). Not additive across types. Default to `overall`
  unless a standard- or group-level breakdown is explicitly requested. Only
  Illuminate populates `standard` / `group`; every other source is
  `response_type = null` (overall only). To isolate those null rows, filter with
  operator `notSet` (or `set` for present) — `equals "null"` matches the literal
  string, not SQL NULL, and silently returns zero rows. This holds for any NULL
  filter.
- **Headline metric: `pct_proficient`.** It is the one score measure comparable
  across the incompatible scales of all sources (proficient scores / total).
  `is_mastery` is the underlying per-score proficient flag. `scale_score`,
  `percent_correct`, `avg_scale_score`, and `avg_percent_correct` are
  scope-bound — meaningful only within one source/subject/grade; pooling them
  across sources returns a valid-looking but meaningless number. Use
  `pct_proficient` / `is_mastery` for any cross-source comparison.
- **Grain.** `count_scores` is additive and resilient (scored-response count) —
  it succeeded across every logged session. `count_students` is a distinct
  student count and is heavier and historically fragile at fine (standard) grain
  (timeouts, and an intermittent location-`US` 400 on the
  `dim_student_enrollments` dependency); `count_scores` is the reliable fallback
  there.
- **A dimension-only pull silently de-duplicates.** A query with no measure
  collapses identical rows and hides true row counts; add a measure (e.g.
  `count_scores`) or the primary key (`assessment_score_key`) to see the real
  count. This is how the i-Ready row duplication (below) was found.
- **Performance bands are Illuminate-only.** `performance_band_label_number`
  (integer 1–5) is populated only for Illuminate; it is null for state and for
  i-Ready/DIBELS/STAR. Where it applies, band 1 = the "Far Below" tier and band
  2 = "Below" (`FB` = band 1, `B` = band 2, `B/FB` = bands 1–2). **Use the
  integer `performance_band_label_number`, never the `proficiency_level` label
  text** — the label strings are wildly inconsistent (dozens of variants per
  band number). Other sources use their own `proficiency_level` scales (see each
  section).
- **Two different subject fields.** `academic_subject` is the subject _tested_
  (e.g., `Mathematics`, `English Language Arts`); `discipline` is the _course_
  subject from the course crosswalk (e.g., `Math`, `ELA`). They answer different
  questions — do not use one in place of the other.
- **Three different grade fields.** `grade_band` is a school-level attribute
  (the band a location serves — `ES` / `MS` / `HS`), not a per-student grade;
  filtering `grade_band = 'MS'` is a school proxy, not a student-grade filter.
  For a student's actual grade use `grade_level`; for the grade an assessment
  targets use `grade_level_tested`.
- **Section/teacher rollups: filter `enrollment_resolution = subject_section`**
  (`homeroom` rows also exist in the same field). Lead-teacher attribution is
  available via `staff_lead_teacher_full_name` / `lead_teacher_staff_key`,
  aliased from `student_section_enrollments`; force-refresh `meta` if the
  lead-teacher fields appear to be missing.
- **Time.** `academic_year` is a July-start integer (2025 = the 2025-26 school
  year). It is populated for Illuminate but **null for state AND for
  i-Ready/DIBELS/STAR** — for those sources filter the school year via a
  `date_taken` window (`date_taken` is fully populated there). `date_taken` is
  nullable for a small share of Illuminate rows with no recorded sitting.
- **Domain rollup: `response_type_root_description`** is the CCSS domain rollup
  — reliable for CCSS-aligned content, unreliable for FL state-aligned
  standards. Illuminate only (null elsewhere, since `response_type` is null
  elsewhere).
- **Open decisions — flag, never assume a value** (per the orchestrator):
  minimum-sample suppression threshold; intervention tier cut-scores;
  pool-vs-per-instrument for multi-module "overall mastery"; which subjects
  count as "math"; and the default grain (record vs distinct-student) for
  count/share questions. None has a documented network default — surface the
  assumption and log it.

## Internal — Illuminate (KIPP interims)

- `assessment_type = 'illuminate'`; `is_internal_assessment = true`. The only
  source with standards breakdowns.
- **Module types:** `module_type` / `module_code` cover QA (Quick Assessments),
  MQQ (Multiple-Choice Quick Questions), and CRQ (Constructed Response
  Questions); `module_code` looks like `QA1`, `QA3`.
- **Measures:** `pct_proficient_formative` pools all three formative module
  types (QA + MQQ + CRQ); `pct_proficient_crq` isolates CRQ. (Whether to pool
  across module types or report per-instrument is an open decision — flag it.)
- **`response_type`:** `overall` / `standard` / `group`. Use `overall` unless a
  standard/group breakdown is requested.
- **Bands:** `performance_band_label_number` applies (band 1 = Far Below … 5 =
  Above); use the integer, not the label.
- `response_type_root_description` (the CCSS domain rollup) is reliable here.
- **Sanity-check watch-out:** Illuminate "overall" mastery cut-scores can read
  much lower than state proficiency for the same students — the two scales are
  not directly comparable, so a wide internal-vs-state gap is often a
  calibration artifact. Flag such a gap for team review rather than reporting it
  as a finding.

## Vendor normed diagnostics — i-Ready

- `assessment_type = 'iready'`; `is_internal_assessment = false`. Subjects
  (`category`): Math and ELA.
- `response_type = null` (overall only — no standards breakdown).
- **Proficiency:** `proficiency_level` is i-Ready's grade-level placement scale
  — `3 or More Grade Levels Below`, `2 Grade Levels Below`,
  `1 Grade Level Below`, `Early On Grade Level`, `Mid or Above Grade Level`.
  `is_mastery` is populated. `performance_band_label_number` is null (band
  shorthand does not apply).
- **Time:** `academic_year` is null — filter the school year via `date_taken`.
- **Known duplication (handle before counting).** i-Ready score rows are
  currently duplicated roughly 2x per student per administration — identical in
  every field except the `assessment_score_key` surrogate key (a suspected
  ingestion fan-out, tracked as a Cube-model defect). De-duplicate on
  `assessment_score_key`, or use `count_students` rather than `count_scores`,
  until it is fixed.
- **Authoritative attempt.** `is_replacement` is not populated for i-Ready, so
  when a student has genuine multiple attempts in a window, pick the
  authoritative score by most recent `date_taken`.
- Documented from the live schema and one working-group session (Camden ES ELA
  DIBELS-vs-i-Ready concordance) — confirm interpretations before external use.

## Vendor normed diagnostics — DIBELS

- `assessment_type = 'dibels'`; `is_internal_assessment = false`. Subject
  (`category`): ELA.
- `response_type = null` (overall only).
- **Proficiency:** `proficiency_level` is the DIBELS benchmark tier —
  `Well Below Benchmark`, `Below Benchmark`, `At Benchmark`, `Above Benchmark`.
  `is_mastery` is populated. `performance_band_label_number` is null.
- **Time:** `academic_year` is null — filter via `date_taken`.
- Documented from the live schema and one working-group session (used as the
  comparison instrument in a Camden ES ELA concordance) — confirm before
  external use.

## Vendor normed diagnostics — STAR

- `assessment_type = 'star'`; `is_internal_assessment = false`. Subjects
  (`category`): ELA and Math.
- `response_type = null` (overall only).
- **Proficiency:** `proficiency_level` is `Level 1`–`Level 5` (a share of rows
  have null `proficiency_level` / `is_mastery`). `performance_band_label_number`
  is null.
- **Time:** `academic_year` is null — filter via `date_taken`.
- Not exercised in the working-group sessions; documented from the live schema —
  confirm before external use.

## NJ state assessments

- `assessment_type` values: `state_nj_njsla` (NJSLA ELA/Math),
  `state_nj_njsla_science` (NJSLA Science), `state_nj_njgpa` (NJGPA). `category`
  carries the subject (ELA / Math / Science).
- `response_type = null` (overall only — no standards breakdown for state).
- **Proficiency:** `proficiency_level` is the state achievement level;
  `is_mastery` is the proficient flag. `performance_band_label_number` is null.
- **Time:** `academic_year` is null for state — filter the school year via a
  `date_taken` window. `administration_period` is the testing season (Fall /
  Winter / Spring).
- **Student identifier:** for NJ, `lea_student_identifier` (KIPP's SIS number)
  is the canonical student number; `district_student_identifier` is null for NJ
  (host-district IDs are Miami-only). `state_student_identifier` is the
  state-assigned number.

## FL state assessments

- `assessment_type` values: `state_fl_fast` (FAST ELA/Math), `state_fl_science`
  (Science), `state_fl_eoc` (end-of-course, e.g. Civics). `category` carries the
  subject.
- `response_type = null` (overall only).
- **Proficiency:** `is_mastery` is the proficient flag — for FAST this matches
  Level 3+. `proficiency_level` carries the achievement level.
  `performance_band_label_number` is null.
- **Time:** `academic_year` is null for FL (100% null for FAST) — filter the
  school year via a `date_taken` window (for example, `PM3` in calendar 2026 =
  the 2025-26 school year). `administration_period` is the FLDOE window (FAST
  `PM1` / `PM2` / `PM3`).
- FL is the Miami region (`region_name = 'Miami'` / `state = 'FL'`).
- `response_type_root_description` is unreliable for FL state-aligned standards
  — do not use it for FL domain rollups.
