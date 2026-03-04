with
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
            f.self_contained,
            f.detailed_status,
            f.status_order,
            f.status_start_date,

            f.next_academic_year as aligned_enrollment_academic_year,
            f.reporting_type,
            f.reporting_code,
            f.reporting_season,
            f.reporting_start_date,
            f.reporting_end_date,

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
        where f.reporting_season = 'Pre FS Rollover'
    ),

    post_fs_rollover as (
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
            f.self_contained,
            f.detailed_status,
            f.status_order,
            f.status_start_date,
            f.reporting_type,
            f.reporting_code,
            f.reporting_season,
            f.reporting_start_date,
            f.reporting_end_date,

            f.next_academic_year as aligned_enrollment_academic_year,

            e.enroll_status as ps_enroll_status,
            e.region as ps_region,
            e.school as ps_school,
            e.grade_level as ps_grade_level,
            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,

            if(e.enroll_status = 0, e.grade_level, f.grade_level) as grade_level,

            if(
                e.enroll_status = 0, f.current_academic_year, f.next_academic_year
            ) as enrollment_academic_year,

            if(
                e.enroll_status = 0,
                cast(f.current_academic_year as string)
                || '-'
                || right(cast(f.next_academic_year as string), 2),
                f.enrollment_academic_year_display
            ) as enrollment_academic_year_display,

            if(
                e.next_year_enrollment_type is null, 'New', e.next_year_enrollment_type
            ) as enrollment_academic_year_enrollment_type,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year - 1 = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
        where f.reporting_season = 'After FS Rollover'
    ),

    post_ps_rollover as (
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
            f.reporting_type,
            f.reporting_code,
            f.reporting_season,
            f.reporting_start_date,
            f.reporting_end_date,

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
            on f.enrollment_academic_year - 2 = e2.academic_year
            and f.finalsite_enrollment_id = e2.infosnap_id
            and e2.rn_year = 1
        where f.reporting_season = 'After PS Rollover'
    ),

    appended_rosters as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            aligned_enrollment_academic_year,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            enrollment_academic_year_enrollment_type,
            self_contained,
            detailed_status,
            status_order,
            status_start_date,
            ps_enroll_status,
            ps_region,
            ps_school,
            ps_grade_level,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            reporting_type,
            reporting_code,
            reporting_season,
            reporting_start_date,
            reporting_end_date,

        from pre_fs_rollover

        union all

        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            aligned_enrollment_academic_year,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            enrollment_academic_year_enrollment_type,
            self_contained,
            detailed_status,
            status_order,
            status_start_date,
            ps_enroll_status,
            ps_region,
            ps_school,
            ps_grade_level,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            reporting_type,
            reporting_code,
            reporting_season,
            reporting_start_date,
            reporting_end_date,

        from post_fs_rollover

        union all

        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            aligned_enrollment_academic_year,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            enrollment_academic_year_enrollment_type,
            self_contained,
            detailed_status,
            status_order,
            status_start_date,
            ps_enroll_status,
            ps_region,
            ps_school,
            ps_grade_level,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            reporting_type,
            reporting_code,
            reporting_season,
            reporting_start_date,
            reporting_end_date,

        from post_ps_rollover
    )

select
    a.aligned_enrollment_academic_year,
    a.enrollment_academic_year,
    a.enrollment_academic_year_display,
    a.current_academic_year,
    a.next_academic_year,
    a.org,
    a.region,
    a.schoolid,
    a.school,
    a.finalsite_enrollment_id,
    a.powerschool_student_number,
    a.first_name,
    a.last_name,
    a.grade_level,
    a.self_contained,
    a.detailed_status,
    a.status_order,
    a.status_start_date,
    a.enrollment_academic_year_enrollment_type,
    a.ps_enroll_status,
    a.ps_region,
    a.ps_school,
    a.ps_grade_level,
    a.is_enrolled_fdos,
    a.is_enrolled_oct01,
    a.is_enrolled_oct15,

    x.status_group_name,
    x.status_group_value,
    x.grouped_status_order,
    x.grouped_status_timeframe,
    x.qa_flag,

    cast(a.aligned_enrollment_academic_year as string)
    || '-'
    || right(
        cast(a.aligned_enrollment_academic_year + 1 as string), 2
    ) as aligned_enrollment_academic_year_display,

    first_value(a.detailed_status) over (
        partition by a.enrollment_academic_year, a.finalsite_enrollment_id
        order by a.status_start_date desc
    ) as latest_status,

from appended_rosters as a
inner join
    {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
    on a.enrollment_academic_year = x.enrollment_academic_year
    and a.enrollment_academic_year_enrollment_type = x.enrollment_type
    and a.detailed_status = x.detailed_status
where
    current_date('{{ var("local_timezone") }}')
    between a.reporting_start_date and a.reporting_end_date
