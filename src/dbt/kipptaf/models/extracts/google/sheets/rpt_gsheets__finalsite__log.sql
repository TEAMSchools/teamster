with
    all_rows as (
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
            status_start_date,
            detailed_status,

            first_value(detailed_status) over (
                partition by finalsite_enrollment_id
                order by status_start_date desc, status_order desc
            ) as latest_status,

            max(status_start_date) over (
                partition by finalsite_enrollment_id
            ) as latest_status_date,

            count(*) over (
                partition by finalsite_enrollment_id, status_start_date
            ) as status_count_for_day,

        from {{ ref("int_finalsite__status_report_unpivot") }}
        where
            status_start_date is not null
            and enrollment_academic_year = {{ var("current_academic_year") }}
    )

select
    a.enrollment_academic_year_display,
    a.region,
    a.assigned_school,
    a.finalsite_enrollment_id,
    a.powerschool_student_number,
    a.first_name,
    a.last_name,
    a.grade_level,
    a.enrollment_type,
    a.status_start_date,
    a.detailed_status,
    a.latest_status,

from all_rows as a
where a.status_start_date = a.latest_status_date and a.status_count_for_day >= 2
