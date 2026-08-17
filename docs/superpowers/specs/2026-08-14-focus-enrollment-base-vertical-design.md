# Focus branch into the kipptaf enrollment `base_` vertical

Design for [#4868](https://github.com/TEAMSchools/teamster/issues/4868), a
sub-issue of [#4729](https://github.com/TEAMSchools/teamster/issues/4729).

## Problem

Phase 1 ([#4731](https://github.com/TEAMSchools/teamster/issues/4731),
[#4775](https://github.com/TEAMSchools/teamster/pull/4775)) restored KIPP Miami
to the kipptaf identity spine and the 14 marts downstream of it. It did not
touch the second kipptaf enrollment vertical.

`base_powerschool__student_enrollments` still unions the frozen
`kippmiami_powerschool` archive as its Miami branch. Miami therefore reads empty
for AY2026 across 15 consumer sites, and through
`int_extracts__student_enrollments` across roughly 150 more.

This is the live, user-facing half of the gap.
`rpt_gsheets__student_contact_info` serves 1,114 Miami students frozen at
`academic_year = 2025` with `enroll_status = 0` to four Google Sheets exposures,
including `gsheets_student_contact_info` and `gsheets_student_logins`.

This spec absorbs [#4811](https://github.com/TEAMSchools/teamster/issues/4811)
and treats [#3999](https://github.com/TEAMSchools/teamster/issues/3999) as the
follow-on rather than a blocker.

### Corrections to the #4729 audit

Three claims in the parent issue did not survive verification against `main`.

- The audit says the insertion point is
  `int_powerschool__student_enrollment_union`, citing #3999 as recording that
  all mart consumers already migrated off `base_`. #3999 is open and its title
  reads "migrate **remaining** consumers".
  `base_powerschool__student_enrollments` has 15 live reference sites under
  `models/` and `tests/`, not 9 — the earlier count treated
  `int_extracts__student_enrollments` as one site when it holds five.
- Phase 1 did not add a Focus branch to
  `int_powerschool__student_enrollment_union`. It built a parallel layer:
  `int_students__student_enrollment_union` is that model filtered to exclude
  `kippmiami`, joined by `full union all corresponding` to a Focus-conformed
  block. The same shape covers `int_students__students`, `__schools`,
  `__student_core_fields`, `__student_user_fields`, `__terms`, and
  `__teacher_grade_levels`.
- The Phase 1 comment says `cohort` derives from `year_entered_ninth_grade`. It
  does not. PowerSchool computes it as grade-level arithmetic in
  `int_powerschool__student_enrollment_union`. The arithmetic reproduces the
  archive's values; `year_entered_ninth_grade` would not, and is null for K-8.

`kippmiami` also no longer imports the `powerschool` package, so there is no
Miami district `base_` model to add a Focus branch to. The archive is BQ-native
and frozen.

## Decision

Keep `base_powerschool__student_enrollments` for compatibility. Build the Focus
branch into a SIS-neutral model underneath it.

Column vocabulary stays PowerSchool for now. The R1-R10 source-agnostic rename
is Phase 5, where it belongs with the `base_` retirement
([#3999](https://github.com/TEAMSchools/teamster/issues/3999),
[#2541](https://github.com/TEAMSchools/teamster/issues/2541)). Renaming here
would churn 137 columns and every downstream consumer for no gain in this
issue's goal, which is Miami rows.

## Architecture

Before:

```text
district base_powerschool__student_enrollments x4 (Miami = frozen archive)
  └─ kipptaf base_powerschool__student_enrollments (137 cols, +10 left joins)
       └─ 15 consumer sites
            └─ int_extracts__student_enrollments → ~150 consumers
```

After:

```text
district base_powerschool__student_enrollments x3 (NJ only) ─┐
                                                             ├─ int_students__student_enrollments
int_focus__student_enrollments ─┐                            │   (+10 left joins, unchanged)
int_focus__students             ├─ focus_conformed CTE ──────┘        │
int_focus__advisory (new)       ┘                                     │
                                                    base_powerschool__student_enrollments
                                                      = select * from the above
```

Six file-level changes, three in the `focus` package and three at kipptaf.

The package half exists because the Focus student conform lives there, not at
kipptaf. kipptaf's `int_focus__students` is a bare `union_relations`
passthrough; `spedlep`, `gifted_and_talented`, and `lep_status` are all
conformed in the package by reading `*_label` columns from
`int_focus__students__pivot`. `kipptaf/CLAUDE.md` forbids the alternative —
exposing `int_focus__custom_field_options` at kipptaf relocates hand-rolled
translation instead of removing it.

1. **`stg_focus__students`** — add `custom_818 as homeless_unaccompanied_youth`.
   It is not staged today and is the only field distinguishing Y1 from Y2. The
   model is contract-enforced, so its properties YAML needs the column too.
1. **`int_focus__students__pivot`** — add `custom_818` to the pivot input and
   its label to the output. The `custom_71` and `custom_820` labels already
   exist there.
1. **`int_focus__students`** (package) — project the three labels into the
   `labeled` CTE and conform `homeless_code`, `is_homeless`,
   `homeless_primary_nighttime_residence_code`, and `lunchstatus`, alongside the
   existing `spedlep` / `gifted_and_talented` / `lep_status` block.
1. **New `int_students__student_enrollments`.** Today's
   `base_powerschool__student_enrollments` body, with the
   `kippmiami_powerschool` relation dropped from the `union_relations` list and
   a `focus_conformed` CTE joined by `full union all corresponding`. The 10
   kipptaf-level left joins (salesforce, njsmart, titan, student logins, fldoe
   fte, illuminate, edplan, staff roster) are unchanged. Miami rows resolve null
   through the joins keyed on `students_dcid`, exactly as they already do for
   other PowerSchool-only fields.
1. **New `int_focus__advisory`** in the kipptaf focus layer. Analogue of
   `int_powerschool__advisory`, but matched on course title rather than the
   `homeroom` flag. That flag exists on three raw Focus tables — `courses`
   (14,616 rows), `master_courses` (71,334) and `users` (2,185) — and is NULL in
   every row of all three, so it carries no data anywhere in Focus. Select rows
   where `course_title` starts with `Homeroom`, resolve the teacher name through
   `int_focus__users`, and take `advisory_name` from `course_period_short_name`,
   falling back to the teacher name.

   `course_period_short_name` is the right column and the others are not:
   `course_period_title` concatenates period code, college and teacher
   (`HR HR - Gonzaga - Gabriela Hector`), `course_short_name` is the FLDOE
   course code (`5022000R3`), and `course_title` only identifies the row as a
   homeroom (`Homeroom - 3rd Grade`).

   **Elementary only.** 957 of 983 ES students (97%) carry a Homeroom course in
   AY2026; MS carries 42 of 593 and HS 0 of 114. The archive covered Miami ES
   and MS at roughly 99%, so this is a regression for MS, not a like-for-like
   port. MS and HS rows read null. `int_focus__schedule` also holds AY2026
   alone, so advisory is null for every historical year and cannot be reconciled
   against the archive.

   Tracked for Ops separately: scheduling homeroom course periods for MS and HS,
   or populating the `homeroom` flag, makes this model work network-wide with no
   code change.

1. **`base_powerschool__student_enrollments` becomes a passthrough** —
   `select * from {{ ref("int_students__student_enrollments") }}`. All 15
   consumer sites keep working untouched. This is the seam #3999 deletes.

### Accepted duplication

The Focus conform now appears twice: once in the spine
(`int_students__student_enrollment_union`, 22 columns) and once here (roughly
40). It is projection and renaming, not logic.

De-duplicating it means either pushing the 10 left joins upstream of the 14
marts that read the spine today, or adding a join-back from the spine to the
district `base_` union. Both are worse than carrying roughly 20 lines of
duplicated projection. Phase 5 collapses the two when `base_` retires.

The spine and its 14 marts are not touched by this work.

## Conform mapping

`base_` emits 137 columns; the spine emits 52, of which 51 are shared. The
`focus_conformed` CTE must produce the full district-`base_` column set.

### Straight projection

Already present on `int_focus__student_enrollments`, no derivation needed:
`school_level`, `school_abbreviation`, `school` as `school_name`,
`reporting_schoolid`, `is_enrolled_fdos`, `entrycode`, `exitcode`,
`grade_level`, `enroll_status`, `year_in_school`, `year_in_network`, `rn_year`,
`is_enrolled_oct01`, `is_enrolled_oct15`, `is_enrolled_mar15`, plus the dates
and identifiers the spine already conforms.

### Derived

Each reproduces the PowerSchool formula against Focus columns.

| Column                                                          | Rule                                                                                        |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `cohort_primary`                                                | `(academic_year + 13) + (-1 * grade_level)`                                                 |
| `cohort_secondary`                                              | `max(if(year_in_school = 1, cohort_primary, null))` over (student, school)                  |
| `cohort`                                                        | grade 99 to `cohort_graduated`; grade 9 and up to `cohort_secondary`; else `cohort_primary` |
| `boy_status`                                                    | grade-history `lag()` — Graduated / New / Re-Enrolled / Promoted / Retained / Demoted       |
| `entry_schoolid`, `entry_grade_level`                           | `max(if(year_in_network = 1, x, null))` over (student)                                      |
| `is_retained_ever`                                              | `max(is_retained_year)` over (student)                                                      |
| `advisory_section_number`, `advisory_name`, `advisor_lastfirst` | new `int_focus__advisory`, ES and AY2026 only — see the architecture note                   |

`boy_status` needs a prior-year grade level and academic year per student.
PowerSchool compares `yearid`; Focus carries `academic_year`, and the
`yearid - yearid_prev > 1` gap test is equivalent on either.

### Custom-field decodes

Two fields the archive left null for Miami are populated in Focus and decode
through `int_focus__custom_field_options`.

**Homelessness** — `custom_820` Homeless Student PK-12 maps four ways onto
`homeless_primary_nighttime_residence_code`, and `custom_818` Homeless
Unaccompanied Youth separates Y1 from Y2.

| `custom_820` | Label                                              | Residence code | `homeless_code` |
| ------------ | -------------------------------------------------- | -------------- | --------------- |
| `A`          | Living in emergency or transitional shelter        | 1              | Y1 or Y2        |
| `B`          | Sharing the housing of other persons               | 2              | Y1 or Y2        |
| `D`          | Living in cars, parks, campgrounds, train stations | 3              | Y1 or Y2        |
| `E`          | Living in hotels or motels                         | 4              | Y1 or Y2        |
| `F`          | Student awaiting foster care                       | null           | Y1 or Y2        |
| `N`          | Student is not homeless (default)                  | null           | N               |

`custom_818` decides Y1 versus Y2. It is a five-option select, not a flag, so a
null check is not enough — a homeless student explicitly coded `N` is
accompanied, and would be mislabeled Y2 by a presence test:

| `custom_818` | Meaning                                                         | `homeless_code` |
| ------------ | --------------------------------------------------------------- | --------------- |
| `Y`          | Not in the physical custody of a parent or guardian             | Y2              |
| `C`          | Homeless, 16 or older, not in custody, certified by the liaison | Y2              |
| `U`          | Homeless, under 16, not in custody                              | Y2              |
| `N`          | Homeless, but does not meet the unaccompanied definition        | Y1              |
| `Z`          | Not homeless, not unaccompanied                                 | Y1              |
| null         | No unaccompanied record                                         | Y1              |

`custom_820` gates the whole decision: its `N` yields `homeless_code = 'N'`
regardless of what `custom_818` says, and its null yields null.

The two fields do not share a label convention. Every `custom_820` label carries
a bracketed `[code]` suffix, but only `Y` and `N` of `custom_818`'s five do — so
`custom_818` is read from the label's leading character, which all five carry,
rather than by bracket extraction.

`is_homeless` follows the staging formula, `homeless_code in ('Y1', 'Y2')`.

**Meal eligibility** — `custom_71` Free/Reduced Meals Program is Florida's full
eligibility element, not a direct-certification flag.

| `custom_71`        | Meaning                                               | `lunchstatus` |
| ------------------ | ----------------------------------------------------- | ------------- |
| `F`, `D`, `C`, `9` | Free, incl. direct cert and CEP with direct cert      | `F`           |
| `3`, `E`, `R`      | Reduced, incl. direct cert variants                   | `R`           |
| `1`, `0`           | Applied Not Eligible, Did Not Apply                   | `P`           |
| `N`, `4`           | CEP NOT Direct Cert, USDA Provision 2                 | null          |
| `2`                | Eligible for Free Lunch, marked DO NOT USE AFTER 1516 | null          |

`N` and `4` describe the school's program rather than the student, so they carry
no per-student eligibility. Every Miami student currently sits at `N`, so this
mapping yields no F/R/P today. It goes live unchanged the moment Ops populates
real values.

`custom_100100000` Lunch Program exists in the field catalog but is
zero-populated; `custom_71` is the only meal field carrying data.

### Null-filled

Each checked against `stg_focus__custom_fields`, the field catalog — not against
the columns `stg_focus__students` happens to project. Focus holds 838
`SISStudent` custom fields; the staging model projects roughly 50, so a column's
absence from the staging model is not evidence Focus lacks the field.

| Column                                                                                                 | Reason                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `is_self_contained`                                                                                    | `custom_863` IDEA Educational Environment is a real placement field, but its configured option set covers restrictive settings (center school, residential, hospital or homebound) and omits the regular-class percentage codes that define self-contained. Deferred; 3,865 students sit at the default `Z`. |
| `is_out_of_district`, and the out-of-district arms of `reporting_schoolid` and `reporting_school_name` | `custom_128` Resident Status carries 352 rows but is residency-for-tuition (In-County Resident, Out-of-State, Foreign Exchange), a different concept from special-program out-of-district placement. Miami falls to the non-OOD branch.                                                                      |
| `exit_code_kf`, `exit_code_ts`                                                                         | `custom_661` and `custom_856` Basis of Exit are ESOL exit criteria (CELLA, FAST ELA, ELL Committee), not KIPP Forward college-tracking codes. Already null for Paterson via a Jinja branch, so the null is precedented.                                                                                      |
| `advisor_teachernumber`                                                                                | No network teacher number in Focus. The computed fields `custom_l1780` Advisor Name, `custom_l1781` Advisor Email, and `custom_l1782` Homeroom Section do not land in the dlt table, which is why advisory is derived from `int_focus__schedule` instead.                                                    |

Downstream, `if(is_self_contained, ...)` renders null identically to today's
`false`, so no consumer changes behavior.

## Validation

1. **NJ parity.** The three NJ regions must be row-identical to prod: `count(*)`
   plus
   `count(distinct format('%T|%T', student_number, academic_year, entrydate, _dbt_source_project))`
   on the PR-branch build against
   `kipptaf_powerschool.base_powerschool__student_enrollments`. Dropping the
   Miami relation must not perturb NJ.
1. **Miami historical reconciliation, AY2018 through AY2025.** Compare conformed
   Focus rows against the archive on student number and academic year, then per
   derived value — `cohort`, `boy_status`, `homeless_code`, `school_level`.
   Reconcile on (student, academic year), not entry date: Focus dates a
   returning student's stint to the real first day of school where PowerSchool
   used a July 1 administrative rollover, so roughly 1,421 of 8,776 historical
   stints carry a different `entrydate`. `advisory_name` is NOT in this check —
   `int_focus__schedule` holds AY2026 alone, so advisory is null for every
   historical year by construction.
1. **Miami AY2026 presence.** Roughly 1,585 rows where there are 0 today,
   including 114 HS students — a school level the archive never carried, so the
   HS paths in `base_` (weighted ADA, `ktc_cohort`, the KIPP Forward joins) see
   Miami rows for the first time. Spot-check those columns rather than assuming
   the NJ behavior transfers.
1. **Advisory coverage.** 957 ES students populated, MS and HS null. Assert the
   ES count rather than a network-wide non-null rate, which would fail by
   design.
1. **Extract acceptance.** `rpt_gsheets__student_contact_info` reports Miami at
   `academic_year = 2026`, closing #4811.
1. **Consumer resolution.** `dbt build --empty` across the descendant graph —
   all 15 sites plus everything under `int_extracts__student_enrollments`.
1. **Uniqueness** on the new model's grain, carried over from `base_`.

Tests and column documentation move to the new model's properties YAML.
`base_powerschool__student_enrollments` keeps only a model-level description
noting it is a compatibility passthrough scheduled for removal under #3999.
Leaving the tests on the passthrough would re-scan 137 columns for nothing.

## Rollout

Single PR, using the cross-project workflow in `kipptaf/CLAUDE.md` rather than
the default two-PR package-then-kipptaf sequence.

This works because `models/focus/sources-kippmiami.yml` already carries the
`target=staging` branch routing to `zz_stg_kippmiami_focus`. The package change
adds columns, and per `src/dbt/CLAUDE.md` a column ADD does not reach an
unmodified kipptaf `union_relations` wrapper — the wrapper defers to the Staging
environment, so the new columns never appear and downstream models fail
`Name <col> not found`. Two steps close that gap:

- `dbt build --select int_focus__students --project-dir src/dbt/kippmiami --target staging`
  writes the widened model into the shared `zz_stg_kippmiami_focus`. This is a
  shared-schema write and needs direct user authorization.
- Force the kipptaf `int_focus__students` wrapper `state:modified` with a doc
  comment in its `.sql`, so CI rebuilds it against the widened staging copy. A
  properties-YAML `description` change does not mark a model modified.

`int_focus__schedule` and `int_focus__users` are already declared and wrapped at
kipptaf, so `int_focus__advisory` needs no new source declaration.

dbt Cloud CI builds the kipptaf project, so CI here is real validation rather
than the trivial no-op a district-only PR produces. The `focus` package models
are not built by CI — validate them locally through the `kippmiami` project-dir
per `src/dbt/CLAUDE.md`.

Post-merge, `stg_focus__students` and both intermediates rematerialize in
kippmiami prod via Dagster before the kipptaf models pick up real values.

The new model emits the same 137-column set `base_` emits today, so no
downstream contract needs updating and `int_extracts__student_enrollments`'
`e.* except (...)` passthrough is unaffected.

### Known effects

- Miami historical enrollment dates shift for roughly 1,421 stints, because
  Focus becomes the source for `base_`'s Miami rows as it already is for the
  spine's. Anything reading Miami history through
  `int_extracts__student_enrollments` sees the new dates. This is the same trade
  Phase 1 made and documented.
- [#4803](https://github.com/TEAMSchools/teamster/issues/4803) orphan counts
  rise. More Miami surface moves onto Focus dates while
  `fct_student_attendance_daily` still keys off archive dates. The test stays
  `severity: warn` and does not block CI; Phase 2 resolves it.
- **`lunch_status` and `lunch_application_status` go blank for Miami** — 8,315
  non-null rows today to 0. The archive held real F/R/P values; Focus's only
  meal element is a school-level CEP code that says nothing about the individual
  student, so the conform maps it to null (see the meal-eligibility table
  above). Decision (2026-08-14): accept. Miami's economic-disadvantage proxy
  loses its historical values along with the archive, and that is a conversation
  for Ops rather than a modeling fix.

- **`is_504` reads null for Miami rather than false.** The network expression
  `coalesce(njr.pid_504_tf, suf.is_504, false)` resolves both inputs through
  `students_dcid`, which Focus never populates, so it would have returned a
  fabricated `false` for every Miami row — asserting "no 504 plan" where prod
  carries 191 rows across 55 students. Focus has no 504 field at all, so the
  Miami branch returns null. Downstream `if(is_504, ...)` renders null and false
  identically, so no consumer changes behavior; the data simply stops claiming
  something it does not know.

- **`school_level` is repaired for Miami's closed legacy schools.** Two closed
  schools carry no `school_level_label` in Focus — Sunrise (2,160 rows,
  AY2018-2022) and Liberty (896 rows, AY2019-2022) — so `int_focus__schools`
  left them null and ES/MS/HS-split reporting lost Miami's first five years.
  `stg_google_sheets__people__locations` already carries `grade_band` for all
  seven Miami schools keyed on `focus_school_id`, and
  `int_focus__student_enrollments` already joins it, so the fix is a coalesce at
  that model. Note the reach: that model also feeds the Phase 1 spine and its 14
  marts, so this corrects `school_level` for Miami network-wide, not only in the
  `base_` vertical.

- **1,002 Miami alumni graduate-placeholder rows leave `base_`.** These are
  `enroll_status = 3` rows with null entry and exit dates, one per student per
  academic year — 420 distinct students across AY2022 to AY2025, matching 881
  rows in `int_kippadb__roster`. Dropping the archive branch removes them, the
  same way Phase 1 already removed them from the spine (which holds 57 Miami
  status-3 rows against `base_`'s 2,123).

  This contradicts #4729's "do not simply drop the archive branch" note and the
  `kipptaf/CLAUDE.md` rule that derived enrollment models must retain them. Both
  were written before Phase 1 shipped. Decision (2026-08-14): drop them, keeping
  `base_` consistent with the spine rather than carrying a divergence between
  the two enrollment verticals. `kipptaf/CLAUDE.md` is amended in this PR to
  record Miami as a deliberate exception; #4729's note needs the same
  correction.

  The KIPP Forward consequence is real and accepted: Miami alumni reached
  through `int_kippadb__roster` lose their placeholder enrollment rows. Phase 1
  has already been in production without them on the spine side.

- **Miami ES `team` values change format.** `int_extracts__student_enrollments`
  renames `advisory_section_number` to `team`, which reaches the Google Sheets
  extracts. KIPP names Miami homerooms after colleges; the archive stored the
  section as grade digit plus college (`4Gonzaga`, `2Spelman`, `0BU`) while
  Focus stores only the college (`Gonzaga`, `Spelman`, `BU`). Decision
  (2026-08-14): ship the bare college name rather than reconstruct the grade
  prefix. `advisory_name` is unaffected — the archive derived it by stripping
  that same prefix, so it already was the college name.

## Out of scope

- SIS-neutral column vocabulary and `base_` retirement — Phase 5, #3999 and
  #2541.
- Attendance (Phase 2) and gradebook grades (Phase 3) — blocked on Focus
  producing rows, see
  [#4220](https://github.com/TEAMSchools/teamster/issues/4220).
- No mart output column changes, so no Cube updates.

## Follow-up for Ops, not this PR

Two items, each filed as its own issue rather than carried in this PR.

**Homeroom scheduling for MS and HS.** Focus's `homeroom` flag is null
everywhere, and only ES has Homeroom course periods scheduled, so advisory
resolves for 957 of 1,690 AY2026 students. Either scheduling homeroom course
periods for MS and HS or populating the `homeroom` flag makes
`int_focus__advisory` work network-wide with no code change. The archive covered
Miami ES and MS at roughly 99%, so this is a live reporting regression for MS
until it is resolved.

**Homelessness field maintenance.** The `custom_820` option set labels `N` as
"Student is not homeless-default", and its options describe residence type
rather than custody. Confirm with the Miami team that `custom_818` Homeless
Unaccompanied Youth is being maintained — it is the only field distinguishing Y2
from Y1 and currently carries one populated row.
