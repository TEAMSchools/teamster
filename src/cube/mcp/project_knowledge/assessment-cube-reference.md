# Assessment Cube — Data-Usage Reference

This file documents settled Cube data-usage conventions for assessment work —
what fields mean and how the cube behaves, verified where noted. Undecided
policy defaults are never stated here as rules; they are only flagged and
logged, per the `Flag, don't invent` rule in `assessment-cube-orchestrator.md`.

## Shared conventions

- **`response_type`** takes the values `overall`, `standard`, `group`, or `null`
  (singular `standard` / `group` — not the older `standards` / `groups`). Values
  are not additive across types. Default to `overall` unless a standard- or
  group-level breakdown is explicitly requested.
- **Grain.** `count_scores` is additive and resilient — it succeeded across
  every logged session. `count_students` is a distinct count and is heavy and
  fragile at standard grain (timeouts, and an intermittent location-`US` 400
  error on the `dim_student_enrollments` dependency); prefer `count_scores` as
  the fallback at fine grain. Which measure is the _default_ for a count/share
  question is an open decision — flag and log it, don't answer it.
- **Performance bands.** Use the numeric `performance_band_label_number`, not
  the `proficiency_level` label string — `proficiency_level`'s label set is
  inconsistent across assessment families. The abbreviation crosswalk (band 1 =
  "Far Below", band 2 = "Below"; `FB`, `B`, `B/FB` = bands 1-2) is **[VERIFY]**
  — confirm it against the live label set before publishing or relying on it.
- **Subject fields.** `discipline` is the course/section subject crosswalk
  (value `Math`); `academic_subject` is the tested subject (value `Mathematics`,
  full word). They answer different questions — do not use one in place of the
  other.
- **Enrollment resolution.** Filter `enrollment_resolution = subject_section`
  for course- or section-level rollups. `homeroom` rows also exist in the same
  field — don't mix the two without an explicit reason.
- **Teacher attribution.** Lead-teacher fields are in the schema as of
  2026-07-24 (`staff_lead_teacher_full_name`, `lead_teacher_staff_key`), aliased
  onto the assessment view from `student_section_enrollments`. They require the
  `student_section_enrollments_view` to be present — force-refresh `meta` if the
  fields appear to be missing.
- **Domain rollup.** `response_type_root_description` is the CCSS domain rollup.
  It is reliable for CCSS-aligned content and **unreliable for FL state-aligned
  standards** — do not use it for FL domain rollups (see FL state, below).

## Internal (Illuminate)

- Module types are `QA`, `MQQ`, and `CRQ` (`module_type`); `module_code` values
  look like `QA3`. The exact internal `assessment_type` enum value is
  **[VERIFY]** — confirm it against the live connector before publishing or
  relying on it.
- Pooling `QA` / `MQQ` / `CRQ` mixes instruments of differing difficulty (in one
  region, `CRQ` was ~60% of that region's middle-school math records). Whether a
  multi-instrument mastery question should pool instruments or report per
  instrument is an open decision — flag and log it, don't answer it.
- `response_type_root_description` (the CCSS domain rollup) is reliable here.
- **Sanity-check watch-out.** Internal "overall" mastery cut-scores may be
  calibrated far lower than state proficiency — in one region, `QA3` overall
  math mastery ran approximately 8.6% against a 50%+ FAST PM3 rate on the same
  population. Flag a large internal-vs-state gap for team review rather than
  treating it as a finding; the internal mastery threshold is trusted from the
  field description, not independently verified.

## NJ state

- `assessment_type` enum values: `state_nj_njsla`, `state_nj_njsla_science`,
  `state_nj_njgpa`.
- `academic_year` is unreliable/null for some state slices — filter school year
  via a `date_taken` window until a reliable crosswalk exists.
- Student identifier: the district ID field is null for NJ rows; only
  `lea_student_identifier` is populated. The canonical NJ student identifier is
  **[VERIFY]** — confirm it against the live connector before publishing or
  relying on it.
- `response_type_root_description` (the CCSS domain rollup) is reliable for NJ.

## FL state

- `assessment_type` enum values: `state_fl_fast`, `state_fl_science`,
  `state_fl_eoc`.
- FAST administration windows are `PM1` / `PM2` / `PM3` (field
  `administration_period`); `PM3` is typically the spring window.
- **Hard rule: `academic_year` is 100% null for `state_fl_fast`.** The standard
  year filter does not work for FAST rows. Map the school year from the
  `date_taken` calendar year instead (for example, `PM3` in calendar 2026 = the
  2025-26 school year).
- `is_mastery = True` matches Level 3+ for FAST (verified).
- "Florida region" resolves to `state = FL` / `region_name = Miami`. Empirically
  all FL rows are Miami, but flag this when it matters — no documented semantic
  link ties `state = FL` to `region_name = Miami`.
- **Hard rule: `response_type_root_description` is unreliable for FL
  state-aligned standards.** Do not use it for FL domain rollups.
