with
    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation=ref("base_powerschool__course_enrollments"),
                partition_by="courses_course_number, _dbt_source_relation",
                order_by="cc_academic_year desc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["courses_course_number", "_dbt_source_relation"]
        )
    }} as course_key,

    courses_course_number as course_number,
    courses_course_name as course_name,
    courses_credittype as credit_type,
    discipline,
    courses_credit_hours as credit_hours,

from deduplicated
