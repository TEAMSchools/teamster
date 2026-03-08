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

            case
                when
                    g.goal_name in (
                        'Inquiries',
                        'Applications',
                        'Offers',
                        'Assigned School',
                        'Accepted',
                        'Offers to Accepted',
                        'Accepted to Enrolled',
                        'Offers to Enrolled'
                    )
                then 'Ever'
                else 'Current'
            end as grouped_status_timeframe,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        inner join
            {{ ref("stg_google_sheets__finalsite__goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.schoolid = g.schoolid
            and b.grade_level = g.grade_level
        where g.goal_type != 'Enrollment'
    ),

    enrolled as (
        select enrollment_academic_year, finalsite_id, latest_status,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            grouped_status = latest_status
            and latest_status in ('Enrolled', 'Enrollment In Progress')
    ),

    conversion_grouping_numerator as (
        select enrollment_academic_year, finalsite_id, goal_type, goal_name,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            goal_type = 'Conversion'
            and grouped_status_timeframe = 'Ever'
            and enrollment_type = 'New'
    )

-- current statuses with latest
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    f.grouped_status_end_date,
    f.days_in_grouped_status,

    null as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.latest_status
    and s.goal_name = f.latest_status
    and s.grouped_status_timeframe = f.grouped_status_timeframe
where
    s.grouped_status_timeframe = 'Current'
    and s.goal_name in ('Waitlisted', 'Deferred', 'Pending Offers')

union all

-- current statuses with grouped
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    f.grouped_status_end_date,
    f.days_in_grouped_status,

    null as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
    and s.goal_name = f.grouped_status
    and s.grouped_status_timeframe = f.grouped_status_timeframe
where s.grouped_status_timeframe = 'Current' and s.goal_name = 'Pending Offers'

union all

-- current statuses with grouped status for pending offers cats
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    f.grouped_status_end_date,
    f.days_in_grouped_status,

    null as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
    and s.goal_name = f.goal_name
    and s.grouped_status_timeframe = f.grouped_status_timeframe
where
    s.grouped_status_timeframe = 'Current'
    and s.goal_name in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')

union all

-- ever statuses with grouped_status (goal type)
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
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
    and s.grouped_status_timeframe = f.grouped_status_timeframe
where
    s.grouped_status_timeframe = 'Ever'
    and s.goal_name in ('Inquiries', 'Applications', 'Offers', 'Accepted')

union all

-- benchmark conversions
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    null as grouped_status_order,
    null as grouped_status_start_date,
    null as grouped_status_end_date,
    null as days_in_grouped_status,

    c.finalsite_id as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_name = f.grouped_status
    and s.grouped_status_timeframe = f.grouped_status_timeframe
left join
    conversion_grouping_numerator as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
    and f.goal_name = c.goal_name
where s.grouped_status_timeframe = 'Ever' and s.goal_type = 'Conversion'

union all

-- overall conversion - enrolled /enrollent in progress
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
    s.grouped_status_timeframe,

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
    f.latest_status,
    f.self_contained,
    f.enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    null as grouped_status_order,
    null as grouped_status_start_date,
    null as grouped_status_end_date,
    null as days_in_grouped_status,

    c.finalsite_id as goal_name_value,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_name = f.grouped_status
    and s.grouped_status_timeframe = f.grouped_status_timeframe
left join
    enrolled as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
    and f.goal_type = c.goal_type
    and f.goal_name = c.goal_name
where s.grouped_status_timeframe = 'Ever' and s.goal_type = 'Assigned School'
