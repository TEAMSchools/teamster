# Translate Paterson Pearson `localstudentidentifier` at the kipppaterson layer

Refs #3882.

## Problem

All 440 Paterson Pearson assessment rows in
`fct_assessment_scores_enrollment_scoped` resolve to the wrong `student_key`:

| Bucket                             |  n_rows |
| ---------------------------------- | ------: |
| Orphan (no PowerSchool match)      |       8 |
| Silently wrong-matched (FK passes) |     432 |
| Correctly resolved                 |       0 |
| **Total Paterson Pearson rows**    | **440** |

The `relationships` test catches only the 8 orphans. The 432 wrong-matches pass
the test today because Paterson Ops uses district SIS IDs in the `10000–10499`
range, which numerically coincide with valid KIPP Newark historical
`student_number`s. **100% of the wrong-matches FK into KIPP Newark** — none into
Camden or Miami.

## Root cause

The Paterson Pearson source data carries Paterson district SIS IDs in
`localstudentidentifier`, not canonical KIPP `student_number`s. The current
identity resolution in
`src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
is:

```sql
coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier
```

where `x` is `stg_google_sheets__pearson__student_crosswalk` (UUID → KIPP
`student_number`). The crosswalk has no Paterson entries, so every Paterson row
falls through to the raw `u.localstudentidentifier` (= Paterson district SIS
ID). Downstream surrogate-key resolution then hashes that district SIS ID as if
it were a KIPP `student_number`, producing collisions with Newark's 10xxx-range
historical records.

## The mapping is already in PowerSchool

Paterson's `stg_powerschool__studentcorefields.prevstudentid` carries the
district SIS ID for each Paterson PS record. 90% of Paterson PS records have
`prevstudentid` populated; values are distinct (one-to-one mapping). For all 432
Paterson Pearson wrong-match rows, `localstudentidentifier` matches exactly one
Paterson PS record via `prevstudentid`. The 8 orphans remain unresolved by any
model-side join (these students have no PS record — separate Ops concern).

## The crosswalk: out of scope, kept

`stg_google_sheets__pearson__student_crosswalk` has 61 entries (61 distinct
UUIDs, 22 distinct `student_number`s). All 61 fire on non-Paterson rows; 0 fire
on Paterson. A first pass concluded the crosswalk was vestigial, but a deeper
investigation (comparing `crosswalk.student_number` against the **raw**
`stg_pearson__*.localstudentidentifier`, not the already-coalesced
`int_pearson__all_assessments.localstudentidentifier`) showed it overrides 13
distinct localids (~28 Pearson rows): the raw Pearson `localstudentidentifier`
is a non-canonical state-ID-shaped value (e.g., `2792`, `701158700`, `15356600`)
and the crosswalk resolves the UUID to a valid KIPP `student_number` (e.g.,
`14005`, `203307`). Removing the crosswalk regresses these 28 rows into
`student_key` orphans against `dim_students`. The crosswalk stays. Architectural
cleanup (move these per-localid corrections into kippnewark / kippcamden
intermediates analogous to the Paterson pattern) belongs in a follow-up issue,
not Phase B.

## Design

Translate Paterson `localstudentidentifier` from district SIS ID to canonical
KIPP `student_number` **at the kipppaterson project layer**, via a
per-assessment intermediate model that joins the Paterson Pearson staging to
Paterson PS `prevstudentid`. The kipptaf-level union then sources from the
translated intermediates and never sees raw district SIS IDs.

```text
pearson package: stg_pearson__<assessment>  (raw, district-agnostic)
                          ↓ instantiated per-district
kipppaterson_pearson.stg_pearson__<assessment>  (raw Paterson)
                          ↓ NEW: kipppaterson intermediate translates IDs
kipppaterson.int_pearson__<assessment>
                          ↓ sourced by kipptaf
kipptaf.stg_pearson__<assessment>  (union of 3 districts)
                          ↓
