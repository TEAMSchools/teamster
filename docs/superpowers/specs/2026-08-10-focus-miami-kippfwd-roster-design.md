# Design: source `rpt_gsheets__kippfwd_miami_roster` from Focus

- **Issue:** [#4782](https://github.com/TEAMSchools/teamster/issues/4782)
- **Upstream defect:**
  [#4794](https://github.com/TEAMSchools/teamster/issues/4794)
- **Date:** 2026-08-10
- **Model:**
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`

No new models. This is a rewrite of one reporting view over kipptaf's existing
Focus layer.

## Problem

`rpt_gsheets__kippfwd_miami_roster` sources every student column from
`base_powerschool__student_enrollments`, reached through
`int_extracts__student_enrollments`, plus a direct join to
`int_powerschool__gpa_term`. The FAST columns already come from FLDOE.

Miami PowerSchool holds no data past `academic_year = 2025`. Focus already holds
`academic_year = 2026` — 194 students in grade 7 and 179 in grade 8. At the July
`current_academic_year` rollover to 2026, the extract's
`academic_year >= current_academic_year - 1` filter selects 2025 and 2026, and
the 2026 half is empty.

## Approach

kipptaf already exposes a complete Focus layer, built by the `focus` package
inside `kippmiami` and read through `sources-kippmiami.yml` (source
`kippmiami_focus`). Three of those models cover nearly the whole extract:

| Model                            | Grain                          | Supplies                                                                       |
| -------------------------------- | ------------------------------ | ------------------------------------------------------------------------------ |
| `int_focus__student_enrollments` | one row per enrollment span    | `academic_year`, `student_name`, `grade_level`, `fteid`, `rn_year`, `exitcode` |
| `int_focus__students`            | one row per student            | `powerschool_id`, `disis_id`, `sex_label`, `ese_fefp_code`                     |
| `int_focus__student_contacts`    | one row per (student, contact) | `contact_name`, `email`, `phone_home`, `phone_mobile`, `sort_order`            |

So the work is a rewrite of the reporting view. No new sources, no new
intermediates, no change to the `focus` package.

### Two naming traps

`int_focus__student_enrollments.student_number` is the **Focus** `student_id`,
not the PowerSchool `student_number`. It is the join key to
`int_focus__students.student_id` and `int_focus__student_contacts.student_id`.
The roster's `ps_id` must come from `int_focus__students.powerschool_id`.

`int_focus__student_contacts.sort_order` is NUMERIC, not a STRING — filter with
`sort_order = 1` / `sort_order = 2`, unquoted. BigQuery has no
`NUMERIC = STRING` signature, so a quoted literal fails the build.

## Column mapping

Match rates and coverage below were measured for Miami grades 7 and 8.

| Roster column              | Source                                                                   |
| -------------------------- | ------------------------------------------------------------------------ |
| `academic_year`            | `int_focus__student_enrollments.academic_year`                           |
| `lastfirst`                | `int_focus__student_enrollments.student_name` — already last-comma-first |
| `grade_level`              | `int_focus__student_enrollments.grade_level` — already INT64             |
| `fleid`                    | `int_focus__student_enrollments.fteid`                                   |
| `ps_id`                    | `int_focus__students.powerschool_id`                                     |
| `mdcps_id`                 | `int_focus__students.disis_id`, zero-padded to width 7                   |
| `gender`                   | `regexp_extract(int_focus__students.sex_label, r'\[(\w)\]')`             |
| `iep_status`               | `int_focus__students.ese_fefp_code` — see recall caveat                  |
| `contact_1_*` (4 columns)  | `int_focus__student_contacts` at `sort_order = 1`                        |
| `contact_2_*` (4 columns)  | `int_focus__student_contacts` at `sort_order = 2`                        |
| 6 FAST columns             | `stg_fldoe__fast` on `fteid` and `academic_year`, unchanged shape        |
| `previous_year_ada`        | `int_extracts__student_enrollments.ada_unweighted_year_prev`             |
| `enroll_status`            | Derived locally, see below                                               |
| `advisor_lastfirst`        | `cast(null as string)`                                                   |
| `gpa_cumulative`, `gpa_y1` | `cast(null as float64)`                                                  |

`sex_label` holds `Male[M]` and `Female[F]`, so the bracketed code extracts
directly to PowerSchool's `M` / `F` domain.

### Contacts

`int_focus__student_contacts` already resolves typed phone columns, so no
Finalsite join and no phone-type mapping is needed. Coverage for AY2026 grades 7
and 8:

| `sort_order` | Students | Name | Email | Mobile | Home |
| ------------ | -------- | ---- | ----- | ------ | ---- |
| `'1'`        | 338      | 338  | 328   | 279    | 55   |
| `'2'`        | 283      | 283  | 200   | 210    | 73   |

`phone_home` is sparse because Focus mostly stores a mobile number. That is a
property of the source data, not of this model.

### Retained from PowerSchool

`previous_year_ada` continues to come from `int_extracts__student_enrollments`,
joined on `powerschool_id = student_number`, `academic_year`, `region = 'Miami'`
and `rn_year = 1`. Reusing that model preserves the existing
weighted-vs-unweighted SY2025 rule rather than reimplementing it.

Focus cannot supply attendance: `attendance_completed` holds 1 row (confirmed by
`count(*)`, not the lagging `__TABLES__.row_count`), and `fl_days_present` /
`fl_days_absent` on `student_enrollment` are entirely null.

### Cast null

| Column                     | Reason                                                                                                                                                                                                         | Tracked |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `advisor_lastfirst`        | Focus has no advisory structure for grades 7-8. Homeroom courses exist only for K-5, `student_enrollment.team_id` is null for all 365 students in both years, and no grade 7-8 course functions as an advisory | #4795   |
| `gpa_cumulative`, `gpa_y1` | Miami middle school will no longer produce a GPA at all. These columns have no future source and need a replacement academic-standing metric chosen by KIPP Forward, not a rebuild against Focus               | #4796   |

The GPA columns are a **permanent** gap, not a modeling backlog item. They stay
in the contract as typed nulls so the sheet's column layout does not shift while
the replacement metric is decided.

Each gets an inline `-- TODO(#4795)` or `-- TODO(#4796)` comment at the
derivation site, per `src/dbt/CLAUDE.md` — not a note in the yml `description`.

## `enroll_status` derivation

**The upstream column is wrong for any closed school year and must not be
used.** `int_focus__student_enrollment` in the `focus` package derives it from
drop-code presence, and Focus stamps a rollover withdrawal code (`W01` In School
Transfer, `W02` In District Transfer) on nearly every span at year end:

| Year   | Upstream `enroll_status`  | PowerSchool actual |
| ------ | ------------------------- | ------------------ |
| AY2025 | 0 = 2, 2 = **361**, 3 = 2 | 0 = 222, 2 = 143   |
| AY2026 | 0 = 353, 2 = 22           | no data            |

AY2026 reads correctly only because the year has not closed yet. Filed as
[#4794](https://github.com/TEAMSchools/teamster/issues/4794); this extract
derives the value locally until that lands.

Local derivation, reading `exitcode` (which is null exactly when the underlying
`drop_code` is null):

| Output | Condition                                                                          |
| ------ | ---------------------------------------------------------------------------------- |
| `-1`   | `startdate` is in the future                                                       |
| `3`    | upstream `enroll_status = 3` — that branch keys on `grad_type` and is correct      |
| `0`    | the student has an enrollment in the latest `academic_year` with a null `exitcode` |
| `2`    | otherwise                                                                          |

Anchor directly on `var("current_academic_year")`, which is 2026 (rolled
2026-07-17 in `7cfd878bf`) and is already trusted by this model's own row
filter. An earlier draft of this design anchored on `max(academic_year)` present
in Focus instead, on the mistaken belief that the var lags the July rollover —
it does not. That anchor was also fragile in its own right: AY2018 through
AY2024 have zero null `exitcode`s, so a single stray future-dated row would flip
`max(academic_year)` and mark nearly every student withdrawn, and the same
all-withdrawn failure would recur every year once the current academic year
closes. Anchoring on the var avoids both problems. This reproduces PowerSchool
`enroll_status` for 341 of 365 students; the 24 disagreements are explainable,
since PowerSchool froze at the Focus cutover.

When #4794 lands, delete the local CTEs and read the upstream column.

## `iep_status` recall

Focus ESE FEFP Code identifies 42 of the 53 IEP students PowerSchool flags via
`spedlep like 'SPED%'` for SY2025 grades 7 and 8 — 79% recall, with 1 student
found by Focus but not PowerSchool. The `ESE Exceptionalities` log field in
`custom_field_log_entries` adds zero additional students.

Accepted as-is. The gap is documented in the column `description` so a consumer
reading `No IEP` knows it is not authoritative. No dbt test guards the recall.

## Grain

One row per student per `academic_year`, enforced by the upstream `rn_year = 1`
filter — the same mechanism the current model uses. No `dbt_utils.deduplicate`
is needed; `int_focus__student_enrollments` already computes `rn_year`
partitioned by (`student_number`, `academic_year`).

`int_focus__student_contacts` is one row per (student, contact), so each
`sort_order` filter must be its own CTE joined once, or the roster fans out.

## Filters

`region = 'Miami'` and the `union_dataset_join_clause` plumbing disappear —
`kippmiami_focus` is a single-region source. `grade_level in (7, 8)` and
`academic_year >= current_academic_year - 1` carry over unchanged, as does
`rn_year = 1`.

## Known limitations

- **`ps_id` is null for roughly 80 students** across both years — new enrollees
  with no `powerschool_id` assigned yet. They also receive no
  `previous_year_ada`, which is correct because they were not previously
  enrolled.
- **`previous_year_ada` empties at the SY2027 rollover, not SY2026.** For SY2026
  rows the prior year is SY2025, which PowerSchool holds. It was null for all
  AY2026 rows in the first cut of this model, keyed to read the current year's
  own PowerSchool row instead of the prior year's; corrected to read the prior
  year's `unweighted_ada` directly, it is now populated for roughly 295 of 375
  AY2026 rows, limited by `powerschool_id` coverage.
- **`fleid` is null for 81 of 375 AY2026 rows (22%)**, versus 5 of 365 in
  AY2025. It is the only grain-test key and both FAST join keys, so the grain
  test covers 78% of current-year rows and those 81 students get no FAST scores.
  `mdcps_id` is null for exactly the same 81 students and `ps_id` for 80 of
  them, so those rows carry no usable identifier except `lastfirst`. Not
  recoverable by coalescing across years — none of the 81 has a prior-year Focus
  row with a non-null `fteid`.
- **`enroll_status` reads `-1` for the whole current year until the first day of
  school (2026-08-12 for AY2026, per `int_focus__school_year_first_day`), then
  clears**, by deliberate choice — see the `enroll_status` derivation above.
- **`contact_1_phone_home` is sparse** — 55 of 338 primary contacts. Expected.

## Testing

The roster contract exposes no column that is both unique and non-null, so the
uniqueness test is scoped:

- `dbt_utils.unique_combination_of_columns` on (`academic_year`, `fleid`) with
  `config.where: fleid is not null`.

Manual verification before opening the PR:

- Row-count parity against the current model for `academic_year = 2025`, grades
  7 and 8.
- `enroll_status` for AY2025 must land near the PowerSchool split (222 at `0`,
  143 at `2`), not the upstream model's 361-at-`2`. This is the regression that
  matters most.
- AY2026 rows exist at roughly 194 in grade 7 and 179 in grade 8.
- Contact coverage matches the table above.

## Corrections to the first draft of this design

Recorded so the reasoning is auditable:

- The first draft proposed reading the raw `dagster_kippmiami_dlt_focus` dlt
  landing tables directly at the kipptaf level and building two new
  intermediates. That analysis was performed against a stale checkout and missed
  kipptaf's entire existing Focus layer. Commit `4bad76cad` on `main` had
  already closed that pattern after review, on the grounds that Focus staging
  belongs in the district via the `focus` package.
- The first draft reported Focus contacts as unavailable and routed the eight
  contact columns through Finalsite. That came from reading
  `__TABLES__.row_count`, which lags; `count(*)` shows `people` at 3,622 and
  `students_join_people` at 3,576. Focus contacts are fully populated and
  already typed by phone kind.
- The ADA and GPA gaps were re-confirmed with `count(*)` and are real.

## Out of scope

- Fixing `enroll_status` upstream — tracked in #4794, needs the district-then-
  kipptaf two-PR sequence.
- Focus attendance ingestion and a `focus` package GPA model.
- The other Miami extracts reading `int_extracts__student_enrollments`. They
  face the same cliff, but each needs its own column analysis.
