with
    data_stack as (
        -- PART 1A: THE STUDENTS (Actuals) by enroll type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            latest_status,
            enrollment_type,
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

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        -- PART 1A: THE STUDENTS (Actuals) by aligned enroll        type
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            finalsite_id,
            latest_status,
            aligned_enrollment_type as enrollment_type,
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

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where latest_status = 'Enrolled' and grouped_status = latest_status

        union all

        /* PART 2: THE GOALS (Targets) */
        select
            gs.enrollment_academic_year,
            gs.region,
            gs.schoolid,
            gs.school,

            null as finalsite_id,

            'Goal Record' as latest_status,
            null as enrollment_type,
            'NA' as self_contained,
            null as enroll_status,
            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,

            'Goal' as row_type,

            0 as student_count,

            gs.goal_value as seat_target,

            gf.goal_value as fdos_target,

            gb.goal_value as budget_target,

            gn.goal_value as new_student_target,

            ge.goal_value as re_enroll_projection,

        from {{ ref("stg_google_sheets__finalsite__goals") }} as gs
        left join
            {{ ref("stg_google_sheets__finalsite__goals") }} as gf
            on gs.schoolid = gf.schoolid
            and gs.goal_granularity = gf.goal_granularity
            and gf.goal_name = 'FDOS Target'
        left join
            {{ ref("stg_google_sheets__finalsite__goals") }} as gb
            on gs.schoolid = gb.schoolid
            and gs.goal_granularity = gb.goal_granularity
            and gb.goal_name = 'Budget Target'
        left join
            {{ ref("stg_google_sheets__finalsite__goals") }} as gn
            on gs.schoolid = gn.schoolid
            and gs.goal_granularity = gn.goal_granularity
            and gn.goal_name = 'New Student Target'
        left join
            {{ ref("stg_google_sheets__finalsite__goals") }} as ge
            on gs.schoolid = ge.schoolid
            and gs.goal_granularity = ge.goal_granularity
            and ge.goal_name = 'Re-Enroll Projection'
        where gs.goal_name = 'Seat Target' and gs.goal_granularity = 'School'
    )

select
    s.academic_year,
    s.org,
    s.region,
    'NA' as school_level,
    s.schoolid,
    s.school,
    null as grade_level,

    d.finalsite_id,
    d.latest_status,
    d.enrollment_type,
    d.self_contained,
    d.row_type,
    d.student_count,
    d.seat_target,
    d.fdos_target,
    d.budget_target,
    d.new_student_target,
    d.re_enroll_projection,

    'School' as granularity,

from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
left join
    data_stack as d
    on s.academic_year = d.enrollment_academic_year
    and s.region = d.region
    and s.schoolid = d.schoolid
