with
    -- current year students
    current_students as (
        select
            f.finalsite_enrollment_id,

            e.district as ps_org,
            e.region as ps_region,
            e.school as ps_school,
            e.grade_level as ps_grade_level,

            'Returning' as enrollment_type,

        from {{ ref("stg_finalsite__status_report") }} as f
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.finalsite_enrollment_id = e.infosnap_id
            -- must hardcode year to avoid issues when 2026 becomes current year
            and e.academic_year = 2025
            and e.enroll_status = 0
            and e.rn_year = 1
        /* have to hardcode year so that it doesnt get dropped when PS gets rolled
           over and next year becomes current year */
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
            and f.active_school_year_int = 2026
            and c.finalsite_enrollment_id is null
    ),

    roster as (
        -- returning students 2025
        select
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

            c.ps_org as org,
            c.ps_region as region,
            c.ps_school as school,
            c.ps_grade_level as grade_level,

            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,

            c.enrollment_type,

            'Pre PS Rollover' as reporting_season,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        inner join
            current_students as c
            on f.finalsite_enrollment_id = c.finalsite_enrollment_id
        where f.file_year = 2026

        union all

        -- returning students 2026
        select
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

            f.org,
            f.region,
            f.school,
            f.grade_level,

            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,

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
        where f.file_year = 2026

        union all

        -- new students
        select
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

            f.org,
            f.region,
            f.school,
            f.grade_level,

            e.is_enrolled_fdos,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,

            n.enrollment_type,

            'All' as reporting_season,

        from {{ ref("int_finalsite__status_report_unpivot") }} as f
        inner join
            next_year_students_new_only as n
            on f.finalsite_enrollment_id = n.finalsite_enrollment_id
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year = e.academic_year
            and f.finalsite_enrollment_id = e.infosnap_id
            and e.rn_year = 1
    )

select *,
from roster
