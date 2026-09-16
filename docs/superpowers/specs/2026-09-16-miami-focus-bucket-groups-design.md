# Miami student buckets from Focus custom student groups

Design for [#5344](https://github.com/TEAMSchools/teamster/issues/5344).
Companion to the goal-setting generator design in
TEAMSchools/academic-goal-setting (`docs/spec.md`, "Miami bucket store"
amendment). Origin:
[#5335](https://github.com/TEAMSchools/teamster/issues/5335). Supersedes the
frozen-buckets sheet tab design drafted earlier the same day, after the Focus
`student_groups` review (`.claude/scratch/focus-student-groups-handoff.md`)
showed that custom groups persist membership and are already ingested.

## Problem

Student buckets reach every dashboard through
`int_extracts__student_enrollments_subjects.nj_student_tier`, which reads
PowerSchool special programs named `Bucket N - Subject`. Miami moved to Focus
and no longer writes PowerSchool programs, so Miami's SY27 buckets have no
warehouse-readable store.

Focus has student groups. Dynamic groups resolve membership from a saved search
the warehouse does not ingest, so their membership rows are unusable. Custom
groups are hand-assigned and their membership does persist in
`students_join_groups`. Both tables are ingested every 15 minutes through the
Focus dlt intraday sensor and staged as `stg_focus__student_groups` and
`stg_focus__students_join_groups` in `kippmiami_focus`, but nothing downstream
reads them.

Miami created six custom groups on 2026-09-16: `Bucket 1 - ELA` (id 76),
`Bucket 1 - Math` (77), `Bucket 2 - ELA` (78), `Bucket 2 - Math` (79),
`Bucket 3 - ELA` (80), `Bucket 3 - Math` (81). Bucket 4 has no group, matching
the PowerSchool convention.

Separately, Miami's SY26 buckets disappeared from the network union when the
Focus cutover dropped the Miami relation from `int_powerschool__spenrollments`
([#5341](https://github.com/TEAMSchools/teamster/issues/5341)). That issue stays
open on its own and is not a dependency here.

## Decision

Read Miami buckets from Focus custom group membership, keyed by the group title,
as a second source behind PowerSchool in the enrollments model. Membership is
loaded by the data team through Focus's mass-assign UI from a per-group student
id list the generator writes. No sheet tab, no new store.

Rejected: a frozen-buckets sheet tab (a second store to explain, and Focus now
works); dynamic groups (membership not ingested); a region switch in the
enrollments model (a coalesce does the same with no literal).

## Design

### Sources and wrappers

`src/dbt/kipptaf/models/focus/sources-kippmiami.yml` gains two entries under
`kippmiami_focus`: `stg_focus__student_groups` and
`stg_focus__students_join_groups`, with the dev and staging schema branch the
sibling entries carry. Each gets the standard kipptaf passthrough wrapper
(`select *` over `dbt_utils.union_relations` of the one region, producing
`_dbt_source_project`), named `stg_focus__student_groups` and
`stg_focus__students_join_groups` under `models/focus/staging/`, with
model-level `config.meta.contains_pii: true` on the membership wrapper since
`student_id` is the school-facing student number.

### Bucket membership CTE

In `int_extracts__student_enrollments_subjects`, a new CTE `bucket_groups` joins
the two wrappers:

- `student_groups.title like 'Bucket%'` and `assignment_type = 'custom'`.
- `bucket` is the text before `-` in the title; `discipline` the text after
  (`ELA`, `Math`), parsed exactly as the PowerSchool CTE parses `specprog_name`.
- `students_join_groups.syear` is the academic year (Focus start-year
  convention, 2026 = 2026-27).
- `students_join_groups.student_id` is the Miami student number as the roster
  carries it; the 8400 prefix is part of the number, not something to strip.

A `bucket_groups_dedupe` CTE keeps the latest `updated_at` per student, year,
and discipline, mirroring `bucket_dedupe`. The join to the roster is on
`co.student_number`, `co.academic_year`, and `sj.discipline`, plus
`co.region = 'Miami'` is not needed: only Miami rows exist in the source.

`nj_student_tier` becomes:

```sql
coalesce(b.bucket, bg.bucket, 'Bucket 4') as nj_student_tier
```

where `b` is the PowerSchool bucket and `bg` the Focus group bucket. New Jersey
resolves at the first term, Miami SY27 at the second, everything else at the
default. No consumer changes.

### Duplicate detection

A student in two bucket groups for one subject and year is a data error the
requester wants surfaced, not masked. The dedupe keeps the model building; a
singular test `test_focus_bucket_groups_one_per_student_subject_year.sql` at
`severity: warn` lists students with more than one custom `Bucket%` group per
subject and syear, so the data team sees it on the next build. The same check is
what `verify-load` in the generator will run from the terminal.

### Illuminate

The Illuminate programs feed keeps reading PowerSchool. Miami gets no Illuminate
bucket groups from this path; routing Miami through the Focus wrappers there is
a later change if Miami uses those groups.

### Tests on the enrollments model

The existing uniqueness test covers fan-out from the new join. A unit test
proves the coalesce with four cases:

1. A Miami student in a custom `Bucket 2 - Math` group for syear 2026 reads
   `Bucket 2` for Math in 2026.
2. A Miami student in no bucket group reads `Bucket 4`.
3. A Newark student with a PowerSchool program reads PowerSchool even if a Focus
   row exists for the same student number.
4. A Miami student in a dynamic group titled `Bucket 1 - ELA` reads `Bucket 4`,
   proving the `custom` filter.

The `nj_student_tier` description in the properties yml names both sources and
the precedence. The stale "all dynamic" description on
`stg_focus__student_groups` in the focus package is corrected in the same PR.

## Verification

- `uv run dbt build --select stg_focus__student_groups+ --project-dir src/dbt/kipptaf`
  against dev, after the kipptaf wrappers exist.
- The unit test above and the singular test.
- Before Miami's rollout: paste one group's id list into Focus, wait for the
  intraday sensor, and confirm `nj_student_tier` for those students matches the
  generator's `student_buckets.csv`. `verify-load` automates this later.

## Out of scope

- Restoring Miami SY26 buckets (#5341).
- Illuminate bucket groups for Miami.
- Dynamic group membership (needs saved-search ingestion).
- Any change to the New Jersey bucket path.
