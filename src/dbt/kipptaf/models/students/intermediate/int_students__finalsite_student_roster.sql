with
    actual_enroll_type as (
        select
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

            f.next_academic_year as aligned_enrollment_academic_year,

            e1.enroll_status as ps_enroll_status,
            e1.region as ps_region,
            e1.school as ps_school,
            e1.grade_level as ps_grade_level,
            e1.is_enrolled_fdos,
            e1.is_enrolled_oct01,
            e1.is_enrolled_oct15,

            if(
                e2.next_year_enrollment_type is null,
                'New',
                e2.next_year_enrollment_type
            ) as enrollment_academic_year_enrollment_type,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e1
            on f.enrollment_academic_year = e1.academic_year
            and f.finalsite_enrollment_id = e1.infosnap_id
            and e1.rn_year = 1
        left join
            {{ ref("int_extracts__student_enrollments") }} as e2
            on f.enrollment_academic_year - 1 = e2.academic_year
            and f.finalsite_enrollment_id = e2.infosnap_id
            and e2.rn_year = 1
        -- fixing the value for now - will remove when a better data model is created
        where f.enrollment_academic_year <= 2026
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
