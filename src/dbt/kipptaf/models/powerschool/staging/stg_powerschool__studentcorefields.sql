with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kippcamden_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kippmiami_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "stg_powerschool__studentcorefields",
                    ),
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
