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
- **`response_type` — always filter it explicitly. The column is non-nullable**,
  with exactly four values (singular `standard` / `group`, not the older
  `standards` / `groups`): `overall`, `group`, `standard`, `not_taken`. Not
  additive across types. Default to `overall` unless a standard- or group-level
  breakdown is explicitly requested.
  - **`overall`** — the summary row for every source (Illuminate, i-Ready,
    DIBELS, STAR, NJ state, FL state). Filter `response_type = 'overall'` to
    isolate it — this is the only cross-source filter that yields one row per
    sitting. (Older guidance said to isolate the non-Illuminate sources with
    operator `notSet`, because `response_type` used to be `null` for every one
    of them. That idiom now returns zero rows — the column is populated on every
    row — so use `response_type = 'overall'` wherever `notSet` used to be the
    instruction.)
  - **`group`** — named breakdowns: Illuminate reporting groups, and now also
    i-Ready domains and DIBELS subtests.
  - **`standard`** — Illuminate standards only.
  - **`not_taken`** — an Illuminate assessment a student was expected to take
    but has no recorded response for.
  - `response_type_code` is populated on Illuminate `standard` rows and on
    vendor `group` rows (i-Ready domain codes, DIBELS subtest codes) — it is
    **NULL on Illuminate `group` rows.** Do not assume `group` always carries a
    code.
- **Querying the i-Ready/DIBELS breakdowns:** filter `response_type = 'group'`
  and break out by `response_type_description` (the domain or subtest name);
  combine with `assessment_type` to pick `iready` vs `dibels` specifically,
  since `group` also covers Illuminate reporting groups. `assessment_type` is
  now carried in the pre-aggregation, so these queries hit the rollup rather
  than falling through to a live query.
- **Proficiency measures exclude `not_taken`.** `count_scores`, the
  `_sum_proficient`-derived measures, and the formative/CRQ pairs
  (`pct_proficient_formative`, `pct_proficient_crq`) all exclude `not_taken`
  rows now — a student who was not tested no longer silently drags down the
  denominator. This moved the topline Illuminate `pct_proficient` from 45.80% to
  49.54%. The backing pre-aggregation is renamed `proficiency_rollup_v2`.
- **Headline metric: `pct_proficient`.** It is the one score measure comparable
  across the incompatible scales of all sources (proficient scores / total).
  `is_mastery` is the underlying per-score proficient flag. `scale_score`,
  `percent_correct`, `avg_scale_score`, and `avg_percent_correct` are
  scope-bound — meaningful only within one source/subject/grade; pooling them
  across sources returns a valid-looking but meaningless number. Use
  `pct_proficient` / `is_mastery` for any cross-source comparison.
- **A cross-instrument gap is a calibration artifact until proven otherwise.**
  Two instruments measuring the same students in the same year routinely
  disagree by double digits, because each carries its own proficiency definition
  and cut-score. This holds for every pairing — internal-vs-state,
  internal-vs-vendor, and vendor-vs-state alike. Report the two rates side by
  side, label the difference as a gap between instruments rather than a gap in
  achievement, and flag it for team review instead of presenting it as a
  finding. (A logged session had to extend this reasoning by analogy because it
  was documented for internal-vs-state only; it applies generally.)
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
- **Performance bands are Illuminate-only, and a band number only means
  something inside its own band set.** `performance_band_label_number` is
  populated only for Illuminate; null for state and for i-Ready/DIBELS/STAR.
  **It is not a 1–5 scale and not comparable across assessments.** Each
  Illuminate assessment points at a configured performance band set, and the
  sets disagree on cut points, on band count, and on where mastery starts. The
  sets carrying the most 2025-26 `overall` scores:

  | Band set                    | Cut points (percent correct) | Mastery starts | Scores  |
  | --------------------------- | ---------------------------- | -------------- | ------- |
  | KIPP T and F 2021-22 MS PB  | 0 / 25 / 45 / 65 / 85        | band 4         | 497,445 |
  | HS Summative (non-AP)       | 0 / 40 / 60 / 75 / 88        | **band 3**     | 273,585 |
  | KIPP T and F 2021-22 ES PB  | 0 / 30 / 50 / 70 / 85        | band 4         | 249,755 |
  | KIPP T and F 2026-27 K-2 PB | 0 / 30 / 60 / 80 / 90        | band 4         | 216,665 |
  | District Default            | 0 / 60 / 70 / 80 / 90        | band 4         | 64,735  |
  | FAST Performance Bands 3-4  | 8 bands                      | band 6         | 113,304 |
  | SY25-26 Practice SAT Math   | 45 bands                     | band 19        | 11,295  |

  Three consequences. **The mastery bar ranges from 60% to 80% correct depending
  on the band set**, so `is_mastery` and `pct_proficient` on Illuminate are not
  one fixed standard — say which assessments a rate covers. **Band counts are 5,
  8, and 45**, so never assume band 5 is the top. **Never pool band numbers
  across assessments** unless you have confirmed they share a band set; a "band
  3" cohort assembled across ES, MS, and K-2 sets mixes three different percent
  ranges. Still prefer the integer over the `proficiency_level` label text
  within a set — the label strings carry dozens of variants per band number.

