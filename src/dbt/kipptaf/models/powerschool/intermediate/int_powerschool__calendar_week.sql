with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__calendar_week"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__calendar_week"
                    ),
                    source("kippmiami_powerschool", "int_powerschool__calendar_week"),
                    source(
                        "kipppaterson_powerschool", "int_powerschool__calendar_week"
                    ),
                ]
            )
        }}
    )

select
    *,
    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
    {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
