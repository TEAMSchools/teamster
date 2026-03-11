with
    scaffold as (
        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            x.grade_band as school_level,

            enrollment_type,

            'School' as goal_granularity,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on s.schoolid = x.powerschool_school_id
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        /* hardcoding year to avoid issues when PS rollsover and next year because
           current year */
        where s.academic_year = 2026 and s.grade_level = -1

        union all

        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            s.school_level,

            enrollment_type,

            'School/Grade Level' as goal_granularity,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        /* hardcoding year to avoid issues when PS rollsover and next year because
           current year */
        where s.academic_year = 2026 and s.grade_level != -1 and s.schoolid != 0
    ),

    data_stack_school as (
        -- PART 1A: THE STUDENTS (Actuals) by enroll type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            -1 as grade_level,
            latest_status,
            self_contained,
            enroll_status,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,

            'Student' as row_type,

            1 as student_count,

            null as seat_target,
            null as fdos_target,
            null as budget_target,
            null as new_student_target,
            null as re_enroll_projection,

            enrollment_type,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        -- PART 1B: THE STUDENTS (Actuals) by aligned enroll type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            -1 as grade_level,
            latest_status,
            self_contained,
            enroll_status,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,

            'Student' as row_type,

            1 as student_count,

            null as seat_target,
            null as fdos_target,
            null as budget_target,
            null as new_student_target,
            null as re_enroll_projection,

            aligned_enrollment_type as enrollment_type,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        -- PART 2: THE GOALS (Targets) - School
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,

            null as finalsite_id,
            grade_level,

            'Goal Record' as latest_status,
            'NA' as self_contained,
            null as enroll_status,
            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,

            'Goal' as row_type,

            0 as student_count,

            seat_target,
            fdos_target,
            budget_target,
            new_student_target,
            re_enroll_projection,

            enrollment_type,

        from {{ ref("int_tableau__finalsite_ptg_goals_scaffold") }}
        where goal_granularity = 'School'
    ),

    data_stack_school_grade as (
        -- PART 1A: THE STUDENTS (Actuals) by enroll type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            grade_level,
            latest_status,
            self_contained,
            enroll_status,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,

            'Student' as row_type,

            1 as student_count,

            null as seat_target,
            null as fdos_target,
            null as budget_target,
            null as new_student_target,
            null as re_enroll_projection,

            enrollment_type,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        -- PART 1B: THE STUDENTS (Actuals) by aligned enroll type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            grade_level,
            latest_status,
            self_contained,
            enroll_status,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,

            'Student' as row_type,

            1 as student_count,

            null as seat_target,
            null as fdos_target,
            null as budget_target,
            null as new_student_target,
            null as re_enroll_projection,

            aligned_enrollment_type as enrollment_type,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        -- PART 2: THE GOALS (Targets) - School
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,

            null as finalsite_id,
            grade_level,

            'Goal Record' as latest_status,
            'NA' as self_contained,
            null as enroll_status,
            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,

            'Goal' as row_type,

            0 as student_count,

            seat_target,
            fdos_target,
            budget_target,
            new_student_target,
            re_enroll_projection,

            enrollment_type,

        from {{ ref("int_tableau__finalsite_ptg_goals_scaffold") }}
        where goal_granularity = 'School/Grade Level'
    )

select
    s.academic_year,
    s.org,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.grade_level,
    s.enrollment_type,

    d.finalsite_id,
    d.latest_status,
    d.enrollment_type as student_enrollment_type,
    d.self_contained,
    d.row_type,
    d.student_count,
    d.seat_target,
    d.fdos_target,
    d.budget_target,
    d.new_student_target,
    d.re_enroll_projection,

from scaffold as s
left join
    data_stack_school as d
    on s.academic_year = d.enrollment_academic_year
    and s.region = d.region
    and s.schoolid = d.schoolid
    and s.grade_level = d.grade_level
    and s.enrollment_type = d.enrollment_type
where s.grade_level = -1

union all

select
    s.academic_year,
    s.org,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.grade_level,
    s.enrollment_type,

    d.finalsite_id,
    d.latest_status,
    d.enrollment_type as student_enrollment_type,
    d.self_contained,
    d.row_type,
    d.student_count,
    d.seat_target,
    d.fdos_target,
    d.budget_target,
    d.new_student_target,
    d.re_enroll_projection,

from scaffold as s
left join
    data_stack_school_grade as d
    on s.academic_year = d.enrollment_academic_year
    and s.region = d.region
    and s.schoolid = d.schoolid
    and s.grade_level = d.grade_level
    and s.enrollment_type = d.enrollment_type
where s.grade_level != -1 and s.schoolid != 0
