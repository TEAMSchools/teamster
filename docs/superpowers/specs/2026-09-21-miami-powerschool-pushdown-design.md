# Push Miami PowerSchool derivations down into the package

Refs [#5413](https://github.com/TEAMSchools/teamster/issues/5413)

## The rule this design applies

All Miami PowerSchool data should arrive in `kipptaf` pre-computed. `kipptaf`
should carry no join or calculation that the `powerschool` dbt project could
have done first.

This is a design rule, not a performance target. #5413 framed the same models as
a cost problem and ranked them by Miami row share. That ranking is wrong — prod
slot time is driven by view-versus-table materialization, and
`int_students__attendance_daily`, the issue's headline item, is the cheapest of
the three it names. The re-scope keeps the issue's model list and replaces its
reasoning.

**The test.** A derivation is pushable only when every one of its inputs is
frozen. Miami's PowerSchool data stops at AY2025 and lives in the
`kippmiami_powerschool` archive, so a value computed from archive columns alone
can be computed once, at bake time. A value that also reads live data cannot,
because the live side keeps changing after the bake.

## Context

Miami's SIS moved from PowerSchool to Focus. `kippmiami_powerschool` is a
BigQuery-native archive of 14 tables built from the frozen `src_powerschool__*`
externals, final ODBC pull 2026-07-01. `kipptaf` reads it as a source and unions
it with the 3 live NJ districts through `dbt_utils.union_relations`. The archive
has been rebuilt 4 times against a documented recipe in
`src/dbt/kippmiami/CLAUDE.md`, and #5260 proved the recipe absorbs a brand-new
model.

## Audit result

**The 14 archive wrappers.** 11 are pure unions, exactly as #5413 claimed. The
12th, `int_powerschool__calendar_week`, derives `region` from
`_dbt_source_relation`, which the union itself creates, so it is structurally
unpushable. `stg_powerschool__storedgrades` carries 2 derivations and
`int_powerschool__gpa_cumulative` carries the KTAF GPA bands.

**Downstream of the wrappers.** #5413 stopped at the wrapper layer. 3 of the 8
SIS-neutral conform models fail the test, and one of them is larger than
anything at the wrapper layer: `int_students__gpa` joins
`int_powerschool__gpa_term` to `int_powerschool__gpa_cumulative`, and for Miami
both sides are frozen archive tables. Nothing live participates.

## Changes to the `powerschool` package

1. Add `agg_credittype` to `stg_powerschool__storedgrades`. It buckets
   `credit_type` by prefix into `ENG` / `MATH` / `SCI` / `SOC`, row-local over
   one frozen column.
2. Add a new `int_powerschool__gpa` model holding the term-to-cumulative join.
   It joins the package's own `int_powerschool__gpa_term` to the package's
   `int_powerschool__gpa_cumulative` on `studentid` and `schoolid`, and carries
   the `academic_year` that change 4 adds.
3. Add `is_in_session` (`insession = 1`) and `is_in_membership`
   (`membershipvalue > 0`) to `int_powerschool__calendar_day`.
4. Add `academic_year` to `int_powerschool__gpa_term` and
   `int_powerschool__attendance_streak`.

**Edit all 3 staging variants.** `agg_credittype` goes in `staging/dlt/`,
`staging/odbc/` and `staging/sftp/`. The archive bakes through the ODBC variant
while the 3 NJ districts run on dlt, so a column added to dlt alone reaches NJ
and silently misses Miami. `sftp/` is `+enabled: false` and no district uses it,
but all 3 variants share one contract-enforced properties file, so a column
declared there must be produced by every variant or that variant's build fails.

**Do not widen `int_powerschool__gpa_term` instead of adding
`int_powerschool__gpa`.** Widening is the smaller diff and it is wrong.
`int_powerschool__gpa_term` feeds `int_powerschool__gpa_term_current`, which
feeds `snapshot_powerschool__gpa_term`. A snapshot on the `check` strategy
backfills only the rows it touches, so added columns sit about 99% null. The
model also has roughly 19 other consumers.

**`academic_year` is a consistency fix, not a new pattern.**
`int_powerschool__ada`, `int_powerschool__calendar_week`,
`base_powerschool__final_grades` and `int_powerschool__terms` already carry both
`yearid` and `academic_year`. `int_powerschool__gpa_term` and
`int_powerschool__attendance_streak` carry `yearid` only.

## Changes to `kipptaf`

1. Add an `int_powerschool__gpa` union wrapper and a `sources-kippmiami.yml`
   entry for it. The archive grows from 14 tables to 15. The new wrapper is
   additive: the `int_powerschool__gpa_term` and
   `int_powerschool__gpa_cumulative` wrappers both stay, because other models
   read them directly and `int_powerschool__gpa_cumulative` still holds the KTAF
   bands until #5462 moves them.
2. Rewrite `int_students__gpa` to read the new wrapper instead of joining the
   two GPA models itself, and to read `academic_year` instead of computing
   `yearid + 1990`.
3. Rewrite `int_students__calendar_day` to read the `academic_year` and the 2
   booleans that now arrive on `int_powerschool__calendar_day`.
4. Rewrite `int_students__attendance_streak` to read `academic_year`.
5. Drop `agg_credittype` from the `stg_powerschool__storedgrades` wrapper.
6. Strip the stale detail from the `date_key` description on
   `dim_school_calendars`.

**`int_students__calendar_day` already ignores a column it has.**
`int_powerschool__calendar_day` carries `academic_year` today, and it equals
`yearid + 1990` on all 126,319 rows with a non-null `yearid`, across all 4
districts, with zero disagreements. The model recomputes a value it could read.
That one is free: no package change and no re-bake.

## What does not change

**`int_students__attendance_daily` passes the test.** Its PowerSchool arm joins
the frozen archive to `focus_stints`, drawn from
`int_students__student_enrollment_union` filtered to Miami. Focus is the live
SIS, so the join result changes as Focus data arrives and the value cannot be
frozen.

**`is_transfer_grade` passes the test.** It reads a LEFT JOIN to
`int_people__location_crosswalk`, a live `kipptaf` view. Its sibling
`agg_credittype` sits in the same model and is pushable; only one of the two
moves.

**The KTAF GPA bands stay out of the package.** The cut-offs are network policy,
documented in `src/dbt/kipptaf/models/students/CLAUDE.md` next to the separate
KIPP Foundation 5-band scale. 3 other district projects import the `powerschool`
package and must not inherit a KTAF policy rule.

The bands are nonetheless in the wrong `kipptaf` model. They sit in
`int_powerschool__gpa_cumulative`, a PowerSchool namespace, so Miami's Focus-era
students reach them through a join that matches nothing, and 2 flags on
`int_extracts__student_enrollments` report `false` for every Miami high
schooler. That is [#5462](https://github.com/TEAMSchools/teamster/issues/5462)
and it stays out of this change: it has a different driver, it needs no re-bake,
and it alters prod values in a model that feeds outbound extracts.

**The pre-2000 filter is deleted, not pushed down.**
`int_students__calendar_day` drops rows before 2000-01-01. The filter removes
exactly 3 rows network-wide — 1 Camden and 2 Newark, and **0** Miami — so it was
never a Miami pushdown item. All 3 are PowerSchool's missing-date placeholder:
`date_value` 1900-01-01, `yearid` null, `insession` 0, `membershipvalue` 0, at 3
real high schools. The rows exist unchanged in the raw external, so the fix
belongs in the SIS.

Deleting the filter makes the `relationships` test on
`dim_school_calendars.date_key` warn at 3 rows until school ops deletes the
records in PowerSchool. That is the intent — the workaround hides a real source
error. All 5 dbt projects already default to `+severity: warn` with
`+store_failures_as: view`, so this needs no severity change and the failing
rows land in a view. The ops request is tracked in Asana, and it says to delete
the records rather than re-date them: re-dating one onto an existing school day
collides with the `(date_key, location_key)` key.

## Sequencing

One change, one re-bake. The archive re-bake is the expensive step and it has
absorbed a new model before, so splitting the work into risk waves buys two
bakes and no safety.

1. Package changes, all 4 at once.
2. Miami archive re-bake, per the `src/dbt/kippmiami/CLAUDE.md` recipe. It adds
   `int_powerschool__gpa` as the 15th table and rebuilds the 4 tables that
   change 1, 3 and 4 widen.
3. `kipptaf` changes.

## Traps

- **`dbt_utils.union_relations` resolves at compile time** from the source
  relations' `INFORMATION_SCHEMA`. A new package column does not appear at a
  `kipptaf` wrapper until the district projects rebuild prod. Follow the
  cross-project column-change procedure in `.claude/rules/dbt-models.md`, which
  ships district first and `kipptaf` second, or use the single-PR pattern it
  points at.
- **The archive bakes through ODBC.** See all-3-variants above.
- **A properties-yml-only change does not bump the dagster-dbt code version**,
  which is derived from the SQL checksum.

## Verification

For each model this change touches, compare the rebuilt relation to prod on
`count(*)` and on `count(distinct format("%T|%T", <key cols>))`, plus a
column-level equality check on the moved derivations. The refactor is
value-preserving by construction, so any difference is a defect rather than an
expected delta. The 2 deliberate exceptions are the 3 rows the deleted filter
stops removing, and the 3 new orphans they create on
`dim_school_calendars.date_key`.
