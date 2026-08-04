# i-Ready domain unpivot: add placement and scale_score

Issue: [#4706](https://github.com/TEAMSchools/teamster/issues/4706)

## Problem

`int_iready__domain_unpivot` unpivots only `relative_placement` per i-Ready
domain (14 domains) from `int_iready__diagnostic_results`. The upstream source
(`stg_iready__diagnostic_results`) carries two more parallel columns per domain
— `<domain>_placement` (string) and `<domain>_scale_score` (int64) — that aren't
yet available at the per-domain grain this model provides. A downstream Cube
mart update needs them.

## Change

### `int_iready__domain_unpivot.sql`

Replace the single-value `UNPIVOT` with a multi-column tuple `UNPIVOT`
(precedent: `int_collegeboard__ap_unpivot.sql`), pulling `placement`,
`relative_placement`, and `scale_score` together per domain in one pass, with an
explicit clean label per domain group instead of relying on the source column
name:

```sql
with
    domain_unpivot as (
        select
            _dbt_source_relation,
            student_id,
            `subject`,
            academic_year_int,
            `start_date`,
            completion_date,
            domain_name,
            placement,
            relative_placement,
            scale_score,
        from
            {{ ref("int_iready__diagnostic_results") }} unpivot (
                (placement, relative_placement, scale_score) for domain_name in (
                    (
                        phonics_placement,
                        phonics_relative_placement,
                        phonics_scale_score
                    ) as 'phonics',
                    (
                        algebra_and_algebraic_thinking_placement,
                        algebra_and_algebraic_thinking_relative_placement,
                        algebra_and_algebraic_thinking_scale_score
                    ) as 'algebra_and_algebraic_thinking',
                    -- ... remaining 12 domains, same (placement,
                    -- relative_placement, scale_score) as 'domain_slug' shape
                )
            )
    )

select
    student_id,
    `subject`,
    academic_year_int,
    `start_date`,
    completion_date,
    domain_name,
    placement,
    relative_placement,
    scale_score,

    row_number() over (
        partition by
            _dbt_source_relation,
            student_id,
            `subject`,
            academic_year_int,
            `start_date`,
            completion_date
        order by domain_name asc
    ) as rn_subject_test,
from domain_unpivot
```

All 14 domains present in the current single-value unpivot get the same
three-column tuple treatment. Grain (one row per domain per test administration)
and the `rn_subject_test` partition/order logic are unchanged.

`domain_name` changes from the current suffixed value (e.g.
`'phonics_relative_placement'`) to a clean slug (e.g. `'phonics'`), since the
multi-column tuple `UNPIVOT` takes an explicit label per group rather than
reusing the source column name.

### `properties/int_iready__domain_unpivot.yml`

Add column entries for `placement` (string) and `scale_score` (int64), with
descriptions, alongside the existing `relative_placement` entry.

### `rpt_tableau__miami_k2_iready.sql` (sole consumer)

Simplify the `domain_name` derivation. Current:

```sql
regexp_replace(
    left(up.domain_name, length(up.domain_name) - 19), '_', ' '
) as domain_name,
```

Becomes:

```sql
regexp_replace(up.domain_name, '_', ' ') as domain_name,
```

since `domain_name` is already the clean slug — no more suffix to trim.

This PR does **not** add `up.placement` / `up.scale_score` to this extract's
`SELECT` list. The intended near-term consumer of the new columns is a Cube mart
update, tracked separately.

## Out of scope

- No uniqueness/data test is being added to `int_iready__domain_unpivot` in this
  change (a pre-existing gap, not introduced or worsened here).
- No changes to `int_iready__diagnostic_results` or the staging layer — the
  source columns already exist as needed.
