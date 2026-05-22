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

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
