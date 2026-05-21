{{
    config(
        meta={
            "dagster": {
                "ref": {
                    "name": "dim_student_meal_eligibility_status",
                    "package": "kipptaf",
                },
            }
        }
    )
}}

with
    spans as (
        select
            student_key,
            effective_date_start_key,
            effective_date_end_key,
            lead(effective_date_start_key) over (
                partition by student_key order by effective_date_start_key
            ) as next_start,
        from {{ ref("dim_student_meal_eligibility_status") }}
    )

select student_key, effective_date_start_key, effective_date_end_key, next_start,
from spans
where next_start is not null and next_start <= effective_date_end_key
