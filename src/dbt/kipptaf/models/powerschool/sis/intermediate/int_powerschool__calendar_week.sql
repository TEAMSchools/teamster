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
select *, initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
from union_relations
