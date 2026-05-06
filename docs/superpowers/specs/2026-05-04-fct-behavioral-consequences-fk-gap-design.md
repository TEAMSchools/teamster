# Design: align `behavioral_incident_key` hash inputs across `fct_behavioral_incidents` and `fct_behavioral_consequences`

Closes #3724. Makes incremental headway on #3142.

## Problem

The relationships test
`fct_behavioral_consequences.behavioral_incident_key → fct_behavioral_incidents.behavioral_incident_key`
fails on the entire population of `fct_behavioral_consequences`: 100% of
`behavioral_incident_key` values (212,694 / 212,694 distinct keys, 243,290 rows)
are orphans against the parent.

The issue body hypothesized a soft-delete / status-filter mismatch. That is
incorrect. Both facts ultimately consume `int_deanslist__incidents__penalties`
and `int_deanslist__incidents`, which both inherit the same
`stg_deanslist__incidents` `WHERE isactive` filter — there is no upstream filter
divergence to reconcile.

## Root cause

Both facts compute `behavioral_incident_key` as
`generate_surrogate_key([incident_id, _dbt_source_relation])`.

At the kipptaf layer, the two intermediate models are independent
`union_relations` views:

- [`int_deanslist__incidents.sql`](../../src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql)
- [`int_deanslist__incidents__penalties.sql`](../../src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql)

`dbt_utils.union_relations` injects `_dbt_source_relation` based on the source
table name. The two models therefore carry different relation strings for the
same logical incident:

| Model                                 | `_dbt_source_relation` value (Camden example)                       |
| ------------------------------------- | ------------------------------------------------------------------- |
| `int_deanslist__incidents`            | `` `…kippcamden_deanslist`.`int_deanslist__incidents` ``            |
| `int_deanslist__incidents__penalties` | `` `…kippcamden_deanslist`.`int_deanslist__incidents__penalties` `` |

`generate_surrogate_key` hashes these as plain strings, so the same
`(incident_id, region)` tuple produces two different `behavioral_incident_key`
values — one from the parent fact, one from the child — and 100% of children
fail the relationships test.

This is the same hash-drift class that PR #3793 closed for
`survey_submission_key` (parent issues #3766 / #3773).

## Fix: surface `_dbt_source_project` upstream, then hash on it

Rather than inline the regex in the marts, add the canonical
`_dbt_source_project` column to the two affected kipptaf union models — the same
column [#3142](https://github.com/TEAMSchools/teamster/issues/3142) is
introducing across all ~73 cross-district union models. This change is two of
those ~73 done, leaving #3142's broader refactor smaller by exactly that margin.

The full #3142 refactor (rename `extract_code_location` →
`extract_source_project`, replace all 268 `union_dataset_join_clause` call
sites, remove the macro, update CLAUDE.md) stays out of scope here.

### Step 1 — add `_dbt_source_project` to the two union models

Use the existing `extract_code_location` macro (renamed by #3142 later). Pattern
matches
[`int_powerschool__teacher_grade_levels.sql:23`](../../src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__teacher_grade_levels.sql#L23),
which already does this.

`src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    )

select
    u.*,
    {{ extract_code_location("u") }} as _dbt_source_project,
    loc.location_key,
from union_relations as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
```

`src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents__penalties"),
                    source("kippcamden_deanslist", "int_deanslist__incidents__penalties"),
                    source("kippmiami_deanslist", "int_deanslist__incidents__penalties"),
                ]
            )
        }}
    )

select
    *,
    {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
```

### Step 2 — properties YAML

Add `_dbt_source_project` (`data_type: string`) to the two intermediates'
properties YAML if/where the column list is enumerated. (These intermediates
inherit `dbt_utils.star()`-style columns from `union_relations`; the YAML
contract treatment matches whatever surrounding cross-district intermediates
already do.)

### Step 3 — facts

In both facts, hash on `[incident_id, _dbt_source_project]`. Producer and
consumer hash on identical inputs by construction.

`fct_behavioral_incidents.sql`:

```sql
select
    {{
        dbt_utils.generate_surrogate_key(
            ["i.incident_id", "i._dbt_source_project"]
        )
    }} as behavioral_incident_key,
    ...
from {{ ref("int_deanslist__incidents") }} as i
```

`fct_behavioral_consequences.sql`:

```sql
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "p.incident_id",
                "p.incident_penalty_id",
                "p._dbt_source_project",
            ]
        )
    }} as behavioral_consequence_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["p.incident_id", "p._dbt_source_project"]
        )
    }} as behavioral_incident_key,
    ...
from {{ ref("int_deanslist__incidents__penalties") }} as p
```

`behavioral_consequence_key` (the child fact's PK) gains `_dbt_source_project`
in its hash for consistency with the FK; this changes its hash too. Marts are
views, so no incremental concerns.

## Files touched

- `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`
- `src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__incidents.yml`
  (only if column list is enumerated there)
- `src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__incidents__penalties.yml`
  (only if column list is enumerated there)
- `src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql`
- `src/dbt/kipptaf/models/marts/facts/fct_behavioral_consequences.sql`

No CLAUDE.md changes — #3142 owns the convention rewrite. The fact-side YAML
column list, contracts, and tests stay unchanged.

## Out of scope

- The full #3142 refactor: macro rename, replacing 268
  `union_dataset_join_clause` call sites, removing the macro, deprecating
  `functions.region_join()`, rewriting `kipptaf/CLAUDE.md`. This change leaves
  all of that to #3142.
- Other surrogate keys on either fact (`student_enrollment_key`,
  `referring_staff_key`) — their inputs are unaffected.
- The other open fact-to-fact FKs registered in #3713
  (`family_communication_key`, `staff_observation_key`) — neither exhibits this
  hash-drift pattern (different root causes; verified during scan).
- Other open FK-orphan issues with different root causes (#3719 `dim_dates`
  range, #3709 Zendesk slug crosswalk, #3794 enrollment-coverage residual, #3799
  Illuminate catalog gaps).

## Hash churn

Per `src/dbt/CLAUDE.md` hash-change discipline, this is reason #1 (values
unify): two equivalent identifiers collapse to one canonical project code.

Hashes that change:

- `fct_behavioral_incidents.behavioral_incident_key`
- `fct_behavioral_consequences.behavioral_incident_key`
- `fct_behavioral_consequences.behavioral_consequence_key`

Marts are views (no incrementals). The FK is currently 100% broken so nothing
downstream is meaningfully relying on the existing `behavioral_incident_key`
hash. No exposures or extracts pin on these surrogate values.

## Verification

1. `relationships` test on
   `fct_behavioral_consequences.behavioral_incident_key → fct_behavioral_incidents.behavioral_incident_key`
   returns 0 failures in dbt Cloud CI.
2. Spot-check via BigQuery MCP on the PR-branch schema: a handful of
   `(incident_id, _dbt_source_project)` tuples produce identical
   `behavioral_incident_key` values in both facts; `_dbt_source_project` values
   are exactly `kippnewark` / `kippcamden` / `kippmiami`.
3. `dbt build --select int_deanslist__incidents+ int_deanslist__incidents__penalties+ --target staging`
   runs clean, including all downstream tests on both facts.

## Acceptance

- [ ] `_dbt_source_project` column exists on both `int_deanslist__incidents` and
      `int_deanslist__incidents__penalties`
- [ ] Both facts hash `behavioral_incident_key` on
      `[incident_id, _dbt_source_project]`
- [ ] `relationships` test on
      `fct_behavioral_consequences.behavioral_incident_key` passes in CI
- [ ] No other test regressions on either fact
- [ ] #3142 acceptance progresses by 2 of ~73 union models