- **Two different subject fields, and `academic_subject` values are
  source-dependent.** `academic_subject` is the subject _tested_; `discipline`
  is the _course_ subject from the course crosswalk (e.g. `Math`, `ELA`). They
  answer different questions — do not use one in place of the other.
  - **Illuminate has no `English Language Arts` value** — filtering for it
    returns zero rows. Illuminate's ELA-equivalent is **`Text Study`** (4.7M
    scores), alongside `Writing`, `English 100`–`400`, `CCR 1`–`4`,
    `Composition 200`, and AP Language / AP Literature. Math-side it uses
    `Mathematics` plus `Algebra I`, `Algebra I MS`, `Algebra II`, `Geometry`,
    `Pre-Calculus`, `Math 4`.
  - **At K-2, `Text Study` is the _only_ ELA-equivalent subject present** — no
    `Writing`, `CCR`, `English 100`–`400`, or AP at those grades. So the "which
    subjects count as ELA" question has an empirical answer for the K-2 band
    even though it stays open for the upper grades.
  - State and vendor sources use the plainer labels (`English Language Arts`,
    `Mathematics`). Check the values for the source you are querying before
    filtering — a wrong label returns zero rows silently, not an error.
- **Three different grade fields, and `grade_level_tested` is null for every
  vendor diagnostic.** `grade_band` is a school-level attribute (the band a
  location serves — `ES` / `MS` / `HS`), not a per-student grade; filtering
  `grade_band = 'MS'` is a school proxy, not a student-grade filter. For a
  student's actual grade use `grade_level`; for the grade an assessment targets
  use `grade_level_tested`.
  - **`grade_level_tested` is populated for Illuminate (99.8%) and every state
    source, and is null on every i-Ready, DIBELS, and STAR row — across every
    `response_type` value, including the `group`-level domain/subtest rows.**
    Filter a vendor diagnostic by it and you get zero rows with no error. This
    has cost two logged sessions a false "no data." For vendor sources, always
    use `grade_level`.
  - The two also answer different questions where both exist, so a result can
    change materially depending which you pick — say which one you used.
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
  standards. Illuminate only — the vendor and state branches hardcode it NULL;
  there is no vendor or state equivalent. (i-Ready domains and DIBELS subtests
  surface through `response_type_description` at `response_type = 'group'`
  instead, not through this field.)
- **The view is enrollment-scoped — its totals are not the vendor's or the
  state's totals.** A score appears only if it resolves to a section enrollment;
  scores that don't resolve are out of scope by design. For 2025-26 i-Ready that
  is about 6% of tests, unevenly: Newark 8.0%, Camden 4.2%, Miami 2.5% — and
  `Outside Round` sittings lose roughly a third. So a Cube count will not
  reconcile to a vendor or state report, and the gap is expected, not a bug. Say
  which one you are quoting.
