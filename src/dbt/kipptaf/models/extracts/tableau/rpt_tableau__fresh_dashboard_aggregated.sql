with
    scaffold as (
        select
            b.academic_year,
            b.org,
            b.region,
            b.schoolid,
            b.school,
            b.grade_level,

            g.school_level,
            g.goal_granularity,
            g.goal_type,
            g.goal_name,
            g.goal_value,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        inner join
            {{ ref("stg_google_sheets__finalsite__goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.schoolid = g.schoolid
            and b.grade_level = g.grade_level
    ),

    add_group_status_end_date as (
        select
            enrollment_academic_year,
            finalsite_id,
            enroll_status,
            enrollment_type,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,

            lead(
                grouped_status_start_date,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_id, enrollment_academic_year
                order by grouped_status_start_date asc, grouped_status_order asc
            ) as grouped_status_end_date,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status_order != 0 and enrollment_type = 'New'
    ),

    days_in_status as (
        select
            enrollment_academic_year,
            finalsite_id,
            enroll_status,
            enrollment_type,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,
            grouped_status_end_date,

            if(
                grouped_status_end_date = grouped_status_start_date,
                1,
                date_diff(grouped_status_end_date, grouped_status_start_date, day)
            ) as days_in_grouped_status,

        from add_group_status_end_date
    ),

    currently_enrolled as (
        select enrollment_academic_year, finalsite_id,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status = 'Enrolled' and latest_status = 'Enrolled'
    ),

    currently_enrollment_in_progress as (
        select enrollment_academic_year, finalsite_id,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            grouped_status = 'Enrollment In Progress'
            and latest_status = 'Enrollment In Progress'
    ),

    conversion_grouping_numerator as (
        select enrollment_academic_year, finalsite_id, grouped_status,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            grouped_status in (
                'Offers to Accepted Num',
                'Accepted to Enrolled Num',
                'Offers to Enrolled Num'
            )
            and enrollment_type = 'New'
    )

-- current statuses
select
    s.academic_year,
    s.org,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.grade_level,
    s.goal_granularity,
    s.goal_type,
    s.goal_name,
    s.goal_value,

    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.enroll_status,
    f.birthdate,
    f.gender,
    f.grouped_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    f.grouped_status_timeframe,
    null as grouped_status_end_date,
    null as days_in_grouped_status,

    null as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
    and s.goal_name = f.latest_status
    and f.grouped_status_timeframe = 'Current'
