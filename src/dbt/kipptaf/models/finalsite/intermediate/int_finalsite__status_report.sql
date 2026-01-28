with
    finalsite_report as (
        select
            f.* except (school),

            x.powerschool_school_id as schoolid,
            x.abbreviation as school,

            row_number() over (
                partition by f.enrollment_academic_year, f.finalsite_student_id
                order by f.status_start_date desc
            ) as rn,

            cast(f.enrollment_academic_year as string)
            || '-'
            || right(
                cast(f.enrollment_academic_year + 1 as string), 2
            ) as enrollment_academic_year_display,

        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    )

select
    * except (finalsite_student_id, powerschool_student_number),

    /* since we get snapshot data, these will ensure only the latest of these fields is
    used for a student, retroactively, for a given academic year */
    first_value(region) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as latest_region,

    first_value(finalsite_student_id) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as finalsite_student_id,

    first_value(powerschool_student_number) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as powerschool_student_number,

    coalesce(
        first_value(schoolid) over (
            partition by enrollment_academic_year, finalsite_student_id
            order by status_start_date desc
        ),
        0
    ) as latest_schoolid,

    coalesce(
        first_value(school) over (
            partition by enrollment_academic_year, finalsite_student_id
            order by status_start_date desc
        ),
        'No School Assigned'
    ) as latest_school,

from finalsite_report