- **Region coverage is uneven, and Paterson is the outlier.** Paterson carries
  Illuminate and DIBELS for 2025-26 only, plus NJSLA and NJSLA-Science for
  2022-23 and 2023-24 — and no i-Ready, STAR, or NJGPA at all. Its state history
  therefore reaches back further than its internal history, the reverse of every
  other region (Newark and Camden run Illuminate from 2014-15). A narrow
  Paterson result is expected coverage, not a load failure; say which regions a
  "network-wide" answer actually covers.
- **`is_foundations` marks intervention courses, and it reaches this view.**
  Sourced from `dim_courses` through the course join, `TRUE` when the section is
  a Foundations (intervention) course. It is the only intervention signal on the
  view — there is no program- or MTSS-tracking dimension — so it is the closest
  available proxy for "was this student receiving intervention." Treat it as
  course enrollment, not as a record of services delivered.
- **Resolve staff names against `staff_directory` before filtering.**
  `staff_lead_teacher_full_name` stores `Last, First`, and a participant's
  spelling will not always match (one logged session searched "Schaffer" against
  a record filed as "Shaffer"). Look the name up first rather than assuming a
  zero-row result means the teacher has no students.
- **Open decisions — flag, never assume a value** (per the orchestrator):
  intervention tier cut-scores; pool-vs-per-instrument for multi-module "overall
  mastery"; which subjects count as "math" _and_ which count as "ELA" (see the
  Illuminate subject list above); whether grade-band reporting keys on
  `grade_level` or `grade_level_tested`; the default grain (record vs
  distinct-student) for count/share questions; what "progress" or "did not make
  progress" means for a growth question (tier movement, scale-score delta, or a
  mastery flip); and whether "top performing" means level or movement. None has
  a documented network default — surface the assumption and log it.

## Internal — Illuminate (KIPP interims)

- `assessment_type = 'illuminate'`; `is_internal_assessment = true`. The only
  source with standards breakdowns.
- **Module types: there are seven, not three.** 2025-26 volumes, `overall`
  scores:

  | `module_type`                           | Codes               | Scores  |
  | --------------------------------------- | ------------------- | ------- |
  | `QA` (Quick Assessments)                | `QA1`–`QA4`, `QA11` | 835,794 |
  | `TP`                                    | `TP1`–`TP8`         | 490,421 |
  | `MQQ` (Multiple-Choice Quick Questions) | `MQQ1`–`MQQ4`       | 472,235 |
  | `CRQ` (Constructed Response Questions)  | `CRQ1`–`CRQ9`       | 353,781 |
  | `UA`                                    | `UA1`–`UA6`         | 140,945 |
  | `ET`                                    | `ET1`–`ET7`         | 132,684 |
  | `WPP`                                   | `WPP1`–`WPP4`       | 37,687  |

  `TP` is the second-largest module type in the network. `TP` / `UA` / `ET` /
  `WPP` together carry 801,737 scores — roughly a third of all module-coded
  Illuminate work — and none of them were documented before. What `TP`, `UA`,
  `ET`, and `WPP` stand for is an open question for the model owner; do not
  invent an expansion.

- **Which module codes exist varies by subject, grade, AND region** — never
  assume a standard checkpoint set. In Newark 2025-26, Math grades 3-4 have no
  `QA4`, and Text Study grades 3-4 have neither `QA3` nor `QA4`, leaving only
  `QA1` / `MQQ2` / `MQQ3` from the familiar set while `ET` / `TP` / `UA` / `WPP`
  make up the majority of available content there. Check what exists for your
  exact subject, grade, and region before building a pooled average — otherwise
  one cell rests on three checkpoints while another rests on five, and the two
  are not comparable.
- **Module codes are not in chronological order by name.** Verify sequence by
  median `date_taken` per `module_code` rather than reading order off the
  numbering; a logged session confirmed an Oct-to-May ordering that the names do
  not imply.
- **`module_code` is not a subject filter — always pair it with
  `academic_subject`.** One module code spans every subject assessed in that
  round. `QA3` in 2025-26 covers 21 distinct `academic_subject` values across
  25,842 `overall` scores, of which `Mathematics` is 7,854 — under a third.
  Filtering `module_code = 'QA3'` alone and calling the result "QA3 math" mixes
  Text Study, Science, Social Studies, the `English 100`–`400` and AP courses,
  and the HS math courses into one number.
