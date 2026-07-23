with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippcamden_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippmiami_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kipppaterson_deanslist",
                        "int_deanslist__incidents__penalties",
                    ),
                ]
            )
        }}
    ),

    sanitized as (
        -- trunk-ignore(sqlfluff/AM04): union_relations expands at compile time
        select
            * except (start_date, end_date),

            if(start_date < date '2000-01-01', null, start_date) as start_date,
            if(end_date < date '2000-01-01', null, end_date) as end_date,
        from union_relations
    )

select *, {{ extract_source_project("sanitized") }} as _dbt_source_project,
from sanitized
