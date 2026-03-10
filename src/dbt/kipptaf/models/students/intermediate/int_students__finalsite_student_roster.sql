with
    -- current year students
    current_students as (
        select
            f.finalsite_enrollment_id,

            e.district as ps_org,
            e.region as ps_region,
            e.schoolid as ps_schoolid,
            e.school as ps_school,
            e.grade_level as ps_grade_level,
            e.enroll_status as ps_enroll_status,

            'Returning' as enrollment_type,

        from {{ ref("stg_finalsite__status_report") }} as f
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.finalsite_enrollment_id = e.infosnap_id
            -- TODO: must hardcode year to avoid issues when 2026 becomes current year
            and e.academic_year = 2025
            and e.enroll_status = 0
            and e.rn_year = 1
        /* TODO: have to hardcode year so that it doesnt get dropped when PS gets
           rolled over and next year becomes current year */
        where f._dagster_partition_key = '2026_27' and f.active_school_year_int = 2026
    ),

    next_year_students_new_only as (
        -- next year new students
        select f.finalsite_enrollment_id, 'New' as enrollment_type,

        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            current_students as c
            on f.finalsite_enrollment_id = c.finalsite_enrollment_id
        where
            f._dagster_partition_key = '2026_27'
            /* TODO: hardcoding year because new student counts are only accurate on the
               2026 years (the 2025 file has 2026 data but it stopped adding students
               when the rollover happened) */
            and f.active_school_year_int = 2026
            and c.finalsite_enrollment_id is null
    ),

    roster as (
        -- returning students 2025
        select
            f.file_year,
            f.finalsite_enrollment_id,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.self_contained,
            f.gender,
            f.birthdate,
            f.detailed_status,
            f.status_start_date,
            f.status_order,

            2025 as enrollment_academic_year,
            '2025-26' as enrollment_academic_year_display,
            '2025_26' as _dagster_partition_key,

            c.ps_org as org,
            c.ps_region as region,
            c.ps_schoolid as schoolid,
            c.ps_school as school,
            c.ps_grade_level as grade_level,

            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,
            c.ps_enroll_status as enroll_status,

            c.enrollment_type,

            'Pre PS Rollover' as reporting_season,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        inner join
            current_students as c
            on f.finalsite_enrollment_id = c.finalsite_enrollment_id
        /* TODO: the 2026 file shows accurate 2025 student data counts, but wrong
           grades, and wrong school, the correct grades and schools exist on the 2025
           file,but it has become obsolete because it is not updating new students. im
           attempting to create fake 2025 finalsite rows for returning students, hence
           why all the hardcoding here */
        where f.file_year = 2026

        union all

        -- returning students 2026
        select
            f.file_year,
            f.finalsite_enrollment_id,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.self_contained,
            f.gender,
            f.birthdate,
            f.detailed_status,
            f.status_start_date,
            f.status_order,

            f.enrollment_academic_year,
            f.enrollment_academic_year_display,
            f._dagster_partition_key,

            f.org,
            f.region,
            f.schoolid,
            f.school,
            f.grade_level,

            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,
            e.enroll_status,

            c.enrollment_type,

            'Post PS Rollover' as reporting_season,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        inner join
            current_students as c
            on f.finalsite_enrollment_id = c.finalsite_enrollment_id
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
        /* TODO: only the 2026 file contains the correct data for returning students in
           2026. cant use vars because when PS rollover, 2026 will no longer be next
           year. it will become current */
        where f.file_year = 2026

        union all

        -- new students
        select
            f.file_year,
            f.finalsite_enrollment_id,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.self_contained,
            f.gender,
            f.birthdate,
            f.detailed_status,
            f.status_start_date,
            f.status_order,

            f.enrollment_academic_year,
            f.enrollment_academic_year_display,
            f._dagster_partition_key,

            f.org,
            f.region,
            f.schoolid,
            f.school,
            f.grade_level,

            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,
            e.enroll_status,

            n.enrollment_type,

            'All' as reporting_season,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        inner join
            next_year_students_new_only as n
            on f.finalsite_enrollment_id = n.finalsite_enrollment_id
        /* no filter_year is needed here because it is an inner join, and
           _dagster_partition_key (the equivalent of filter_year) was already used on
           the next_year_students_new_only cte */
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
    )

select
    r.file_year,
    r.enrollment_academic_year,
    r.enrollment_academic_year_display,
    r.org,
    r.region,
    r.schoolid,
    r.school,
    r.finalsite_enrollment_id,
    r.powerschool_student_number,
    r.first_name,
    r.last_name,
    r.grade_level,
    r.self_contained,
    r.gender,
    r.birthdate,
    r.is_enrolled_fdos,
    r.is_enrolled_oct01,
    r.is_enrolled_oct15,
    r.enroll_status,
    r.enrollment_type,
    r.detailed_status,
    r.status_start_date,
    r.status_order,
    r.reporting_season,

    x.status_group_name,
    x.status_group_value,
    x.grouped_status_order,
    x.grouped_status_timeframe,
    x.qa_flag,

    t.type as reporting_type,
    t.code as reporting_code,
    t.start_date as reporting_start_date,
    t.end_date as reporting_end_date,

    if(
        current_date('{{ var("local_timezone") }}') between t.start_date and t.end_date,
        true,
        false
    ) as active_season,

    first_value(r.detailed_status) over (
        partition by r.enrollment_academic_year, r.finalsite_enrollment_id
        order by r.status_start_date desc
    ) as latest_status,

from roster as r
inner join
    {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
    on r._dagster_partition_key = x._dagster_partition_key
    and r.reporting_season = x.reporting_season
    and r.enrollment_type = x.enrollment_type
    and r.detailed_status = x.detailed_status
    and x.valid_detailed_status
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as t
    on r.enrollment_academic_year = t.academic_year
    and r.region = t.region
    and r.reporting_season = t.name
    and t.type = 'SRE'