- **Measures — `pct_proficient_formative` does not cover all formative work.**
  It filters `module_type IN ('QA', 'MQQ', 'CRQ')`, so it silently excludes
  `TP`, `UA`, `ET`, and `WPP` — about a third of module-coded Illuminate scores.
  If a participant means "all our internal checkpoints," this measure is not it;
  build the rollup explicitly from the module types you intend.
  `pct_proficient_crq` isolates CRQ. (Whether to pool across module types or
  report per-instrument is an open decision — flag it.)
- **`response_type`:** `overall` / `standard` / `group`. Use `overall` unless a
  standard/group breakdown is requested.
- **Bands:** `performance_band_label_number` applies, but read the Shared
  conventions entry first — the number is only meaningful inside the
  assessment's own band set, and the sets differ on cut points, band count, and
  where mastery starts.
- **Normalize standard codes before any standards-level rollup.**
  `response_type_code` and `response_type_description` both carry formatting
  variants for the same standard (`8.EE.C.8.b` vs `8.EE.C.8b`; `y = mx + b` vs
  `y = m x + b`), which splits one standard across two rows and halves each
  one's counts. 2,620 raw codes collapse to 2,565 canonical ones — **55
  standards are fragmented today.** The rule: strip all non-alphanumeric
  characters from `response_type_code`, group on the result, and recompute
  `pct_proficient` as a **count-weighted average of the underlying counts —
  never an average of the two reported percentages.** A logged session
  corroborated this across four grade levels using the code and the description
  as two independent keys; merging one pair moved a standard from a confusing
  split to a clean SY25 16.7% (n=1,356) versus SY26 20.4% (n=1,379).
- **"How many times was this standard assessed" is a distinct count of
  `source_assessment_id`,** not `count_scores`. `count_scores` counts scored
  student responses; the distinct administration count is typically 1–5 per
  standard per year. A standard resting on one administration is a thin
  evidentiary base — say so rather than trending it.
- **A CCSS code's own grade can differ from `grade_level_tested`.** A grade-6
  code appearing in a grade-8 mix is spiral or prerequisite review content, not
  a data error. Flag it for curriculum confirmation instead of excluding it
  silently.
- `response_type_root_description` (the CCSS domain rollup) is reliable here.
- **Sanity-check watch-out:** Illuminate "overall" mastery cut-scores can read
  much lower than state proficiency for the same students — the two scales are
  not directly comparable, so a wide internal-vs-state gap is often a
  calibration artifact. Flag such a gap for team review rather than reporting it
  as a finding.

## Vendor normed diagnostics — i-Ready

- `assessment_type = 'iready'`; `is_internal_assessment = false`. Subjects
  (`category`): Math and ELA.
- **Grade field: use `grade_level`. `grade_level_tested` is null on every
  i-Ready row** — filtering by it returns zero rows silently.
- **`response_type`:** `overall` is the summary row for every sitting; i-Ready
  now also populates `group` for domain-level breakdowns (see Shared conventions
  — filter `response_type = 'group'`, break out by `response_type_description`,
  and pair with `assessment_type = 'iready'`). No `standard` breakdown exists
  for i-Ready. Default to `overall` unless a domain breakdown is explicitly
  requested.
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
- **`Outside Round` is also the least complete round.** Roughly a third of
  `Outside Round` sittings never resolve to a section enrollment, so they never
  reach this view (Newark loses ~40%); the named rounds lose under 10%. Treat
  `Outside Round` counts as a floor, not a census.
- **Resolving "the most recent diagnostic":** take the latest _named_ round
  (`BOY` / `MOY` / `EOY`) within the latest `academic_year_label` — do **not**
  take the maximum `date_taken`. The literal latest rows are usually one-off
  `Outside Round` makeup sittings, and a July test date lands in the _next_
  July-start academic year, so a max-date pick returns a single student rather
  than the administration.