int_pearson__all_assessments  (crosswalk join retained)
```

**Architectural rationale**: the asymmetry is structural to Paterson's
PowerSchool migration (district SIS IDs persisted in `prevstudentid` rather than
retired). It belongs in the kipppaterson project where the mapping data lives.
kipptaf stays single-purpose (cross-district aggregation). The pearson
source-system package stays district-agnostic.

## Implementation

### 1. kipppaterson intermediates (2 new models)

Add `src/dbt/kipppaterson/models/pearson/intermediate/`:

- `int_pearson__njsla.sql`
- `int_pearson__njsla_science.sql`

`stg_pearson__parcc` and `stg_pearson__njgpa` are disabled in
`kipppaterson/dbt_project.yml`, so no Paterson rows exist for those assessments
in the kipptaf union and no intermediate is needed.

Each model:

```sql
with
    raw as (select * from {{ ref("stg_pearson__<assessment>") }}),
    paterson_id_map as (
        select
            cast(scf.prevstudentid as string) as paterson_district_sis_id,
            cast(s.student_number as string) as kipp_student_number,
        from {{ ref("stg_powerschool__students") }} as s
        inner join {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
        where s.enroll_status in (0, 2, 3)
          and scf.prevstudentid is not null
    )

select
    /* pass through every column except localstudentidentifier */
    raw.* except (localstudentidentifier),

    coalesce(
        m.kipp_student_number, raw.localstudentidentifier
    ) as localstudentidentifier,
from raw
left join paterson_id_map as m
    on raw.localstudentidentifier = m.paterson_district_sis_id
```

Each gets a properties yml requiring `unique_combination_of_columns` matching
the upstream staging model's uniqueness grain.

The `enroll_status IN (0, 2, 3)` filter follows the kipptaf CLAUDE.md
"`enroll_status = 1` is invalid" rule (active / withdrawn / graduated only).

### 2. Update kipptaf `sources-kipppaterson.yml`

Declare the 2 new intermediates as sources alongside the existing per-assessment
staging models. The kipptaf-level `stg_pearson__<assessment>` union models then
source the translated intermediates for Paterson.

### 3. Update kipptaf `stg_pearson__<assessment>.sql` (2 union models)

For `stg_pearson__njsla.sql` and `stg_pearson__njsla_science.sql` in
`src/dbt/kipptaf/models/pearson/staging/`, replace:

```sql
source("kipppaterson_pearson", "stg_pearson__<assessment>")
```

with:

```sql
source("kipppaterson_pearson", "int_pearson__<assessment>")
```

Newark / Camden sources stay unchanged.

### 4. Crosswalk: keep as-is

The crosswalk overrides 13 distinct localids (~28 Pearson rows). Initial
analysis missed those overrides (see "The crosswalk: out of scope, kept" above).
Removing it now would regress those rows into `dim_students` orphans. Leave the
`LEFT JOIN` to `stg_google_sheets__pearson__student_crosswalk` in
`int_pearson__all_assessments` intact. File a follow-up issue to move the
per-localid corrections to kippnewark / kippcamden intermediates analogous to
the Paterson pattern; then the crosswalk can be retired.

## Acceptance criteria

- [ ] 2 new `int_pearson__<assessment>` models exist in kipppaterson (NJSLA +
      NJSLA Science) with passing uniqueness tests.
- [ ] The 2 kipptaf-level `stg_pearson__njsla` / `stg_pearson__njsla_science`
      union models source the translated intermediates for Paterson.
- [ ] Crosswalk join and source declarations remain in place (regression scope
      avoided; cleanup deferred to a follow-up issue).
- [ ] 432 Paterson Pearson rows that previously FKed into Newark `student_key`s
      now FK into Paterson `student_key`s.
- [ ] 8 Paterson Pearson orphans remain orphans (relationships test continues to
      flag them — surfaces are tracked in a separate Ops issue, not blocking
      this PR).
- [ ] Newark and Camden Pearson row counts unchanged.
- [ ] Newark and Camden `student_key` resolution unchanged (verify via pre-merge
      diff query).

## Pre-merge verification

Run against PR-branch CI schema and prod (substitute `<ci_schema>` for the dbt
Cloud CI schema name per the kipptaf CLAUDE.md):

### Confirm Paterson now resolves into Paterson PS

```sql
select
    regexp_extract(_dbt_source_relation, r'`(kipp[^_]+)_powerschool`')
      as resolved_district,
    count(*) as n_rows,
from `teamster-332318.<ci_schema>.int_pearson__all_assessments` as p
left join `teamster-332318.kipptaf_powerschool.stg_powerschool__students` as s
    on cast(s.student_number as string) = p.localstudentidentifier
where p._dbt_source_relation like '%paterson%'
group by resolved_district;
```

Expected: `kipppaterson` row count = 432, NULL row count = 8 (orphans),
`kippnewark` / `kippcamden` / `kippmiami` rows = 0.

### Confirm Newark / Camden unchanged

```sql
select
    p._dbt_source_relation,
    count(*) as n_rows,
    countif(p.localstudentidentifier != prev.localstudentidentifier) as n_changed,
from `teamster-332318.<ci_schema>.int_pearson__all_assessments` as p
inner join `teamster-332318.kipptaf_pearson.int_pearson__all_assessments` as prev
    on p.studenttestuuid = prev.studenttestuuid
where p._dbt_source_relation not like '%paterson%'
group by p._dbt_source_relation;
```

Expected: `n_changed = 0` for both Newark and Camden source relations.

## What this spec does NOT do

- **Does not consolidate duplicate `student_key`s in `dim_students`** for the 37
  same-person PS-merge-workaround cases (#3955). The state-ID collisions remain
  in dim_students; each duplicate gets its own `student_key`. The Paterson fix
  is unaffected by those (Paterson cases don't overlap the 37).
- **Does not add `_dbt_source_project` to the `student_key` hash** for
  defense-in-depth against future cross-district SIS-namespace overlap. That's a
  separate marts hardening question, intentionally deferred.
- **Does not fix the 8 Paterson orphans** — they need Ops action (either add the
  student to Paterson PS with `prevstudentid` populated, or determine that the
  rows shouldn't exist). Tracked in
  [#3956](https://github.com/TEAMSchools/teamster/issues/3956).
- **Does not correct ~6 silent wrong-matches in non-Paterson Pearson** that were
  surfaced during investigation. Those are different mechanism (state-ID
  collisions per #3954 / dirty data per #3955) and not in scope.

## Related issues

- [#3882](https://github.com/TEAMSchools/teamster/issues/3882) — this fix
- [#3953](https://github.com/TEAMSchools/teamster/issues/3953) — `_dupe`
  enroll_status sync (Ops)
- [#3954](https://github.com/TEAMSchools/teamster/issues/3954) —
  `state_studentnumber` collisions (Ops)
- [#3955](https://github.com/TEAMSchools/teamster/issues/3955) — duplicate
  student records for the same human (Ops decision blocking marts identity
  consolidation)
- [#3956](https://github.com/TEAMSchools/teamster/issues/3956) — 8 Paterson
  Pearson rows with no PowerSchool record (Ops follow-up)
- [#3957](https://github.com/TEAMSchools/teamster/issues/3957) — proactive dbt
  tests to surface state_studentnumber collisions going forward
