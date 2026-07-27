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
  - Treat this list as current, not closed: other categories exist upstream
    (`college`, `ap`, `state_nj_parcc`, `state_fl_fsa`, plus `_unknown`
    fallbacks) but carry no scores on this view today.
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
  row count.
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
- **Time.** `academic_year` (July-start integer; 2025 = the 2025-26 school year)
  and `academic_year_label` (the `"2025-2026"` string form) now resolve for
  every source — use `academic_year_label` as the canonical year filter. One
  nuance: the date each source's year is derived from differs — the
  administration date for Illuminate/college, the student's completion (test)
  date for state and vendor — so a within-month _cross-source_ date cut (e.g.
  "scores in May") mixes those two date concepts. `date_taken` is a standalone
  field (nullable for a small share of internal rows); prefer the
  `academic_year` / `academic_year_label` members for year rollups.
- **`administration_period` is populated for every source except Illuminate**,
  but the vocabulary differs by source — so never filter it without also scoping
  `assessment_type`. i-Ready and DIBELS use `BOY` / `MOY` / `EOY`; STAR and NJ
  state use `Fall` / `Winter` / `Spring`; FL state uses the FLDOE window (`PM1`
  / `PM2` / `PM3`). It is null only for `illuminate`. (The field's own
  description covers the state and college windows only — it does not mention
  the vendor values.)
- **There is no growth measure.** The view carries point-in-time scores only —
  no native growth, gain, or progress-to-target measure exists for any source.
  Any growth figure is therefore constructed by the analyst: say so explicitly,
  and see the i-Ready section for why cross-grade-band growth comparisons are a
  trap.
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
- **Time:** `academic_year` / `academic_year_label` now resolve (derived from
  the completion/test date) — filter the school year with them.
- **Administrations:** `administration_period` = `BOY` / `MOY` / `EOY`, plus
  `Outside Round` for sittings taken outside the three benchmark windows.
  Filtering to only `BOY` / `MOY` / `EOY` silently drops the `Outside Round`
  rows — scope deliberately and state which windows you used.
- **Region coverage: Newark, Camden, and Miami only — there is no i-Ready data
  for Paterson.** A "compare i-Ready across all regions" question therefore
  returns three of the four regions; say so rather than implying network-wide
  coverage.
- **Growth is not in the model, and scale scores do not normalize across grade
  bands.** i-Ready's vendor growth norms (typical growth, percent progress to
  typical growth) are not ingested, so that metric cannot be computed — do not
  approximate it and label it with the vendor's name. A BOY-to-EOY scale-score
  delta _is_ computable, but it compresses at higher grades, and dividing by the
  BOY baseline makes the distortion worse because the baseline itself rises with
  grade. Report growth **within** a grade band, never pooled across ES and MS:
  pooling makes every MS school look low-growth from scale mechanics alone, not
  from instruction.
- **`is_replacement` is Illuminate-only by design** — null for i-Ready (and all
  vendor/state sources), not a gap. Genuine multiple sittings occur even within
  a single benchmark window, so dedup to the most recent `date_taken` per
  student per window before computing anything student-level.
- Documented from the live schema and two working-group sessions (a Camden ES
  ELA DIBELS-vs-i-Ready concordance, and a BOY-to-EOY growth-quadrant analysis)
  — confirm interpretations before external use.

## Vendor normed diagnostics — DIBELS

- `assessment_type = 'dibels'`; `is_internal_assessment = false`. Subject
  (`category`): ELA.
- `response_type = null` (overall only).
- **Proficiency:** `proficiency_level` is the DIBELS benchmark tier —
  `Well Below Benchmark`, `Below Benchmark`, `At Benchmark`, `Above Benchmark`.
  `is_mastery` is populated. `performance_band_label_number` is null.
- **Time:** `academic_year` / `academic_year_label` now resolve — filter the
  school year with them.
- **Administrations:** `administration_period` = `BOY` / `MOY` / `EOY`, the same
  benchmark-window vocabulary as i-Ready.
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
- **Time:** `academic_year` / `academic_year_label` now resolve — filter the
  school year with them.
- **Administrations:** `administration_period` = `Fall` / `Winter` / `Spring` —
  season names, **not** the `BOY` / `MOY` / `EOY` vocabulary i-Ready and DIBELS
  use. Do not carry a benchmark-window filter across from those sources.
- Not exercised in the working-group sessions; documented from the live schema —
  confirm before external use.

## NJ state assessments

- `assessment_type` values: `state_nj_njsla` (NJSLA ELA/Math),
  `state_nj_njsla_science` (NJSLA Science), `state_nj_njgpa` (NJGPA). `category`
  carries the subject (ELA / Math / Science).
- `response_type = null` (overall only — no standards breakdown for state).
- **Proficiency:** `proficiency_level` is the state achievement level;
  `is_mastery` is the proficient flag. `performance_band_label_number` is null.
- **Time:** `academic_year` / `academic_year_label` now resolve for state
  (derived from the test date) — filter the school year with them.
  `administration_period` is the testing season (Fall / Winter / Spring).
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
- **Time:** `academic_year` / `academic_year_label` now resolve for FL (derived
  from the test date) — filter the school year with them (e.g. `PM3` in spring
  2026 lands in the 2025-26 year). `administration_period` is the FLDOE window
  (FAST `PM1` / `PM2` / `PM3`).
- FL is the Miami region (`region_name = 'Miami'` / `state = 'FL'`).
- `response_type_root_description` is unreliable for FL state-aligned standards
  — do not use it for FL domain rollups.
