with
    actual_enroll_year as (
        select
            * except (
                enrollment_year, enrollment_academic_year_display, status_end_date
            ),
            -- flawed because it only works when we only have 2 academic years at a time
            if(
                extract_year = 'Current_Year' and detailed_status = 'Enrolled',
                current_academic_year,
                null
            ) as actual_enrollment_academic_year,

        from {{ ref("stg_finalsite__status_report") }}
        -- limited to only 2 yrs as a temp workaround
        where enrollment_academic_year <= {{ var("current_academic_year") + 1 }}
    ),

    fill_in_actual_enroll_year as (
        select
            * except (actual_enrollment_academic_year),

            coalesce(
                max(actual_enrollment_academic_year) over (
                    partition by finalsite_student_id
                ),
                enrollment_academic_year
            ) as actual_enrollment_academic_year,

        from actual_enroll_year
    ),

    remove_not_in_workflow_rows as (
        select
            * except (enrollment_academic_year),

            {{ var("current_academic_year") + 1 }} as aligned_enrollment_academic_year,

            cast(actual_enrollment_academic_year as string)
            || '-'
            || right(
                cast(actual_enrollment_academic_year + 1 as string), 2
            ) as enrollment_academic_year_display,

            lead(
                status_start_date,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, actual_enrollment_academic_year
                order by status_start_date asc, status_order asc
            ) as status_end_date,

        from fill_in_actual_enroll_year
        where enrollment_academic_year = actual_enrollment_academic_year
    ),

    days_in_stat as (
        select
            * except (days_in_status),

            cast(aligned_enrollment_academic_year as string)
            || '-'
            || right(
                cast(aligned_enrollment_academic_year + 1 as string), 2
            ) as aligned_enrollment_academic_year_display,

            if(
                status_end_date = status_start_date,
                1,
                date_diff(status_end_date, status_start_date, day)
            ) as days_in_status,

        from remove_not_in_workflow_rows
    )

select
    f.region,
    f.actual_enrollment_academic_year as enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.aligned_enrollment_academic_year,
    f.aligned_enrollment_academic_year_display,
    f.finalsite_student_id,
    f.powerschool_student_number,
    f.last_name,
    f.first_name,
    f.grade_level,
    f.status_order,
    f.detailed_status,
    f.status_start_date,
    f.status_end_date,
    f.days_in_status,

    'KTAF' as org,

    coalesce(x.powerschool_school_id, 0) as schoolid,
    coalesce(x.abbreviation, 'No School Assigned') as school,

    coalesce(xl.powerschool_school_id, 0) as latest_schoolid,
    coalesce(xl.abbreviation, 'No School Assigned') as latest_school,

    date(f.actual_enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,
    date(f.actual_enrollment_academic_year, 6, 30) as sre_academic_year_end,

    row_number() over (
        partition by f.actual_enrollment_academic_year, f.finalsite_student_id
        order by f.status_start_date desc, f.status_order desc
    ) as rn,

from days_in_stat as f
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as x on f.school = x.name
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as xl
    on f.latest_school = xl.name
