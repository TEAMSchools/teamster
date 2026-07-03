# Promotional Status Policy Engine — Design

Issue: [#4324](https://github.com/TEAMSchools/teamster/issues/4324)

## Problem

`int_reporting__promotional_status` hardcodes every region-by-grade promotion
policy in ~600 lines of CASE statements. Changing a cutoff (or restructuring a
policy) requires a PR each year. Regional leaders own these policies and should
be able to change both **thresholds** and **combination logic** without code
changes, including complex rules such as: retained if fails 2+ core classes OR
(ADA below 85% AND 3+ grade levels below in ELA).

A prior lookup-table attempt
(`stg_google_sheets__reporting__promo_status_cutoffs`, now `enabled: false`)
stored one cutoff per row but had no way to express AND/OR structure, and
stalled.

## Goals

- Policies and cutoffs live in a Google Sheet that regional leaders populate.
- The sheet can express arbitrary boolean combinations of conditions.
- The metric vocabulary stays fixed in code; adding a new metric is a one-place
  code change.
- Output contract of `int_reporting__promotional_status` is preserved (same
  columns, same grain) so `rpt_tableau__promo_status` and
  `rpt_deanslist__promo_status` only change `ref()`s.
- New models live under `models/students/` (`int_students__*`), retiring the
  `reporting` placement.

## Non-goals

- Historical backfill. The sheet is seeded with current-year policies only;
  backfilling the previous 2 academic years is a follow-up (tracked in #4324).
- Making SPED exemptions or PowerSchool log overrides sheet-driven — those stay
  in code.
- Letting leaders define new metrics without a code change.

## Design overview

Encode policies in **disjunctive normal form** (OR-of-ANDs). One sheet row = one
condition. Conditions sharing a `rule_group` AND together; rule groups OR
together. A domain is Off-Track when any matching rule group is fully satisfied;
otherwise On-Track.

The example policy becomes:

| domain   | rule_group | metric                        | comparator              | value | if_missing |
| -------- | ---------- | ----------------------------- | ----------------------- | ----- | ---------- |
| academic | 1          | `n_failing_core`              | `greater_than_or_equal` | 2     | not_met    |
| academic | 2          | `ada_term_running`            | `less_than`             | 0.85  | met        |
| academic | 2          | `iready_reading_levels_below` | `greater_than_or_equal` | 3     | met        |

Any boolean expression has a DNF equivalent, so no future policy shape outgrows
the schema.

## Component 1: Policy sheet + source + staging model

### Sheet

A new tab on the existing promo-status spreadsheet
(`1bRd3cI3WlTdizm5ja7IxGxGjJDzXrOX6i2G731h9yr8`), exposed as source
`src_google_sheets__reporting__promo_status_policies`. The disabled
`promo_status_cutoffs` source entry and staging model are deleted.

Columns (one row per condition):

| Column          | Type    | Notes                                                                                                     |
| --------------- | ------- | --------------------------------------------------------------------------------------------------------- |
| `academic_year` | int64   | Starting year of the school year (2025 = SY25-26)                                                         |
| `region`        | string  | `Camden` / `Newark` / `Miami` (Paterson adds rows later, no code change)                                  |
| `grade_min`     | int64   | K = 0                                                                                                     |
| `grade_max`     | int64   | Single grade = same value as `grade_min`                                                                  |
| `term_name`     | string  | `Q1`–`Q4` or `All`. Term-scaled thresholds (Newark HS absences Q1=6 … Q4=24) are one row per term         |
| `domain`        | string  | `attendance` / `academic` / `overall`                                                                     |
| `rule_group`    | int64   | Conditions in the same group AND together; groups OR together                                             |
| `metric`        | string  | From the fixed catalog (Component 2)                                                                      |
| `comparator`    | string  | One of `less_than`, `less_than_or_equal`, `greater_than`, `greater_than_or_equal`, `equals`, `not_equals` |
| `value`         | float64 | The cutoff                                                                                                |
| `if_missing`    | string  | `met` / `not_met` — what the condition evaluates to when the student's metric is NULL                     |
| `detail_label`  | string  | Optional. Emitted as `attendance_status_hs_detail` when an attendance-domain group fires                  |

The sheet uses data-validation dropdowns on `region`, `term_name`, `domain`,
`metric`, `comparator`, and `if_missing`.

### Scope-matching semantics

A student-term row matches every policy row where all of the following hold:

- `academic_year` equals the student's academic year
- `region` equals the student's region
- `grade_level between grade_min and grade_max`
- `term_name` equals the reporting term name, or is `All`

Overlapping scopes are legal and simply contribute additional OR branches — e.g.
NJ grades 5–8 carry both the grades 3–8 rules and an extra `n_failing_core` rule
scoped 5–8.

If a rule group's scope matches but some of its conditions reference metrics the
student lacks, `if_missing` decides each condition. If **no** policy rows match
a student-term-domain at all, the domain status is **NULL** (not On-Track) —
absence of policy is not evidence of being on track. A warn-level coverage test
surfaces these gaps.

### Staging model

`stg_google_sheets__reporting__promo_status_policies`: contract enforced
(directory default), phantom-null-row filter on `academic_year`, snake_case
aliasing of sheet headers.

## Component 2: Metric catalog

Defined once as a dbt macro returning the list of metric column names, reused by
the unpivot step and the staging `accepted_values` test. All metrics are numeric
so every condition is uniformly `metric comparator value`.

| Metric                                    | Source                                  | Notes                                      |
| ----------------------------------------- | --------------------------------------- | ------------------------------------------ |
| `ada_term_running`                        | `int_powerschool__ps_adaadm_daily_ctod` | Running ADA through term end               |
| `n_absences_y1_running`                   | same                                    | YTD absences incl. suspensions             |
| `n_absences_y1_running_non_susp`          | same                                    | Excl. suspensions, + floor(tardies/3)      |
| `n_absences_y1_running_non_susp_no_tardy` | same                                    | Excl. suspensions, no tardy penalty        |
| `iready_reading_levels_below`             | `int_iready__diagnostic_results`        | Placement string mapped to int (see below) |
| `iready_math_levels_below`                | same                                    | same mapping                               |
| `dibels_composite_level`                  | `int_amplify__all_assessments`          | Most recent benchmark composite, int       |
| `star_ela_level`                          | `stg_renlearn__star`                    | Most recent achievement level              |
| `star_math_level`                         | `stg_renlearn__star`                    | same                                       |
| `fast_ela_level`                          | `stg_fldoe__fast`                       | Most recent achievement level (FL)         |
| `fast_math_level`                         | `stg_fldoe__fast`                       | same                                       |
| `n_failing`                               | `int_powerschool__final_grades_rollup`  | Failing course count, term                 |
| `n_failing_core`                          | same                                    | Failing core course count, term            |
| `projected_credits_y1_term`               | same                                    | HS                                         |
| `projected_credits_cum`                   | + `int_powerschool__gpa_cumulative`     | HS                                         |
| `is_off_track_attendance`                 | pseudo — computed domain result         | 0/1; valid in `overall` domain only        |
| `is_off_track_academic`                   | pseudo — computed domain result         | 0/1; valid in `overall` domain only        |

iReady placement mapping: `3 or More Grade Levels Below` → 3,
`2 Grade Levels Below` → 2, `1 Grade Level Below` → 1, all on/above-grade
placements → 0, no result → NULL (handled by `if_missing`). This integer version
is already present on the i-ready diagnostic results view

Raw display columns (`iready_reading_recent` placement string,
`dibels_composite_level_recent_str`, etc.) still pass through to the output
unchanged.

## Component 3: Model architecture

### `int_students__promotional_status_metrics` (new)

The metric layer, extracted from the current model's CTEs: active enrollments
(`rn_year = 1`) joined to RT terms, attendance rollup, credits, iReady, mClass,
STAR, FAST, plus the string→int mappings. Also carries the kept-in-code layers'
inputs: SPED exemption flags and PowerSchool log overrides.

- Grain: one row per `student_number` × `academic_year` × `term_name`;
  uniqueness-tested (the legacy model lacked this test — the rebuild adds it).
- Computed for **all** academic years, exactly as today.

### `int_students__promotional_status` (new; replaces `int_reporting__promotional_status`)

The evaluation engine:

1. **Unpivot** metric columns to long form (`metric`, `metric_value`) via the
   catalog macro.
2. **Join** policy rows on the scope-matching rules above.
3. **Evaluate** each condition: apply `comparator` to (`metric_value`, `value`);
   when `metric_value` is NULL, the condition is met iff `if_missing = 'met'`.
4. **Aggregate pass 1** (`attendance`, `academic` domains): a rule group fires
   when `countif(met) = count(*)`; a domain is `Off-Track` when any group fires,
   `On-Track` when matching rows exist but no group fires, NULL when no rows
   match. `attendance_status_hs_detail` takes the `detail_label` of the
   lowest-numbered fired attendance group, falling back to `attendance_status`.
5. **Aggregate pass 2** (`overall` domain): same evaluation with two extra
   unpivoted rows per student-term: `is_off_track_attendance` and
   `is_off_track_academic` (1 when the pass-1 domain is `Off-Track`, 0 when
   `On-Track`, NULL when NULL).
6. **Kept-in-code layers** (logic unchanged from today): `exemption` (SPED
   self-contained / state-assessment rules + `Exempt from retention` log
   entries) and `manual_retention` (`Retain without criteria` log entries).
7. Emit the existing output contract: identity/term columns, all raw metric and
   display columns, `attendance_status`, `attendance_status_hs_detail`,
   `academic_status`, `overall_status`, `exemption`, `manual_retention`.

Behavior change (accepted): years/scopes with no policy rows emit NULL statuses
instead of fabricated `On-Track`. `rpt_tableau__promo_status` filters to
`var("current_academic_year")`, so the dashboard is unaffected; prior years read
NULL until the backfill follow-up.

### Downstream

`rpt_tableau__promo_status` and `rpt_deanslist__promo_status` update
`ref("int_reporting__promotional_status")` →
`ref("int_students__promotional_status")`. No other changes. The old model SQL
and properties yml under `models/reporting/intermediate/` are deleted.

## Testing and validation

Staging tests (all `severity: error`):

- `accepted_values` on `region`, `domain`, `comparator`, `if_missing`, and
  `metric` (values from the catalog macro)
- `not_null` on every column except `detail_label`
- `dbt_utils.unique_combination_of_columns` on the condition grain
  (`academic_year`, `region`, `grade_min`, `grade_max`, `term_name`, `domain`,
  `rule_group`, `metric`, `comparator`)
- `expression_is_true`: `grade_min <= grade_max`
- `expression_is_true`: pseudo-metrics only in the `overall` domain

Warn-level tests:

- **Coverage** (singular test): enrolled `region` × `grade_level` × current-year
  combinations with zero matching policy rows for any of the three domains
- **Label consistency** (singular test): `detail_label` identical across all
  rows of a rule group

Model tests:

- Uniqueness on both new intermediates (`student_number`, `academic_year`,
  `term_name`)
- dbt unit tests on the evaluation engine: OR-of-ANDs firing, `if_missing` both
  ways, term scoping, overlapping scopes, NULL-when-no-policy, pseudo-metric
  overall pass

Rollout validation (one-time): build the new model alongside the old logic and
diff current-year statuses student-by-student. Every mismatch is either a sheet
transcription error or a latent bug in the legacy CASE logic (at least one
suspected: Camden HS `hs_off_track_absences` branch is unreachable in
`attendance_status` because the `hs_at_risk_absences` branch precedes it and
both map to the same label). Resolve every diff deliberately before the swap.

## Rollout

1. Data team seeds the new sheet tab with current-year policies transcribed from
   the CASE logic; adds dropdown validations. Leaders own it afterward.
2. Add source + staging model; stage the external with `--target staging` before
   dbt Cloud CI can pass (new-external convention).
3. Build both new models; run the diff validation; resolve discrepancies.
4. Swap: point the `rpt_*` models at `int_students__promotional_status`, delete
   the legacy model + yml and the disabled `promo_status_cutoffs` source/staging
   pair.
5. Follow-up (separate issue per #4324): backfill previous 2 years of policies
   into the sheet.

## Risks

- **Sheet as production input**: a bad edit changes statuses silently. The
  error-severity staging tests catch structural mistakes (typos, dupes, invalid
  enums); the warn-level coverage test catches missing scopes; but a
  wrong-but-valid threshold is leaders' responsibility by design.
- **Fan-out**: the unpivot × policy join is bounded (≈17 metrics × matching
  conditions per student-term) — well within BigQuery comfort for ~10k students
  × 4 terms.
- **Shared-spreadsheet trigger**: all tabs on the spreadsheet URI trigger
  together on any tab change (repo-known Sheets behavior). The promo sheet
  already behaves this way; no new exposure.
