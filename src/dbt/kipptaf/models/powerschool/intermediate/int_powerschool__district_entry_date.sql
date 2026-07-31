with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__district_entry_date",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__district_entry_date",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__district_entry_date",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__district_entry_date",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
