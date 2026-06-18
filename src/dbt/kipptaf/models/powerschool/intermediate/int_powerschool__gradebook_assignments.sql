with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

    -- flags
    if(
        category_code = 'W' and totalpointvalue != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        category_code = 'F' and totalpointvalue != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        category_code = 'H' and totalpointvalue != 10, true, false
    ) as h_assign_max_score_not_10,

from union_relations