- **Proficiency cutoff:** `is_mastery` is TRUE for `Early On Grade Level` and
  `Mid or Above Grade Level`, FALSE for the three below-grade-level bands. Note
  that `Early On Grade Level` counts as proficient — a looser bar than "at or
  above grade level", and it is roughly half of all proficient scores. If a
  participant means the stricter definition, filter `proficiency_level` directly
  instead of using `pct_proficient`.
- **EOY is administered _after_ NJSLA, so it cannot be a leading indicator for
  the same year's state test.** Median math test dates in 2024-25: BOY
  2024-09-04, MOY 2025-01-15, **NJSLA Math 2025-05-14**, EOY 2025-06-04. MOY is
  the last named round that precedes the state test. Any "does i-Ready predict
  NJSLA" framing must therefore use MOY (or a prior-year EOY); an EOY-vs-NJSLA
  comparison within one year is concurrent-or-trailing, not predictive. Say
  which it is — the direction of the claim depends on it.
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
  student per window before computing anything student-level — **scope this
  dedup to `response_type = 'overall'` rows.** At the current grain, an i-Ready
  sitting also produces `group`-level domain rows alongside its `overall` row;
  deduping across all `response_type` values collapses a subject's `overall` row
  together with its domain rows into one, silently destroying the domain
  breakdown. **The rate varies enormously by slice**, so treat the dedup as
  standing practice rather than something to skip when it looks unnecessary:
  Camden grade 6 ELA runs 1.55% at BOY, **15.38% at MOY**, and 3.06% at EOY,
  while Newark grades 3-4 Math runs 0.08% / 0.57% / 0.75% across the same
  rounds. Most windows sit under 2%; one measured window hit one student in six.
  It is genuine repeat testing, not a section-join fan-out. Skipping the dedup
  inflates any student-level count or growth figure. (Which sitting is
  _authoritative_ for reporting is an open decision; most-recent-by-date is the
  working convention, not ratified policy.)
- **Query this view, not the upstream i-Ready model.** i-Ready arrives with
  fiscal-year re-pull duplicates — the same physical test landing under two
  partitions. The mart collapses them, so counts here are right; a query
  straight against the warehouse source double-counts nearly every row.
- Documented from the live schema and four working-group sessions (a Camden ES
  ELA DIBELS-vs-i-Ready concordance, a BOY-to-EOY growth-quadrant analysis, and
  two Camden proficiency-by-grade pulls) — confirm interpretations before
  external use.

## Vendor normed diagnostics — DIBELS

- `assessment_type = 'dibels'`; `is_internal_assessment = false`. Subject
  (`category`): ELA.
- **Grade field: use `grade_level`. `grade_level_tested` is null on every DIBELS
  row.**
- **Tier-movement rates are not comparable to i-Ready's.** DIBELS has four
  benchmark tiers; i-Ready has five placement levels. Fewer, wider bins
  mechanically produce a higher "stayed the same" rate, so a DIBELS no-movement
  share will look worse than i-Ready's for the same students — one logged
  session saw 22% versus 10% in the same grade. Compare each instrument to
  itself over time, never to the other.
- **`response_type`:** `overall` is the summary row for every sitting; DIBELS
  now also populates `group` for subtest-level breakdowns (see Shared
  conventions — filter `response_type = 'group'`, break out by
  `response_type_description`, and pair with `assessment_type = 'dibels'`). No
  `standard` breakdown exists for DIBELS. Default to `overall` unless a subtest
  breakdown is explicitly requested.
- **Proficiency:** `proficiency_level` is the DIBELS benchmark tier —
  `Well Below Benchmark`, `Below Benchmark`, `At Benchmark`, `Above Benchmark`.
  `is_mastery` is populated. `performance_band_label_number` is null.
- **Time:** `academic_year` / `academic_year_label` now resolve — filter the
  school year with them.
- **Administrations:** `administration_period` = `BOY` / `MOY` / `EOY`, the same
  benchmark-window vocabulary as i-Ready.
