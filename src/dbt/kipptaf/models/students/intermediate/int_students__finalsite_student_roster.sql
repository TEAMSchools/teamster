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
            f.finalsite_student_id,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.grade_level,
            f.detailed_status,
            f.status_start_date,

            e.enroll_status as ps_enroll_status,
            e.region as ps_region,
            e.school as ps_school,
            e.grade_level as ps_grade_level,

            if(
                e.next_year_enrollment_type is null, 'New', e.next_year_enrollment_type
            ) as enrollment_year_enrollment_type,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year - 1 = e.academic_year
            and f.powerschool_student_number = e.student_number
            and e.rn_year = 1
    )

select
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.current_academic_year,
    f.next_academic_year,
    f.org,
    f.region,
    f.schoolid,
    f.school,
    f.finalsite_student_id,
    f.powerschool_student_number,
    f.last_name,
    f.first_name,
    f.grade_level,
    f.detailed_status,
    f.status_start_date,
    f.enrollment_year_enrollment_type,

    x.detailed_status_branched_ranking,
    x.valid_detailed_status,
    x.qa_flag,
    x.status_group_numerator,
    x.status_group_denominator,
    x.conversion_metric_numerator,
    x.conversion_metric_denominator,
    x.sre_academic_year_start,
    x.sre_academic_year_end,

from actual_enroll_type as f
inner join
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
    on f.enrollment_academic_year = x.enrollment_academic_year
    and f.enrollment_year_enrollment_type = x.enrollment_type
    and f.detailed_status = x.detailed_status
