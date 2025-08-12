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
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
    case
        when regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippcamden'
        then 'KIPP Cooper Norcross Academy'
        when regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippmiami'
        then 'KIPP Miami'
        when regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippnewark'
        then 'TEAM Academy Charter School'
        when regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kipppaterson'
        then 'KIPP Paterson'
    end as region_expanded,
from union_relations
