with
    actual_enroll_type as (
        select
            f.current_academic_year,
            f.next_academic_year,
            f.org,
            f.region,
            f.schoolid,
            f.school,
            f.finalsite_enrollment_id,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.grade_level,
            f.self_contained,
            f.detailed_status,
            f.status_order,
            f.status_start_date,

            f.next_academic_year as aligned_enrollment_academic_year,

            e.enroll_status as ps_enroll_status,
            e.region as ps_region,
            e.school as ps_school,
            e.grade_level as ps_grade_level,
            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,

            if(
                e.enroll_status = 0, f.current_academic_year, f.next_academic_year
            ) as enrollment_academic_year,

            if(
                e.enroll_status = 0,
                cast(f.current_academic_year as string)
                || '-'
                || right(cast(f.current_academic_year + 1 as string), 2),
                f.enrollment_academic_year_display
            ) as enrollment_academic_year_display,

            if(
                e.next_year_enrollment_type is null, 'New', e.next_year_enrollment_type
            ) as enrollment_academic_year_enrollment_type,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
        -- this has to be a fixed value that is changed when the rollover happens
        where f.enrollment_academic_year = 2026
    )

select
    f.aligned_enrollment_academic_year,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.current_academic_year,
    f.next_academic_year,
    f.org,
    f.region,
    f.schoolid,
    f.school,
    f.finalsite_enrollment_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level,
    f.self_contained,
    f.detailed_status,
    f.status_order,
    f.status_start_date,
    f.enrollment_academic_year_enrollment_type,
    f.ps_enroll_status,
    f.ps_region,
    f.ps_school,
    f.ps_grade_level,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,

    x.status_group_name,
    x.status_group_value,

    cast(f.aligned_enrollment_academic_year as string)
    || '-'
    || right(
        cast(f.aligned_enrollment_academic_year + 1 as string), 2
    ) as aligned_enrollment_academic_year_display,

    first_value(f.detailed_status) over (
        partition by f.enrollment_academic_year, f.finalsite_enrollment_id
        order by f.status_start_date desc
    ) as latest_status,

    if(
        f.enrollment_academic_year = f.current_academic_year,
        f.grade_level + 1,
        f.grade_level
    ) as aligned_enrollment_academic_year_grade_level,

from actual_enroll_type as f
inner join
    {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
    on f.enrollment_academic_year = x.enrollment_academic_year
    and f.enrollment_academic_year_enrollment_type = x.enrollment_type
    and f.detailed_status = x.detailed_status
