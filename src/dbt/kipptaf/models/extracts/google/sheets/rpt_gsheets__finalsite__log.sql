with
    ranked as (
        select
            enrollment_academic_year_display,
            region,
            assigned_school,
            finalsite_enrollment_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            enrollment_type,
            gender,
            birthdate,
            status_start_date,
            detailed_status,

            row_number() over (
                partition by finalsite_enrollment_id
                order by status_start_date desc, status_order desc
            ) as rn,

        from {{ ref("int_finalsite__status_report_unpivot") }}
        where
            status_start_date is not null
            and enrollment_academic_year = {{ var("current_academic_year") }}
    )

select
    enrollment_academic_year_display,
    region,
    assigned_school,
    finalsite_enrollment_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    enrollment_type,
    gender,
    birthdate,
    status_start_date,
    detailed_status,
from ranked
where rn = 1
