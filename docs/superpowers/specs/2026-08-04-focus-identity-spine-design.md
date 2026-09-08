# Focus identity spine — design

Restores KIPP Miami to the kipptaf network layer for AY2026 by adding a Focus
branch to the models carrying student, school, and enrollment identity.

Issue: [#4731](https://github.com/TEAMSchools/teamster/issues/4731) (Phase 1 of
[#4729](https://github.com/TEAMSchools/teamster/issues/4729))

## Problem

Miami's SIS moved to Focus. `kippmiami_powerschool` is a frozen archive (final
pull 2026-07-01), and 49 kipptaf models still union that archive as their Miami
branch. From AY2026 forward Miami contributes zero rows to the whole kipptaf
PowerSchool vertical and to the 38 marts downstream of it.

Already wrong in prod: `int_powerschool__student_enrollment_union` and
`dim_student_enrollments` hold 0 Miami rows for AY2026 against 10,117 for the NJ
regions. Miami's first day of AY2026-27 is 2026-08-12.

## What this spec restores

Two different things, worth separating because conflating them overstates the
result.

**Fully restored — 8 marts** gain Miami rows at their own grain, because their
grain driver is a model this spec changes:

`dim_students`, `dim_student_enrollments`, `dim_student_enrollment_status`,
`dim_student_ell_status`, `dim_student_iep_status`,
`dim_student_meal_eligibility_status`, `fct_behavioral_consequences`,
`fct_family_communications`.

The two facts populate because Miami's behavior and communications data comes
from DeansList, which is live for Miami — only the enrollment spine they join
was missing.

**Miami becomes resolvable — 34 marts** total sit downstream of the changed
models. The other 26 gain Miami dimension rows and working FKs, but stay
row-empty for Miami until their own driver is fed: attendance and
`dim_school_calendars` in Phase 2, grades and course enrollments in Phase 3,
contacts separately.

That distinction is the same reachability trap the #4729 audit flagged for
marts: being downstream of a fixed model does not mean a mart's rows appear.
Phase 2 and 3 wait on Focus producing attendance and gradebook rows, tracked as
source-data availability in
[#4220](https://github.com/TEAMSchools/teamster/issues/4220), not as modeling
work.

## Student identity

**The unprefixed Focus student id is the canonical network `student_number`.**
Focus stores `students.student_id` as `8400` (Miami-Dade's FLDOE district
number) prefixed to the student's number. Stripping that prefix yields the
network identifier.

Verified against the frozen archive:

| Measure                                                        | Count |
| -------------------------------------------------------------- | ----- |
| Distinct unprefixed Focus ids                                  | 3,907 |
| Match the archive's `student_number` exactly                   | 3,453 |
| Archive `student_number` values total                          | 3,453 |
| No archive match (students new since the freeze)               | 454   |
| Collisions between those 454 and the 26,706 NJ student numbers | 0     |

Two consequences that shape the whole design:

- **Returning Miami students keep their existing `dim_students.student_key`.**
  That key hashes `student_number` alone, the number is unchanged, so the hash
  is unchanged. Miami history stays attached, and no Cube or Tableau surface
  moves.
- **No crosswalk is needed.** The finalsite `focus_student_id_prefixed` column
  exists to feed the outbound `rpt_focus__*` extracts, which need the prefixed
  form. It is not an inbound translation and must not be used as one.

### The unprefix rule

Strip a leading `8400` where present. Pass any other value through unchanged
rather than guessing at a different prefix — one AY2026 row (a single active
student) carries a 10-digit id that does not start with `8400`. Passing it
through keeps the anomaly visible instead of silently mangling it.

Add a warn-severity test flagging any Miami id that does not match the expected
pattern, and report that record to Ops for correction in Focus.

## Architecture

Two different insertion strategies, chosen per layer.

### Intermediate-layer models take the Focus branch in place

`int_powerschool__student_enrollment_union`, `int_powerschool__terms`, and
`int_powerschool__teacher_grade_levels` are intermediates, so a conforming
`int_focus__*` sibling unions into them with no layer inversion. Their consumers
change nothing — and `int_powerschool__student_enrollment_union` alone serves 13
marts, all of its direct consumers.

### Staging-layer models get a SIS-agnostic sibling

`stg_powerschool__students`, `__schools`, `__studentcorefields`, and
`__u_studentsuserfields` are staging models, and the Focus values they need are
only available through an `int_focus__*` wrapper. Rather than invert the
layering (a pattern only 3 of 783 kipptaf staging models use), add a
SIS-agnostic intermediate per model and repoint its **mart** consumers:

```text
stg_powerschool__students ──────┐
                                ├── int_students__students ── dim_students
int_focus__students_conformed ──┘
```

| New model                           | Unions                                                       | Marts repointed                                                                                               |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `int_students__students`            | `stg_powerschool__students` (NJ) + Focus conform             | `dim_students`                                                                                                |
| `int_students__schools`             | `stg_powerschool__schools` (NJ) + Focus conform              | `dim_assessment_goals`, `dim_course_sections`, `dim_school_calendars`, `dim_student_enrollments`, `dim_terms` |
| `int_students__student_core_fields` | `stg_powerschool__studentcorefields` (NJ) + Focus conform    | `dim_student_ell_status`, `dim_student_iep_status`                                                            |
| `int_students__student_user_fields` | `stg_powerschool__u_studentsuserfields` (NJ) + Focus conform | `dim_students`                                                                                                |

The PowerSchool side of each union must **exclude the Miami archive**, or Miami
students appear twice — once from the archive, once from Focus. Filter on
`_dbt_source_relation`.

### Conform models

One `int_focus__*_conformed` model per spine model, holding the column renames,
the unprefix rule, and the value translations. Keeping them separate makes each
translation independently testable against the archive and gives the historical
reconciliation a single target per model.

`union_relations` builds a column superset and null-fills absent columns with
`cast(null as <type>)`, so PowerSchool-only columns (dcids, NJ state fields)
resolve to null for Miami with no special handling. The conform models therefore
project only what Focus can supply.

## Column vocabulary

The spine keeps **PowerSchool column names**. Renaming to the source-agnostic
`marts/CLAUDE.md` R1–R10 vocabulary is Phase 5, sequenced with the `base_`
retirement in [#3999](https://github.com/TEAMSchools/teamster/issues/3999) and
[#2541](https://github.com/TEAMSchools/teamster/issues/2541). Conforming Focus
into the existing names keeps this change to zero column churn for the marts
being repointed.

Value translations, sourced from `int_focus__students` except where noted:

| Network column                                                  | Focus column                                                 | Work                                |
| --------------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------- |
| `student_number`                                                | `student_id`                                                 | strip the `8400` prefix             |
| `lep_status`, `spedlep`, `lunchstatus`                          | no usable Focus source — see below                           | archive carry-forward; null for new |
| race and ethnicity                                              | `race_*`, `ethnicity_hispanic_or_latino`, `single_ethnicity` | direct, already decoded             |
| `entrydate`, `exitdate`                                         | `startdate`, `exitdate`                                      | rename                              |
| `cohort`                                                        | `year_entered_ninth_grade`                                   | derive; null for K-8                |
| `rn_year`, `year_in_school`, `year_in_network`, `is_enrolled_*` | same names                                                   | already computed                    |
| `students_dcid`, NJ state fields                                | none                                                         | null for Miami, by design           |

**The governing rule for every translation is to reproduce the values Miami's
PowerSchool archive carried.** Every consumer was written against those, and
`base_powerschool__student_enrollments` already branches on `region = 'Miami'`
to pass Miami's own domain through for `spedlep`, `lunchstatus`, and
`lep_status`. Because Focus covers AY2018 through AY2026, the structural
translations are testable against the archive across eight overlapping years.

### The three status fields have no usable Focus source

Each of `spedlep`, `lunchstatus`, and `lep_status` was checked against the
archive independently. All three collapse, for the same root cause as attendance
and gradebook: AY2026-27 is Miami's first Focus year and this data has not been
entered or migrated.

| Network column | Focus field                      | What Focus holds                                        | Archive AY2025    |
| -------------- | -------------------------------- | ------------------------------------------------------- | ----------------- |
| `spedlep`      | `ese_fefp_code`                  | 162 students; ESE log covers 10                         | 419 SPED          |
| `lunchstatus`  | `free_reduced_meals_program`     | one constant, `CEP NOT Direct Cert [N]`, 3,874 students | `F` 1,422, `P` 92 |
| `lep_status`   | `english_language_learner_pk_12` | 3,844 at `Not applicable [ZZ]`; 5 `LY`, 5 `LF`, 5 `LZ`  | 153 ELL           |

Why each is unusable, and not merely sparse:

- `ese_fefp_code` is a Florida Education Finance Program **funding** code,
  populated only for specific ESE service levels — not a general IEP flag. Focus
  does define richer ESE fields (`primary_exceptionality`, `ESE`,
  `ESE Primary Computed`, `IEP`, `504 Indicator Computed`), but they are
  log-based custom fields covering 10 students.
- `free_reduced_meals_program` records **school-wide** CEP eligibility, not
  per-student status — under CEP the district collects no individual meal
  applications, so there is no per-student signal to read.
- `english_language_learner_pk_12` puts 98% of students at `ZZ`. The 5/5/5 split
  across the three real codes reads as placeholder data, not a population.

Taking any of them would under-report by 60% to 97% silently, which is worse
than reporting nothing.

Handling for all three:

- **Returning students** carry the value forward from the frozen archive. It is
  student-level and the archive is static, so it is stable.
- **New students** get `null` — not `'No IEP'`, not `'F'`, not `false`. A false
  negative on IEP status is compliance-adjacent, and a fabricated FRL or ELL
  value feeds an economic-disadvantage or service-eligibility proxy. Unknown
  must read as unknown. Null `lunchstatus` is already ~23% of Miami archive
  rows, so consumers already tolerate it.
- Add a warn-severity test on the null count for each, so the gaps stay visible
  and close when Focus is populated.
- Track population as a data-availability item alongside #4220, not as modeling
  work here.

Do not use `ese_fefp_code` for `spedlep`. It is the right source for a future
FEFP-funding measure and nothing else.

**Consequence for scope.** `dim_student_iep_status`,
`dim_student_meal_eligibility_status`, and `dim_student_ell_status` are three of
the eight fully-restored marts. They restore rows, but AY2026 status values for
new Miami students are null until Focus is populated. Returning students are
exact. This belongs in the PR description and in the stakeholder note.

## Enrollment: history and alumni placeholders

> **CORRECTED DURING IMPLEMENTATION.** This section originally concluded that no
> cutover date was needed. That was wrong, and the paragraph below is superseded
> by _The AY2026 cutover_ that follows it. Focus does carry the history, but it
> dates a stint differently, and `entrydate` feeds the enrollment key hash.

No cutover date is needed. Focus carries Miami's real enrollment stints for
AY2018 through AY2026, matching the archive once alumni placeholders are
excluded.

### The AY2026 cutover

Reconciling the conformed Focus output against the archive for AY2018 through
AY2025 returned identical stint counts — 8,315 on both sides — but 954
single-stint AY2025 students differ by exactly 42 days:

| Source              | AY2025 entry date for a returning student |
| ------------------- | ----------------------------------------- |
| PowerSchool archive | `2025-07-01` (administrative rollover)    |
| Focus               | `2025-08-12` (actual first day of school) |

July 1 is the network PowerSchool convention, not a Miami quirk — Camden dates
2,118 AY2025 stints there and Newark 6,472. Paterson already diverges.

This matters because `entrydate` is an input to the `student_enrollment_key`
hash:

```text
surrogate_key(student_number, _dbt_source_project, academic_year, entrydate)
```

Adopting Focus dates for closed years would therefore recompose 954 historical
Miami enrollment keys. Those keys are load-bearing: `fct_family_communications`
alone holds **114,038 rows** keyed to Miami's 8,315 historical enrollments, and
re-keying orphans every fact attached to a changed stint — silently, since a
surrogate key that no longer matches produces no error.

So the Miami branch cuts over by academic year rather than replacing history:

- **Archive** supplies AY2025 and earlier, plus its alumni graduate placeholders
  in any year.
- **Focus** supplies AY2026 forward.

Neither system is wrong about the date; they answer different questions. Focus's
answer is the more accurate one, and it is what Miami gets from AY2026 on.
Aligning the historical record to it is a separate migration with its own
key-churn budget, not a side effect of restoring the current year.

The archive contributes exactly one thing: **1,002 alumni graduate-placeholder
rows** (`enroll_status = 3` with null `entrydate` and `exitdate`, one row per
academic year), which `kipptaf/CLAUDE.md` requires retaining for KIPP Forward
reporting and which Focus has no equivalent for.

So the Miami branch of `int_powerschool__student_enrollment_union` is Focus for
real stints plus the archive filtered to
`enroll_status = 3 and entrydate is null`. The filter goes in the model body,
not `union_relations`' `where` argument, which applies to every relation.

A test must assert that no Miami `(student_number, academic_year, entrydate)`
appears in both branches.

## Accepted divergence

Repointing only mart consumers means the marts carry Miami while 33 non-mart
consumers of the four staging models do not, until Phase 5 migrates them. This
is a deliberate tradeoff, taken to keep the change set small.

The sharpest case is `rpt_gsheets__kippmiami_payout_roster` — a Miami-only
extract reading `stg_powerschool__students`, which stays empty for Miami.
`rpt_littlesis__enrollments` and `int_tableau__fresh_enrollment_scaffold` are
also affected; the FRESH scaffold already reads Focus directly on a separate
path, so it is inconsistent rather than empty.

Anyone comparing a Tableau extract against Cube during this window will see them
disagree for Miami. That is expected, not a defect. The full list is in the
appendix and belongs in the PR description too.

## Validation

1. **NJ parity.** The three NJ regions' output must be row-identical to current
   prod for every modified model. `count(*)` plus
   `count(distinct format('%T|%T', ...))` on key columns, PR-branch schema
   against prod.
2. **Miami historical reconciliation.** For AY2018 through AY2025, compare each
   conform model's output against the archive on
   `(student_number, academic_year, entrydate)`, then on each translated value.
   This is the only real test of the race, ethnicity, and cohort translations,
   and it proves the three status carry-forwards reproduce the archive exactly
   for returning students.
3. **`student_key` stability.** Assert that every Miami `student_number` present
   in prod `dim_students` today still hashes to the same key. This is the
   no-churn guarantee and must be proven, not assumed.
4. **Alumni placeholders preserved.** Count the `enroll_status = 3` null-date
   rows before and after; expect 1,002 either side.
5. **Consumer resolution.** `dbt build --empty` across the repointed marts and
   their descendants.
6. Uniqueness test on each new model's key, and the warn-severity id-pattern
   test from the unprefix rule.

## Out of scope

- SIS-neutral column vocabulary and the `base_` retirement — Phase 5.
- Attendance (Phase 2) and gradebook grades (Phase 3) — blocked on Focus
  producing rows, per #4220.
- Migrating the 33 non-mart consumers — Phase 5.
- No mart output column changes, so no Cube updates.

## Open items

- `int_focus__student_enrollment.student_number` holds the **prefixed** id under
  a name implying the network student number. Anyone joining on that name gets
  zero matches with no error. Its consumers
  (`int_tableau__fresh_enrollment_scaffold`, `rpt_focus__student_enrollment`)
  need checking for that assumption. Rename is out of scope here but should be
  filed.
- Decide who owns getting Focus ESE and meal-eligibility fields populated, since
  `spedlep` and `lunchstatus` stay null for new Miami students until that
  happens.
- The one AY2026 student whose Focus id lacks the `8400` prefix needs an Ops
  correction.

## Prerequisites

`stg_focus__co_teachers`, `stg_focus__students_join_users`, and
`int_focus__schedule` shipped in
[#4725](https://github.com/TEAMSchools/teamster/pull/4725) but are not declared
in `kipptaf/models/focus/sources-kippmiami.yml` and have no kipptaf wrapper. Per
`kipptaf/CLAUDE.md` every source added there needs a matching `union_relations`
passthrough, and consumers read the wrapper. Declaring and wrapping them is the
first step of implementation.

Each kipptaf PR needs `dbt clone --select ... --target staging` to refresh
`zz_stg_kippmiami_focus`, or CI reads a stale copy and fails deterministically.

## Appendix — consumers staying PowerSchool-only

The 33 non-mart consumers of the four staging models. These keep reading
`stg_powerschool__*` and remain Miami-less until Phase 5 migrates them.

Intermediates (10):

```text
base_powerschool__student_enrollments      int_kippadb__roster
int_assessments__academic_goals            int_powerschool__gradebook_assignments_scores
int_extracts__course_schedule_by_term      int_tableau__fresh_enrollment_scaffold
int_finance__enrollment_targets            int_tableau__gradebook_audit_teacher_scaffold
int_google_sheets__dibels_pm_expectations  stg_people__student_logins
int_google_sheets__topline_aggregate_goals
```

Extracts and reports (23):

```text
rpt_clever__enrollments                rpt_gsheets__csgf_enrollment
rpt_clever__schools                    rpt_gsheets__kippmiami_payout_roster
rpt_clever__sections                   rpt_illuminate__roles
rpt_clever__staff                      rpt_illuminate__sites
rpt_deanslist__family_contacts         rpt_littlesis__enrollments
rpt_deanslist__hs_transcript_programs  rpt_parentsquare__schools
rpt_deanslist__state_test_scores       rpt_parentsquare__staff
rpt_deanslist__student_misc            rpt_powerschool__autocomm_students
rpt_deanslist__transcript_gpas         rpt_tableau__academic_goals_rollup
rpt_deanslist__transcript_grades       rpt_tableau__college_assessment_dashboard_de
rpt_tableau__state_assessments_dashboard
rpt_tableau__student_attrition_over_time_v1
```

Note that `stg_people__student_logins` is itself a staging model consumed
elsewhere, so its Miami gap propagates further than this list shows. Worth
checking during Phase 5 sequencing.
