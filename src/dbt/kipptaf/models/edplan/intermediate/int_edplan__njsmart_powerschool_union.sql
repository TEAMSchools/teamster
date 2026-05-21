with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_edplan",
                        "int_edplan__njsmart_powerschool_union",
                    ),
                    source(
                        "kippcamden_edplan",
                        "int_edplan__njsmart_powerschool_union",
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
