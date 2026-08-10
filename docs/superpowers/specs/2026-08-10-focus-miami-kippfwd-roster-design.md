# Design: source `rpt_gsheets__kippfwd_miami_roster` from Focus and Finalsite

- **Issue:** [#4782](https://github.com/TEAMSchools/teamster/issues/4782)
- **Date:** 2026-08-10
- **Models:**
  - `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`
  - `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql`
    (new)
  - `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql`
    (new)

The kipptaf spine is named `int_focus__student_roster`, not
`int_focus__student_enrollment` — the latter already exists in the `focus`
package. There is no dbt graph collision, since kipptaf does not import that
package, but two same-named models in one repo make `grep`, `dbt ls`, and
`dbt clone --select` ambiguous. The name also describes the grain: one row per
student per year, not one row per enrollment span.

## Problem

`rpt_gsheets__kippfwd_miami_roster` sources every student column from
`base_powerschool__student_enrollments`, reached through
`int_extracts__student_enrollments`, plus a direct join to
`int_powerschool__gpa_term`. The FAST columns already come from FLDOE.

Miami PowerSchool holds no data past `academic_year = 2025`. Focus already holds
`syear = 2026` — 188 students in grade 7 and 167 in grade 8. At the July
`current_academic_year` rollover to 2026, the extract's
`academic_year >= current_academic_year - 1` filter selects 2025 and 2026, and
the 2026 half is empty.

## Approach

Move the enrollment spine to Focus and the guardian contacts to Finalsite,
keeping PowerSchool only where Focus has no equivalent data.

The output contract does not change. All 30 columns keep their names and types,
so the Google Sheet, the `columns:` block in the properties yml, and the
exposure in `models/exposures/google-sheets.yml` are untouched.

### How kipptaf reaches Focus

`int_focus__student_enrollment` in the `focus` package cannot be referenced from
kipptaf — the package is imported only by `kippmiami`. kipptaf reads Focus
through the BQ-native `kippmiami_dlt_focus` source declared in
`src/dbt/kipptaf/models/focus/sources-bigquery.yml`, the same path
`int_focus__school_year_first_day` already uses, and the path
`src/dbt/focus/CLAUDE.md` recommends for a new kipptaf dependency on Focus data.

Rejected alternatives:

- **kippmiami region source** (`sources-focus-kippmiami.yml` reading the
  district's `stg_focus__*`). Reuses the package join logic but requires the
  `dev` / `zz_stg_` / prod schema branch plus clone seeding for CI, and district
  prod must materialize first.
- **Read raw Focus in the `rpt_` view.** Fewest files, but puts the school,
  grade, and enrollment-code joins in a reporting view where they cannot be
  tested independently or reused.

## Column mapping

Match rates below were measured against PowerSchool for SY2025 grades 7 and 8,
n=365 students.

### Sourced from Focus

| Roster column   | Derivation                                                          |
| --------------- | ------------------------------------------------------------------- |
| `academic_year` | `student_enrollment.syear`                                          |
| `lastfirst`     | `concat(last_name, ', ', first_name)` from `students`               |
| `ps_id`         | `students.custom_l1482` (`powerschool_id`) — 365/365                |
| `mdcps_id`      | `students.custom_l1483` (`disis_id`), zero-padded to width 7        |
| `fleid`         | `students.custom_200000224` — 360/365                               |
| `gender`        | `students.custom_200000000` decoded to `M` / `F`                    |
| `grade_level`   | `cast(school_gradelevels.short_name as int64)` — `'07'` becomes `7` |
| `enroll_status` | Derived, see below                                                  |
| `iep_status`    | `students.custom_698` (ESE FEFP Code) — see recall caveat below     |

`custom_53` (`local_student_id`) is **not** PowerSchool `student_number` —
0/365. Do not use it as the PowerSchool key.

`gender` decodes through `custom_field_select_options.code`, which holds `M` and
`F` — exactly PowerSchool's domain. The `label` values are `Male[M]` and
`Female[F]`; read `code`, not a regex over `label`. Join on
`custom_field_select_options.source_id = custom_fields.id` with
`source_class = 'CustomField'`, and match the stored value against both
`option_id` and `code`, per `src/dbt/focus/CLAUDE.md`.

### Sourced from Finalsite

The eight `contact_1_*` and `contact_2_*` columns come from
`stg_finalsite__contacts` joined to `stg_finalsite__contact_relationships`,
resolved to a Focus student via
`int_finalsite__contact_id_attributes.focus_student_id_prefixed`, which equals
the Focus `student_id`. This is the join `rpt_focus__contacts` already uses.

Guardian ranking mirrors `rpt_focus__contacts` — partition by
`finalsite_enrollment_id`, order by `is_primary desc, last_name, first_name` —
and filters `rel_type` to `parent`, `guardian`, `grandparent`, `stepparent`,
`relative`, `aunt/uncle`. Rank 1 populates `contact_1_*`, rank 2 populates
`contact_2_*`.

Coverage for SY2026 grades 7 and 8, n=365 students:

| Field                     | Populated |
| ------------------------- | --------- |
| `contact_1_name`          | 364       |
| `contact_1_email_current` | 355       |
| `contact_1` phone slot 1  | 360       |
| `contact_2` present       | 255       |

Phone columns map by type: `Cell` to `phone_mobile`, `Home` to `phone_home`. A
contact's two typed slots (`phone_1_type` / `phone_1_number` and `phone_2_type`
/ `phone_2_number`) are searched for each target type.

### Retained from PowerSchool

`previous_year_ada` continues to come from `int_extracts__student_enrollments`
(`ada_unweighted_year_prev`), joined on `student_number = ps_id` and
`academic_year`. Reusing that model preserves the existing
weighted-vs-unweighted SY2025 rule rather than reimplementing it.

Focus cannot supply this: `attendance_completed` holds 1 row, and
`fl_days_present` / `fl_days_absent` on `student_enrollment` are entirely null.

### Cast null

| Column                     | Reason                                                                                                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `advisor_lastfirst`        | Focus has no advisory structure for grades 7-8. Homeroom courses exist only for K-5, `student_enrollment.team_id` is null for all 365 students in both years, and no grade 7-8 course functions as an advisory |
| `gpa_cumulative`, `gpa_y1` | Focus `report_card_grades` holds 1,357 rows total and no GPA model exists in the `focus` package                                                                                                               |

Each gets an inline `-- TODO(#N)` comment at the derivation site pointing at its
follow-up issue, per `src/dbt/CLAUDE.md` — not a note in the yml `description`.
Those two follow-up issues (one for the advisory gap, one for Focus GPA) must be
opened during implementation so the TODO references resolve to something that
stays open after this PR merges.

## `enroll_status` derivation

The output stays `int64` with PowerSchool semantics, because the sheet consumes
those codes.

**Do not derive withdrawal from drop-code presence.** Nearly every SY2025 Focus
enrollment carries a drop code — 227 rows are `W01` (In School Transfer) and 133
are `W02` (In District Transfer) — because that is how Focus closes out a school
year. A presence test would flag roughly 99% of students as transferred out.

Derive from whether the student holds an open enrollment in the current `syear`:

| Output | Condition                                                                |
| ------ | ------------------------------------------------------------------------ |
| `-1`   | `start_date` is in the future                                            |
| `3`    | Drop code short name is `W06` (Graduated With Standard Diploma)          |
| `0`    | An enrollment row exists in the current `syear` with `drop_code is null` |
| `2`    | Otherwise                                                                |

The `0`-versus-`2` rule reproduces PowerSchool `enroll_status` for 341 of 365
students. The 24 disagreements split 16 PowerSchool-`0`-with-no-open-Focus-row
and 8 the other way; PowerSchool froze at the Focus cutover, so Focus is the
more current value in both directions.

## `iep_status` recall

Focus ESE FEFP Code identifies 42 of the 53 IEP students PowerSchool flags via
`spedlep like 'SPED%'` for SY2025 grades 7 and 8 — 79% recall, with 1 student
found by Focus but not PowerSchool. The `ESE Exceptionalities` log field in
`custom_field_log_entries` adds zero additional students.

Accepted as-is. The gap is documented in the column `description` so a consumer
reading `No IEP` knows it is not authoritative. No dbt test guards the recall.

## Grain

One row per student per `academic_year`.

Focus SY2025 grades 7-8 has 366 enrollment rows for 365 students — one student
holds two spans. SY2026 is 1:1. Resolve with
`dbt_utils.deduplicate(partition_by="student_id, syear", order_by="start_date desc")`.
This replaces the current `co.rn_year = 1` filter.

## Filters

`region = 'Miami'` and the `_dbt_source_project` / `union_dataset_join_clause`
plumbing disappear — the `kippmiami_dlt_focus` source is Miami-only by
construction. The `grade_level in (7, 8)` and
`academic_year >= current_academic_year - 1` filters carry over unchanged.

The FAST joins keep their shape, now keyed on the Focus `fleid` and `syear`
rather than the PowerSchool-derived `state_studentnumber`.

## Known limitations

- **`ps_id` is null for roughly 62 SY2026 students** (37 in grade 7, 25 in
  grade 8) — new enrollees with no `powerschool_id` assigned yet. Those students
  also receive no `previous_year_ada`, which is correct because they were not
  enrolled last year. They are likewise absent from the FAST join, which needs a
  FLEID.
- **`previous_year_ada` empties at the SY2027 rollover, not SY2026.** For SY2026
  rows the prior year is SY2025, which PowerSchool holds. It only breaks once
  the prior year is itself a Focus year.
- **`contact_1_phone_home` will look sparse** relative to the PowerSchool era.
  For the primary contact of the SY2026 grade 7-8 roster, 291 phones are typed
  `Cell` and 64 `Home`.

## Testing

Every layer needs a uniqueness test per `src/dbt/CLAUDE.md`. The roster's
contract exposes no column that is both unique and non-null — `ps_id` is null
for new SY2026 enrollees and `fleid` is null for a handful — so the
authoritative grain test lives on the intermediate and the `rpt_` test is
necessarily scoped.

| Model                               | Test                                                                                                            |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `int_focus__student_roster`         | `dbt_utils.unique_combination_of_columns` on (`student_id`, `syear`) — the authoritative grain                  |
| `int_finalsite__student_guardians`  | `dbt_utils.unique_combination_of_columns` on (`focus_student_id_prefixed`, `guardian_rank`)                     |
| `rpt_gsheets__kippfwd_miami_roster` | `dbt_utils.unique_combination_of_columns` on (`academic_year`, `fleid`), with `config.where: fleid is not null` |

Manual verification before opening the PR:

- Row-count parity against the current model for `academic_year = 2025`, grades
  7 and 8 — expect 365 students on both sides.
- Re-run the three identity match rates and confirm they hold at 365/365,
  360/365, and 356/365.
- Confirm `enroll_status` distributes near the PowerSchool SY2025 split (222 at
  `0`, 143 at `2`) rather than collapsing to `2`, which is the symptom of the
  drop-code landmine.

## Out of scope

- Focus attendance ingestion and a `focus` package GPA model. Both are
  prerequisites for restoring `previous_year_ada` beyond SY2026 and the two GPA
  columns; both are ingestion work, not modeling work.
- Any change to `int_extracts__student_enrollments` itself. Other consumers
  depend on its PowerSchool spine.
- The other Miami extracts that read `int_extracts__student_enrollments`. They
  face the same SY2026 cliff, but each needs its own column analysis.
