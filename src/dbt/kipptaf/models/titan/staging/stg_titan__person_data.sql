with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_titan", "stg_titan__person_data"),
                    source("kippcamden_titan", "stg_titan__person_data"),
                ]
            )
        }}
    )

select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
