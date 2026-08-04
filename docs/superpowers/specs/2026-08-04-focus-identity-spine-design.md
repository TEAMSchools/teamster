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

Value translations, all available on `int_focus__students`:

| Network column                                                  | Focus column                                                 | Work                                      |
| --------------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------- |
| `student_number`                                                | `student_id`                                                 | strip the `8400` prefix                   |
| `lep_status`                                                    | `english_language_learner_pk_12`                             | code to boolean                           |
| `spedlep`, `special_education_code`                             | `ese_fefp_code`                                              | FL ESE FEFP code to the archive's strings |
| `lunchstatus`                                                   | `free_reduced_meals_program`                                 | FL program code to the archive's values   |
| race and ethnicity                                              | `race_*`, `ethnicity_hispanic_or_latino`, `single_ethnicity` | direct, already decoded                   |
| `entrydate`, `exitdate`                                         | `startdate`, `exitdate`                                      | rename                                    |
| `cohort`                                                        | `year_entered_ninth_grade`                                   | derive; null for K-8                      |
| `rn_year`, `year_in_school`, `year_in_network`, `is_enrolled_*` | same names                                                   | already computed                          |
| `students_dcid`, NJ state fields                                | none                                                         | null for Miami, by design                 |

**The governing rule for every translation is to reproduce the values Miami's
PowerSchool archive carried.** Every consumer was written against those, and
`base_powerschool__student_enrollments` already branches on `region = 'Miami'`
to pass Miami's own domain through for `spedlep`, `lunchstatus`, and
`lep_status`. Because Focus covers AY2018 through AY2026, each translation is
testable against the archive across eight overlapping years.

## Enrollment: history and alumni placeholders

No cutover date is needed. Focus carries Miami's real enrollment stints for
AY2018 through AY2026, matching the archive once alumni placeholders are
excluded.

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
   This is the only real test of the ESE, ELL, and meal translations.
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
- Confirm the Focus `ese_fefp_code` domain reconciles against the archive's
  `special_education_code` values for AY2018–2025 before finalizing that
  translation. If it does not, Miami SPED status needs a different source.
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
