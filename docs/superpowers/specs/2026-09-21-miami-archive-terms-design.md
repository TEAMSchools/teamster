# Miami archive terms and the PowerSchool terms spine

Design for [#5397](https://github.com/TEAMSchools/teamster/issues/5397).

## Problem

`int_students__terms` carries no Miami quarters before AY2025, so 492,482 Miami
membership days in `int_students__attendance_daily` have a null `term` and
`semester` — 26% of the 1,864,931 days PR #5396 recovered network-wide.

Miami's frozen PowerSchool archive holds the missing quarters, but the archive
is not wired into `int_students__terms` at all. The kipptaf source wrappers
`stg_powerschool__terms` and `int_powerschool__terms` union the three NJ
districts only, and both carry a header comment asserting Miami is absent on
purpose because Focus covers the whole archive range. That assertion is false.

## What changed in the diagnosis

The issue named three decisions. Two dissolved and one moved.

1. **Where the Focus-over-archive precedence rule lives.** No precedence rule is
   needed. Focus has no attendance or grades before AY2026, which is why
   `int_students__calendar_day` already floors its Focus arm on the cutover
   year. Flooring the Focus terms arm the same way makes the two arms disjoint
   by year, so there is nothing to reconcile.
2. **Order of wiring vs archive rebuild.** The 16 quarters the archive is
   missing come from #5396's fallback logic, which is code, not data. A plain
   rebuild against the existing frozen externals produces them. No PowerSchool
   server and no sync are needed for the wiring.
3. **The 511 residual days.** Corrected at source on the PowerSchool server,
   followed by a final sync. No code comment, no workaround.

A fourth question arrived during design: the PowerSchool conform logic sitting
in `int_students__terms` should be pushed down into the `powerschool` package,
and the full join it centres on should be removed if possible.

## Verified facts

All measured against prod on 2026-09-21.

### The Focus arm fabricates history

Pre-AY2026 Miami rows exist only for schoolids 30200801 through 30200804, in
both `int_students__attendance_daily` and `int_students__enrollment_daily`.
Schoolid 30200805 carries a full 7-row Focus term set in every year from AY2018
with zero attendance and zero enrollment behind it. The existing `syear >= 2018`
floor was never sufficient; those rows are fabricated.

The SIS cutover year is 2026, and it is permanent — the cutover already
happened, so the year is a historical fact, not a parameter. Flooring the Focus
arm there orphans nothing: every Focus grades and attendance model reads
`stg_focus__marking_periods` directly, never through `int_students__terms`, so
the 321 pre-2018 report card grade rows keep resolving.

### The null days decompose exactly

| Schoolids          | Cause                                             | Days        |
| ------------------ | ------------------------------------------------- | ----------- |
| 30200801, 30200802 | No Focus quarter row at all                       | 442,576     |
| 30200803, 30200804 | Focus quarters narrower than the archive calendar | 49,906      |
|                    | **Total**                                         | **492,482** |

Matches the issue's figure.

### The full join is a union wearing a join's clothes

`int_students__terms` full-joins the raw terms rows against the derived quarter
list on `(schoolid, yearid, abbreviation = term)`. Its stated purpose is
preserving 86 "orphan" quarters that exist via `termbins` with no raw `Q1`-`Q4`
row.

No consumer reads a merged row. All eight pick one side:

| Consumer                                        | Side                                 | Selector                                      |
| ----------------------------------------------- | ------------------------------------ | --------------------------------------------- |
| `int_students__attendance_daily`                | quarter                              | `term is not null`                            |
| `int_students__enrollment_daily`                | quarter                              | `term is not null`                            |
| `int_extracts__course_enrollments_by_term`      | quarter                              | `term is not null`                            |
| `int_extracts__course_schedule_by_term`         | quarter                              | `term is not null`                            |
| `int_tableau__gradebook_audit_teacher_scaffold` | quarter                              | joins on `t.term`                             |
| `int_extracts__student_enrollments_subjects`    | raw                                  | `abbreviation`, `name`, `firstday`, `lastday` |
| `rpt_illuminate__terms`                         | raw                                  | `name is not null`                            |
| `rpt_tableau__gradebook_gpa`                    | both, in two separate union branches | `term is not null` / `isyearrec = 1`          |

Five read zero raw-side columns. `rpt_tableau__gradebook_gpa` touches both
halves but never on one row.

Value-level equivalence against prod:

| Check                                                             | Result                                                 |
| ----------------------------------------------------------------- | ------------------------------------------------------ |
| Quarter rows in the full join vs `int_powerschool__terms`         | 926 = 926, symmetric difference 0 over 9 columns       |
| Raw rows in the full join vs `stg_powerschool__terms` at `rn = 1` | 1,925 = 1,925, symmetric difference 0 over 15 columns  |
| Rows where the full join MERGES a raw record with its quarter     | 840 -- kippnewark 548, kippcamden 276, kipppaterson 16 |

The two shapes carry the same VALUES but not the same ROWS. Where a raw Q1-Q4
record's `abbreviation` matches a quarter's `term`, the full join collapses the
pair into one row carrying both halves; a `union all` emits two. NJ output
therefore grows from 2,011 rows to 2,851.

That is safe, on two measurements. Both uniqueness keys hold over the full
branch sets rather than only the subsets they are tested on today -- 0 duplicate
keys on `(schoolid, yearid, abbreviation)` across all 1,925 raw rows, and 0 on
`(schoolid, yearid, term)` across all 926 quarter rows. And no consumer reads a
merged row's two halves together or changes cardinality when one row becomes
two: of 9 consumers, 5 read quarter-side columns only, 2 read raw-side only, and
2 (`rpt_tableau__gradebook_gpa`, `rpt_tableau__student_course_grades`) read both
families but in separate single-sided `union all` branches. Nothing is lost
either -- the union is a strict superset of the full join's row set.

The 86 orphans also stop being a special case, because a union never attempts a
match.

### Date-based joining is worse, measured

Two alternatives to the `abbreviation = term` key were tested and rejected.

Date equality fails on 143 of 840 matched quarters (17%): 76 kippnewark, 61
kippcamden, 6 kipppaterson. The derived dates come from `termbins.date1` and
`date2`, the grade-storage window; the raw quarter row's `firstday` and
`lastday` are the scheduling window. The disagreement is exactly why
`int_powerschool__terms` prefers termbins.

Date containment fans out. Of 926 derived quarters, only 31 have a single
containing raw row; 260 have 2, 633 have 3, and 2 have 4. A `Q1` sits inside the
year record, inside `S1`, and inside its own raw row.

### The orphans are load-bearing

The 86 orphan rows are the only source of `term` and `semester` for **1,752,966
enrollment days** across 4 NJ schoolids. The counterfactual is in the same
table: schoolid 133570965 has no orphan quarter in AY2012-AY2014, and `term` is
null on all 363,537 of those days.

The existing join comment calls these schoolids "non-instructional". That is
wrong — they carry millions of enrollment and attendance days. Zero attendance
days fall in an orphan-quarter school-year, but enrollment days do.

### Wiring facts

- All four districts carry identical column sets and types for both
  `stg_powerschool__terms` and `int_powerschool__terms`, so the union superset
  does not widen and NJ output stays byte-identical.
- Miami is singleton on `(schoolid, yearid, abbreviation)`: 193 rows, 193
  distinct keys, so the `rn = 1` guard drops nothing there. It drops nothing in
  NJ either — all 1,925 keys are singletons. The guard stays defensive-only, and
  moves to the package per-district, so the kipptaf wrapper's network-wide count
  comment does not carry forward.
- No junk-schoolid filter is needed. NJ already carries schoolid 0 (Newark 64,
  Camden 66, Paterson 15) and 999999 (Newark 28, Camden 28).
- The frozen archive `int_powerschool__terms` has 72 rows and is missing 16
  quarters: 30200801 in AY2018, AY2019 and AY2023, and 30200802 in AY2023.
- The Miami archive dataset already holds `stg_powerschool__terms`,
  `stg_powerschool__termbins` and `int_powerschool__terms` as real relations.
  They were only ever missing from the kipptaf source list.
- kipptaf's `stg_powerschool__terms` and `int_powerschool__terms` wrappers have
  exactly one consumer each, `int_students__terms`. Nothing in Cube, no
  exposures.
- The package's `int_powerschool__terms` has one package consumer,
  `int_powerschool__student_course_grades_spine`, at quarter grain.

## Design

### 1. New package model `int_powerschool__terms_spine`

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql`

Full-grain term spine for one district. Two `union all` branches, no join:

- **Raw branch** — `stg_powerschool__terms` filtered to `rn = 1`, where `rn` is
  a `row_number()` over `(schoolid, yearid, abbreviation)` ordered by `id`.
  Quarter columns are typed nulls.
- **Quarter branch** — `int_powerschool__terms` as-is. Raw columns are typed
  nulls.

The `rn` window moves here from the kipptaf wrapper. Being per-district, the
partition drops `_dbt_source_project`, and every `coalesce` across the two sides
of the old full join disappears — each branch supplies its own keys.

`int_powerschool__terms` is not modified, so
`int_powerschool__student_course_grades_spine` is untouched. That is why this is
a new model rather than a widening of the existing one.

Columns follow the positional-union rule: enumerate both branches column for
column with `cast(null as <type>)` where a branch has no equivalent. No
`select *`, no `full union all corresponding`.

### 2. kipptaf union wrapper `int_powerschool__terms_spine`

`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql`
plus its properties yml. A `dbt_utils.union_relations` passthrough over four
districts — the three NJ regions and `kippmiami_powerschool` — with
`extract_source_project()` supplying `_dbt_source_project`.

### 3. `sources-kippmiami.yml`

Add one table entry, `int_powerschool__terms_spine`, following the existing
`config.meta.dagster.{group, asset_key}` block shape. The source description
currently claims terms are "deliberately absent" because Focus covers the whole
archive range; rewrite it to state that the archive supplies Miami terms before
the cutover year and Focus supplies them from the cutover year on.

### 4. `int_students__terms` collapses

From 257 lines to roughly 90. The PowerSchool arm becomes a projection of the
new spine wrapper. The Focus arm keeps its conform but changes its floor from
`mp.syear >= 2018` to the cutover year:

```sql
where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2026
```

The literal is deliberate. `int_students__calendar_day` reads the same year from
`int_students__sis_cutover`, which derives it from the first Focus academic year
with recorded attendance — so a Focus backfill reaching further back would move
it. The cutover is done and 2026 will not change, so this model states the year
instead of deriving it, and takes on no dependency on the cutover model.

The existing note about 321 report card grade rows stays — it explains why both
filters live here rather than in staging, and that reasoning is unchanged.

Deleted: `powerschool_quarters`, `powerschool_canonical`, `powerschool_joined`,
the full join, and its comment.

### 5. Retire the two kipptaf wrappers

Both lose their only consumer.

- `int_powerschool__terms` — a bare `select *` union passthrough over district
  sources with no remaining `ref()`. The #5162 exception in
  `.claude/rules/dbt-models.md` applies: delete outright, source entries
  included.
- `stg_powerschool__terms` — the `rn` window goes too, at cbini's direction, so
  this is a bare passthrough as well and gets the same delete. The window's
  stated purpose is to keep a duplicate raw record from fanning out across the
  quarter-grain full join, and change 4 removes that join. The signal moves
  upstream instead: the `powerschool` package's `stg_powerschool__terms` carries
  a warn-severity `dbt_utils.unique_combination_of_columns` on
  `(schoolid, yearid, abbreviation)`, so a duplicate surfaces to ops rather than
  being absorbed silently. `severity: warn` departs from the staging-severity
  rule in `.claude/rules/dbt-yaml.md`, also at cbini's direction: PowerSchool
  does not enforce the key, no district violates it today, and
  `int_powerschool__terms_spine` still reduces to one row per key.

Both also carry the false Miami header comment, which goes with them.

### 6. `int_students__terms.yml`

The model description asserts "the frozen archive contributes no Miami rows" and
"the Focus branch is floored at Miami's first real enrollment year". The
`schoolid` column says "For Miami, resolved from Focus's internal school id";
`yearid` says "For Miami, no Focus source". All become wrong. Rewrite the
description and those column docs to describe the archive-before-cutover,
Focus-from-cutover split.

The `_dbt_source_relation` column doc describes taking "whichever side of the
full join supplied the row". Rewrite for the union.

Both uniqueness tests keep their current keys and `where` clauses. Under the
union the 840 matched quarters split into two rows, moving the raw half from the
`term is not null` test to the `term is null` test. Both still hold at one row
per key.

### 7. Miami archive rebuild

Per `src/dbt/kippmiami/CLAUDE.md`: re-include the `powerschool` package with the
ODBC variant plus the 16 post-hooks, rebuild, then remove the package again.
This produces one new relation, `int_powerschool__terms_spine`, and refreshes
`int_powerschool__terms` to pick up #5396's fallback — the 16 missing quarters,
worth 86,213 days.

No PowerSchool server, no dlt, no sync for this step.

### 8. Source correction and dlt revival

Independent of the wiring. The 511 residual days (all AY2018 at 30200801, a Q4
`lastday` that stops short of the archive's attendance calendar) are corrected
on the PowerSchool server by Ops, then pulled with a final sync.

Miami's PowerSchool Dagster stack was decommissioned in commit `6d07bb5081` on
2026-07-17 (refs #4441, #4442). Reviving it via dlt for that one sync costs:

- Parameterizing credentials. `get_powerschool_ssh_resource()` and
  `get_powerschool_oracle_resource()` in `src/teamster/core/resources.py` take
  no district argument — one credential set serves all three NJ regions.
- A staging-variant switch from ODBC (82 models, GCS Avro externals) to dlt (56
  models, BigQuery-native, schema `dagster_kippmiami_dlt_powerschool`),
  affecting all 14 kipptaf-facing archive relations.
- A Dagster+ pool, following the `dlt_powerschool_kippnewark` precedent at
  limit 1.

`src/teamster/code_locations/kippnewark/powerschool/sis/dlt/assets.py` is the
template; its `assets.yaml` already includes `terms` and `termbins`.

## Sequencing

The package model is consumed by kipptaf through `source()`, so the two-PR
cross-project rule in `.claude/rules/dbt-models.md` applies.

1. **PR A** — the package model (change 1). Merge, then wait for Dagster to
   materialize `int_powerschool__terms_spine` in all four district prod
   datasets. Miami's comes from the archive rebuild (change 7), which must
   complete before PR B.
2. **PR B** — everything in kipptaf: changes 2 through 6.
3. **Phase C** — changes 8, on its own timeline. May need its own issue.

`zz_stg_*` staging copies are not auto-refreshed by a district prod merge. PR B
needs the staged copies seeded per district before push, or CI's union-wrapper
rebuild will not see the new relation.

## Testing

- Both existing uniqueness tests on `int_students__terms`, unchanged.
- Row-count and value-level comparison of the PR-branch build against prod for
  every consumer-relevant projection: the quarter-side set and the raw-side set
  must each be unchanged for the three NJ regions.
- Miami: `term` and `semester` non-null on the 492,482 previously-null
  membership days, less the 511 awaiting the source fix.
- `uv run dbt build --select int_powerschool__terms_spine+` per district.

## Risks

- **Change 5 deletes both wrappers**, which the #5162 exception in
  `.claude/rules/dbt-models.md` permits but does not compel. Disabling both is
  the conservative alternative. The cost of being wrong is bounded: nothing in
  kipptaf reads either wrapper after change 4, and the district relations they
  read stay in place, so a forgotten consumer loses a view that held no logic.
- **The Focus floor move to 2026** is safe only because schoolids 30200805,
  30200806 and 30200807 carry zero pre-AY2026 attendance and enrollment days.
  Verified on prod; re-verify if the cutover value changes.
- **The 840-row split** means matched quarter rows no longer carry raw-side
  column values on the same row. Verified that no consumer reads them, but a new
  consumer could regress silently. The model description should say so.
- **Archive rebuild drift.** The archive has been rebuilt 4 times; confirm
  `packages.yml` is clean before and after.

## Out of scope

- Small-cell suppression, PII tagging. Terms are reference data.
- Any change to `int_powerschool__terms` itself, so
  `int_powerschool__student_course_grades_spine` stays untouched.
- Reviving Miami placeholder enrollment rows, decided against on 2026-08-14.
