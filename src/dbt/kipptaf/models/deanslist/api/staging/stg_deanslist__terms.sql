with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__terms"),
                    source("kippcamden_deanslist", "stg_deanslist__terms"),
                    source("kippmiami_deanslist", "stg_deanslist__terms"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (start_date_date, end_date_date),

    start_date_date as start_date_datetime,
    end_date_date as end_date_datetime,

    cast(start_date_date as date) as start_date_date,
    cast(end_date_date as date) as end_date_date,

    safe_cast(left(academic_year_name, 4) as int) as academic_year,
from union_relations
