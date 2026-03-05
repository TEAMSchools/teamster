with
    /* this cte uses the current year file to report on current year students and next
       year students and is valid during pre fs rollover season for a region */
    pre_fs_rollover as (
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
            f.birthdate,
            f.gender,
            f.self_contained,
            f.detailed_status,
            f.status_order,
            f.status_start_date,

            f.reporting_type,
            f.reporting_code,
            f.reporting_season,
            f.reporting_start_date,
            f.reporting_end_date,

            e1.enroll_status as ps_enroll_status,
            e1.region as ps_region,
            e1.school as ps_school,
            e1.grade_level as ps_grade_level,

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
        where f.reporting_season = 'Pre FS Rollover'
    )

select *,
from pre_fs_rollover
