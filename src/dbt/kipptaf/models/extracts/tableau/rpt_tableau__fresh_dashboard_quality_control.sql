with
    finalsite_data as (
        select
            _dbt_source_relation,
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            latest_region,
            schoolid,
            latest_schoolid,
            school,
            latest_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,

            detailed_status,
            status_start_date,
            status_end_date,
            days_in_status,

        from {{ ref("int_finalsite__status_report") }}
        where rn = 1
    )

select *,
from finalsite_data