- **Coverage starts in 2023-24**, and that first year is partial (about a third
  of a normal year's volume, consistent with mid-year adoption). Earlier years
  are simply absent — do not read a pre-2023-24 gap as a load failure, and don't
  trend across the 2023-24 boundary.
- Documented from the live schema and one working-group session (used as the
  comparison instrument in a Camden ES ELA concordance) — confirm before
  external use.

## Vendor normed diagnostics — STAR

- `assessment_type = 'star'`; `is_internal_assessment = false`. Subjects
  (`category`): ELA and Math.
- **Grade field: use `grade_level`. `grade_level_tested` is null on every STAR
  row.**
- `response_type = 'overall'` (overall only — no group or standard breakdown for
  STAR).
- **Proficiency:** `proficiency_level` is `Level 1`–`Level 5` (a share of rows
  have null `proficiency_level` / `is_mastery`). `performance_band_label_number`
  is null.
- **Time:** `academic_year` / `academic_year_label` now resolve — filter the
  school year with them.
- **Administrations:** `administration_period` = `Fall` / `Winter` / `Spring` —
  season names, **not** the `BOY` / `MOY` / `EOY` vocabulary i-Ready and DIBELS
  use. Do not carry a benchmark-window filter across from those sources.
- **Coverage starts in 2023-24** at a steady but small volume (~2.3-2.5k scores
  per year, far below the other sources). Earlier years are absent, not lost.
- Not exercised in the working-group sessions; documented from the live schema —
  confirm before external use.

## NJ state assessments

- `assessment_type` values: `state_nj_njsla` (NJSLA ELA/Math),
  `state_nj_njsla_science` (NJSLA Science), `state_nj_njgpa` (NJGPA). `category`
  carries the subject (ELA / Math / Science).
- `response_type = 'overall'` (overall only — no group or standard breakdown for
  state).
- **Proficiency:** `proficiency_level` is the state achievement level;
  `is_mastery` is the proficient flag. `performance_band_label_number` is null.
- **Time:** `academic_year` / `academic_year_label` now resolve for state
  (derived from the test date) — filter the school year with them.
  `administration_period` is the testing season (Fall / Winter / Spring).
- **Spring 2026 onward, NJSLA and NJGPA are computer-adaptive — and this view
  cannot tell you which form a score came from.** NJDOE, with Cambium, launched
  NJSLA-Adaptive (ELA/Math) and NJGPA-Adaptive; announced August 2025, first
  operational windows spring 2026 (NJGPA-A March 16-20 2026; NJSLA-A April 27 to
  May 22 2026). NJSLA-Science is not part of the transition. `assessment_type`
  carries one value per state test and each resolves to a single `title`, so
  **no field distinguishes adaptive from fixed-form**. Any NJSLA or NJGPA
  comparison that crosses the spring 2026 boundary may therefore be comparing
  two different scales. Flag that every time, and never present a cross-year NJ
  state trend spanning the boundary as settled. Whether NJDOE reset
  achievement-level cut-scores for the adaptive forms is an open question for
  instructional leadership — it is not answerable from this view.
- **A Fall NJGPA slice is the routine retake window, not adaptive field-test
  data.** Small Fall administrations appear every year alongside the main Spring
  one (193 scores in October 2024; 137 in October 2025). The prior-year
  precedent settles it — do not read a Fall slice as an anomaly, and do not
  attribute it to the adaptive rollout.
- **A missing current-year NJSLA is a release lag, not a defect.** State results
  land well after the testing window closes; as of this writing 2025-26 NJSLA
  and NJSLA-Science carried no rows in any NJ region while 2025-26 NJGPA did.
  Absence here means "not yet released," so do not log it as a data-quality
  defect or build a workaround around it — and do not describe estimating those
  values as forecasting a future event, because the test itself has already been
  given.
- **Student identifier:** for NJ, `lea_student_identifier` (KIPP's SIS number)
  is the canonical student number; `district_student_identifier` is null for NJ
  (host-district IDs are Miami-only). `state_student_identifier` is the
  state-assigned number.

## FL state assessments

- `assessment_type` values: `state_fl_fast` (FAST ELA/Math), `state_fl_science`
  (Science), `state_fl_eoc` (end-of-course, e.g. Civics). `category` carries the
  subject.
- `response_type = 'overall'` (overall only — no group or standard breakdown for
  FL state).
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
