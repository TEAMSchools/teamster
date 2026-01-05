with
    transformations as (
        select
            finalsite_student_id,
            enrollment_year,
            enrollment_type,
            `status`,
            last_name,
            first_name,
            grade_level as grade_level_name,
            school,

            cast(powerschool_student_number as int) as powerschool_student_number,

            cast(`timestamp` as date) as status_start_date,

            cast(left(enrollment_year, 4) as int) as enrollment_academic_year,

            cast(left(enrollment_year, 4) as int) - 1 as academic_year,

            if(
                grade_level = 'Kindergarten', 'K', regexp_extract(grade_level, r'\d+')
            ) as grade_level_string,

            if(
                grade_level = 'Kindergarten',
                0,
                safe_cast(regexp_extract(grade_level, r'\d+') as int64)
            ) as grade_level,

        from {{ source("finalsite", "status_report") }}
    )

select
    *,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "academic_year",
                "last_name",
                "first_name",
                "grade_level",
                "school",
                "powerschool_student_number",
            ]
        )
    }} as surrogate_key,

from transformations
