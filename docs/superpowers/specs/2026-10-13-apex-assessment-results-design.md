# Apex assessment results in the shared assessment pipeline

Issue: [#5830](https://github.com/TEAMSchools/teamster/issues/5830). Decisions
comment:
[#5830 (comment)](https://github.com/TEAMSchools/teamster/issues/5830#issuecomment-6151737735).
Staging this builds on: #5828 and
`docs/superpowers/specs/2026-10-09-focus-apex-sync-design.md`.

## Why

Miami left Illuminate this year and gives its interim assessments in Apex, the
assessment module inside Focus. Miami has 0 Illuminate rows for 2026-27, so
every surface that shows Illuminate results shows nothing for Miami this year.
Apex has no report by section, grade, or school.

The goal is parity. Miami staff use Apex results exactly the way NJ staff use
Illuminate results: the same dashboards, filters, and metrics, on the same
definitions. Nobody learns a Miami-only screen.

The user wants this as soon as possible.

## Goals

1. Apex results flow into `int_assessments__response_rollup` and through it to
   every live consumer, so Miami 2026-27 results appear wherever Illuminate
   results do.
2. Taggers tag Apex assessments in the existing AppSheet assessment app, next to
   Illuminate assessments.
3. A data tab in the 2026-27 KIPP Miami Data Tracker shows percent at mastery by
   school, grade, subject, and assessment.

## Non-goals

- A separate Tableau rollup for Apex. #5830 proposed one; the existing
  dashboards cover it once Apex is in the shared pipeline.
- `rpt_tableau__power_standards` and `rpt_tableau__qbl`. Both are disabled.
- `rpt_tableau__miami_fast`. It reads only frozen 2023 Illuminate rows, and its
  Dagster refresh schedule is stopped. Leave it alone.
- Fixing #5392. It is effectively fixed by #5760 (see _Canonical grouping_).
- Parsing module type or number from Apex titles. The user rejected this.

## Anti-goals

- Any change to NJ numbers. Every NJ row in every consumer is identical before
  and after.
- A Miami Apex assessment merging with an NJ assessment in canonical grouping,
  or an Apex id matching an Illuminate id anywhere.
- A guessed mastery cutoff. An Apex assessment without a band set has no mastery
  value.

## Settled rules

From the decisions comment on #5830. Miami confirmation is tracked in 2 Asana
subtasks under the #5830 task; build on these values now.

- **Mastery:** Level 3 and above in the band set attached to the assessment in
  Apex (`stg_focus__apex_band_set_assessments` → `stg_focus__apex_band_levels`).
  Band levels carry only a label and a score range, so mastery is decided by
  label (`Level 3`, `Level 4`, `Level 5`). On the 8-level 6–12 FAST set, `Low 1`
  through `High 2` are below mastery.
- **Standards use the assessment's band set.** Illuminate gives each standard
  its own band set; Apex has 1 per assessment. Per-standard rows take the band,
  label, and mastery from the assessment's band set applied to the standard's
  percent correct (user decision).
- **Band numbers (my call):** `performance_band_label_number` runs 1 to N in
  `min_score` order within the band set, so the 8-level 6–12 FAST set numbers
  1–8. Today's 4 sets carry 10 distinct labels, all `Level N` or
  `Low/Mid/High N`. A label outside those patterns gets null mastery, as for no
  band set.
- **Ignore `stg_focus__apex_sessions.passed`.** It disagrees with the bands.
- **No band set:** null band, null band label, null mastery. 23 assessments have
  no band set today. Apex marks band set 3 as `is_default`, but do not apply it.
- **Denominator:** students who tested, as in NJ. Untested students may appear
  with null mastery (the NJ scaffold already does this); they never count as not
  mastered.
- **Retakes:** Apex retakes are not in use (`max_attempts = 1` everywhere,
  `attempt_id` always null). 1.5% of student × assessment pairs still have 2 or
  more completed sessions, mostly duplicate assignments. The latest
  `completed_at` among completed, non-discarded, non-excused sessions wins.
- **Overall score:** the session's own `score_actual` / `score_max`, not the sum
  of responses. About 6% of sessions disagree with their response sum (pending
  rescores, imported scores, max-point edits).
- **Standard scores:** scored responses (`score_actual is not null`) summed by
  standard. A response tagged to 2 standards counts once for each.
- **Percent correct:** `points_earned / points_possible`, on the same scale as
  `int_assessments__response_rollup.percent_correct` (0–100).

## Identity

### Source column

Every assessment-grain and student-assessment-grain row in the pipeline carries
`source` (`illuminate` or `apex`). The key for an assessment is source plus the
source system's own `assessment_id`. 12 Apex assessment ids already equal
Illuminate assessment ids, so `assessment_id` alone is never a key once Apex
rows exist.

Every join and grain test on `assessment_id` in the assessment models and their
consumers adds `source`. The marts fact
`fct_assessment_scores_enrollment_scoped` hard-codes the literal `'illuminate'`
into its administration key hash; that becomes the row's `source`. Illuminate
rows must hash to the same value they do today, so NJ surrogate keys do not
move.

### Years

Apex data starts in 2026-27: all 11,111 sessions and every dated assessment
carry Focus `syear = 2026`. The Apex branch still filters to academic year 2026
and later (my call), so a stray older Apex record can never double Miami rows
for years Illuminate covers.

### Students

Focus `student_id` equals `student_number` for every Apex student (1,493 of
1,493 matched against Miami 2026-27 enrollments). Apex rows fill
`powerschool_student_number` with it. `illuminate_student_id` is null for Apex
rows; any grain or join that uses it needs a source-aware substitute (for
example `powerschool_student_number` for Apex).

### Canonical grouping

#5760 added `is_florida_assessment` to the canonical grouping key in
`int_assessments__assessments_members`, so Florida and NJ assessments no longer
merge. That flag comes from the AppSheet `regions_assessed` tag being exactly
`Miami`. An untagged Apex assessment would not be flagged. So for Apex rows,
`is_florida_assessment` is true because `source = 'apex'`, regardless of tags.

Whether Apex rows go through canonical grouping at all, or enter as their own
canonical group, is the builder's call. Either is safe once the flag is forced.

## AppSheet

The app reads `rpt_appsheet__assessments` (a BigQuery view) and writes tags to
`kipptaf_appsheet.illuminate_assessments_extension` (a BigQuery table). Both are
keyed on the integer `assessment_id` today.

- `rpt_appsheet__assessments` lists Apex assessments alongside Illuminate ones
  and gains a `source` column. Apex rows fill what Apex knows (title, academic
  year, band set) and leave Illuminate-only fields null.
- `illuminate_assessments_extension` gains a `source` column, and existing rows
  get `illuminate`. Draft the `alter table` and `update` and hand them to the
  user; Claude does not run warehouse DDL.
- The user (or the app owner) changes the app's key and the reference between
  the 2 tables to source plus `assessment_id` in the AppSheet editor.
- `stg_google_appsheet__illuminate_assessments_extension` changes its uniqueness
  test to source plus `assessment_id`, and every join to it adds `source`:
  `int_assessments__assessments_members`, `rpt_deanslist__mod_assessment`,
  `rpt_deanslist__mod_standards_domains`, and
  `rpt_gsheets__deanslist_mod_audit`.
- Keep the table name `illuminate_assessments_extension` and its Dagster asset
  key.

Order: the table DDL and the app edit land before the view lists Apex rows, or
the app sees duplicate keys.

## What Apex supplies and what tags supply

| Column                                                                         | Apex rows get it from                                                                                                                     |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment_id`, `title`, `academic_year`                                      | Apex assessment                                                                                                                           |
| `administered_at`                                                              | AppSheet override when present; otherwise builder's call from Apex (assignment window or sessions)                                        |
| `date_taken`                                                                   | session `completed_at`                                                                                                                    |
| `percent_correct`, points                                                      | session (overall) or summed responses (standard)                                                                                          |
| band label, band number, `is_mastery`                                          | Apex band set, per _Settled rules_                                                                                                        |
| `response_type`                                                                | `overall` or `standard`. Apex has no reporting groups, so no `group` rows                                                                 |
| `response_type_code`, description                                              | `stg_focus__standards`                                                                                                                    |
| `subject_area`                                                                 | AppSheet subject when tagged; otherwise the subject of the assessment's standards (`stg_focus__standard_categories_1`). No title fallback |
| `module_type`, `module_code`, `scope`, report-card and progress-report regions | AppSheet tags only. Null until tagged                                                                                                     |
| `discipline`                                                                   | Focus course enrollment, not PowerSchool. See _Sections_                                                                                  |
| `region`, school                                                               | Focus enrollment; region is `Miami`                                                                                                       |
| `term_administered`, `term_taken`                                              | `stg_google_sheets__reporting__terms`, as for Illuminate                                                                                  |
| `is_internal_assessment`                                                       | builder's call; it gates the marts fact and the mod-standards extracts                                                                    |
| `is_replacement`                                                               | false                                                                                                                                     |

## Untagged data is provisional

The user chose to ship the pipeline before the AppSheet change, with no title
parsing. Until an Apex assessment is tagged, its module, scope, and region
fields are null, so it is absent from every surface that filters on them:
topline formative, school metrics, the assessment roster, the DDI module grid,
and the DeansList mods. The assessment dashboard still shows it if its subject
resolves.

The PR and the issue say plainly that Miami numbers are not valid until Apex
assessments are tagged. Tags take effect on the next build with no code change.

## Sections

Section comes from the student's Focus schedule on the date taken, limited to
core courses in the assessment's subject. A row carries a section only when
exactly 1 such section matches. Otherwise the section is null and a
`section_match_method` column says why (for example no match, multiple matches).

`discipline` comes from the same match.
`stg_google_sheets__assessments__course_subject_crosswalk` has Focus rows for
ELA and math only (#5750), so science and social studies Apex rows have null
discipline until #5750 extends it. That keeps them out of the ELA and math
surfaces, which is correct.

`int_students__course_enrollments` has a Focus branch but hard-codes
`rn_student_year_illuminate_subject_desc` to null, and `credit_type` is null for
every Miami row. The dashboards' PowerSchool section join
(`base_powerschool__course_enrollments` on `illuminate_subject_area`) will not
match Apex rows; they need the Focus match instead.

## Consumers

Live consumers of `int_assessments__response_rollup`, and what each needs. A
consumer not listed needs no change beyond the `source` join key.

| Consumer                                                   | Needed for Apex rows                                                                                                              |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_tableau__assessment_dashboard`                        | Focus section match in place of the PowerSchool join                                                                              |
| `rpt_tableau__ddi_dashboard`                               | `region = 'Miami'`; Focus section match                                                                                           |
| `int_topline__formative_assessment_weekly`                 | `module_type`, `discipline`; already has a Miami CRQ branch                                                                       |
| `rpt_gsheets__assessment_roster`                           | `module_type`, `discipline`                                                                                                       |
| `rpt_gsheets__school_metrics_extract`                      | `module_type`, `discipline`                                                                                                       |
| `fct_assessment_scores_enrollment_scoped` (and Cube)       | `source` in place of literal `'illuminate'`; members, canonical, and resolved-section rows for Apex, or its inner joins drop them |
| `rpt_deanslist__mod_*`, `rpt_gsheets__deanslist_mod_audit` | `source` on the AppSheet join; mod audit builds its Illuminate link only for Illuminate rows                                      |
| `int_assessments__college_assessment_practice`             | Nothing; driven by a sheet of Illuminate ids. Add `source` so an Apex id cannot match                                             |

Disabled consumers (`rpt_tableau__power_standards`, `rpt_tableau__qbl`) and
`rpt_tableau__miami_fast` are out of scope.

## Layers

Apex staging lives in the `focus` package and builds in `kippmiami`. Logic
within Apex (latest session, overall and per-standard scores, bands, mastery)
belongs in source `int_` models in the `focus` package. Cross-source logic
(Focus enrollments and sections, AppSheet tags, the union with Illuminate)
belongs in kipptaf. kipptaf reads district models through
`sources-kippmiami.yml` plus a union passthrough, per
`src/dbt/kipptaf/CLAUDE.md`. Model names, the exact split, and whether this
ships as 1 PR (cross-project staging) or 2 are the builder's call.

Student-level Apex models carry `contains_pii: true` on student number and
student-level score columns, per `.claude/rules/ferpa-pii.md`.

## Rollout

Priority set by the user:

1. **Pipeline.** Apex into the rollup and consumers. Ships first, with
   provisional untagged data.
2. **AppSheet.** Source column, key change, user-run DDL, app edit.
3. **Tracker tab.** A data tab in Google Sheet
   `1LPYJFgvi5Btkqf4Q2onmM7A90MykKcqFyzZLOcUr7mA` (tab and header notes are in
   #5821's fold-out): 1 row per school, grade, subject, and assessment, with
   percent at mastery, number tested, and number enrolled. It reads from the
   shared pipeline so its numbers match the dashboards. Aggregate only. New
   `rpt_gsheets__` model and a Google Sheets exposure. My calls:
   - It does not filter on AppSheet tags. It needs only subject (from standards)
     and assessment, so it works before tagging.
   - Grade is the student's enrolled grade.
   - Number enrolled is counted in the tracker's own model: students enrolled in
     a core course for the subject on the assessment's date. The shared pipeline
     does not need to carry untested Apex students.

Pieces 1 and 2 touch the same keys, so the builder may combine or reorder the
code as long as the AppSheet ordering rule holds.

## Verification

- **NJ unchanged:** for every changed model, NJ row counts and a key-plus-value
  fingerprint match prod. Illuminate surrogate keys in the marts do not move.
- **Known answer:** `Math - G3 - PET 1 - 2026 - 2027 FL` at KIPP Royalty Academy
  returns 60 of 130 tested students at Level 3 and above, with 156 enrolled in
  `MATH GRADE 3`.
- **Tracker:** the tab reproduces the grade 6–8 math cells Miami filled in by
  hand, or each difference has a written cause.
- **No collisions:** no consumer join matches an Apex row to an Illuminate row
  on `assessment_id`.
- **No guessed cutoffs:** every Apex row with a non-null `is_mastery` has a band
  set.

## Left to the builder

- Model names and the package/kipptaf split.
- Whether Apex enters canonical grouping or bypasses it.
- `administered_at` fallback for untagged Apex assessments.
- `is_internal_assessment` for Apex rows.
- How `rpt_appsheet__assessments` fills Illuminate-only fields for Apex rows.
- 1 PR or several, within the rollout order.

## Housekeeping

- Close #5392 against #5760, with the user's go-ahead.
