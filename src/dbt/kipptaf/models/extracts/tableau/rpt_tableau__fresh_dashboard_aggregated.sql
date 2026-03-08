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

    add_group_status_end_date as (
        select
            enrollment_academic_year,
            finalsite_id,
            enroll_status,
            enrollment_type,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,

            lead(grouped_status_start_date, 1, current_date('America/New_York')) over (
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

    pending_offers_categories as (
        select
            enrollment_academic_year,
            finalsite_id,
            enroll_status,
            enrollment_type,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,
            grouped_status_end_date,
            days_in_grouped_status,

            case
                when days_in_grouped_status <= 4
                then '<= 4 Days'
                when days_in_grouped_status between 5 and 10
                then '>= 5 & <= 10 Days'
                when days_in_grouped_status > 10
                then '> 10 Days'
            end as goal_name,

        from days_in_status
        where grouped_status = 'Pending Offers'

    ),

    -- trunk-ignore(sqlfluff/ST03)
    currently_accepted as (
        -- grouped status is made of multiple detailed status. need 1 row
        select distinct enrollment_academic_year, finalsite_id,
        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status = 'Currently Accepted'
    ),

    -- trunk-ignore(sqlfluff/ST03)
    currently_enrolled as (
        select enrollment_academic_year, finalsite_id,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status = 'Enrolled' and latest_status = 'Enrolled'
    ),

    -- trunk-ignore(sqlfluff/ST03)
    currently_enrollment_in_progress as (
        select enrollment_academic_year, finalsite_id,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            grouped_status = 'Enrollment In Progress'
            and latest_status = 'Enrollment In Progress'
    ),

    -- trunk-ignore(sqlfluff/ST03)
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

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

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
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
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

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

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
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
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

    c.grouped_status_order,
    c.grouped_status_start_date,
    c.grouped_status_end_date,
    c.days_in_grouped_status,

    c.finalsite_id as goal_name_value,

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
left join
    pending_offers_categories as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
    and f.grouped_status = c.grouped_status
    and f.goal_name = c.goal_name
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

-- conversions
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
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    conversion_grouping_numerator as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
where s.goal_type = 'Conversion'
