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

## The crosswalk is vestigial

`stg_google_sheets__pearson__student_crosswalk` has 61 entries (61 distinct
UUIDs, 22 distinct `student_number`s). All 61 fire on non-Paterson rows; 0 fire
on Paterson. In every case the crosswalk's `student_number` equals the raw
`localstudentidentifier` — the coalesce is a no-op in current data. After this
spec ships the crosswalk would still resolve nothing, and Paterson is now
handled upstream of the union. Remove it.

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
int_pearson__all_assessments  (crosswalk join removed)
```

**Architectural rationale**: the asymmetry is structural to Paterson's
PowerSchool migration (district SIS IDs persisted in `prevstudentid` rather than
retired). It belongs in the kipppaterson project where the mapping data lives.
kipptaf stays single-purpose (cross-district aggregation). The pearson
source-system package stays district-agnostic.

## Implementation

### 1. kipppaterson intermediates (4 new models)

Add `src/dbt/kipppaterson/models/pearson/intermediate/`:

- `int_pearson__parcc.sql`
- `int_pearson__njsla.sql`
- `int_pearson__njsla_science.sql`
- `int_pearson__njgpa.sql`

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

Declare the 4 new intermediates as sources alongside the existing per-assessment
staging models. The kipptaf-level `stg_pearson__<assessment>` union models then
source the translated intermediates for Paterson.

### 3. Update kipptaf `stg_pearson__<assessment>.sql` (4 union models)

For each of the 4 assessment union models in
`src/dbt/kipptaf/models/pearson/staging/`, replace:

```sql
source("kipppaterson_pearson", "stg_pearson__<assessment>")
```

with:

```sql
source("kipppaterson_pearson", "int_pearson__<assessment>")
```

Newark / Camden sources stay unchanged.

### 4. Remove the vestigial crosswalk

In `int_pearson__all_assessments.sql`:

- Drop the `LEFT JOIN stg_google_sheets__pearson__student_crosswalk as x`
- Replace `coalesce(x.student_number, u.localstudentidentifier)` with
  `u.localstudentidentifier`

Disable the staging model and the upstream Google Sheet source:

- Set `config: enabled: false` on
  `stg_google_sheets__pearson__student_crosswalk` in its properties yml.
- Remove (or disable) the corresponding `pearson__student_crosswalk` entry in
  `src/dbt/kipptaf/models/google/sheets/sources-external.yml` so the Google
  Sheet external table is no longer registered as a source. With the staging
  model and the source both gone, the sheet has no entry points into the
  warehouse.

## Acceptance criteria

- [ ] 4 new `int_pearson__<assessment>` models exist in kipppaterson with
      passing uniqueness tests.
- [ ] All 4 kipptaf-level `stg_pearson__<assessment>` union models source the
      translated intermediates for Paterson.
- [ ] `int_pearson__all_assessments` no longer references the crosswalk.
- [ ] `stg_google_sheets__pearson__student_crosswalk` is disabled.
- [ ] `pearson__student_crosswalk` source entry removed (or disabled) in
      `sources-external.yml`.
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
