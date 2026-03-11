with
    enrolled as (
        select
            enrollment_academic_year,
            finalsite_id,
            latest_status,

            'Assigned School' as goal_type,
            'Overall Conversion' as goal_name,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            grouped_status = latest_status
            and latest_status = 'Enrolled'
            and grouped_status_timeframe = 'Current'
    ),

    conversion_grouping_numerator as (
        select
            enrollment_academic_year,
            finalsite_id,

            'Conversion' as goal_type,
            regexp_replace(goal_name, r' Num$', '') as goal_name,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            goal_name in (
                'Accepted to Enrolled Num',
                'Offers to Accepted Num',
                'Offers to Enrolled Num'
            )
            and grouped_status_timeframe = 'Current'
            and enrollment_type = 'New'
    ),

    pending_offers_by_day_numerator as (
        select enrollment_academic_year, finalsite_id, goal_type, goal_name,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where
            goal_name in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')
            and enrollment_type = 'New'
            and grouped_status_timeframe = 'Current'
    )

-- latest status: deferred and waitlisted
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

    f.finalsite_id as goal_name_value,

from {{ ref("int_google_sheets__finalsite__scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.goal_type
    and s.goal_name = f.latest_status
    and s.grouped_status_timeframe = f.grouped_status_timeframe
where
    s.grouped_status_timeframe = 'Current' and s.goal_name in ('Deferred', 'Waitlisted')

union all

-- current status: all pending offers, inquiries, apps, offers
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

    if(
        f.goal_name in ('Pending Offers', 'Inquiries', 'Applications', 'Offers'),
        f.finalsite_id,
        n.finalsite_id
    ) as goal_name_value,

from {{ ref("int_google_sheets__finalsite__scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.goal_type
    and s.goal_name = f.goal_name
    and s.grouped_status_timeframe = f.grouped_status_timeframe
left join
    pending_offers_by_day_numerator as n
    on f.enrollment_academic_year = n.enrollment_academic_year
    and f.finalsite_id = n.finalsite_id
    and f.goal_type = n.goal_type
    and f.goal_name = n.goal_name
where s.goal_type in ('Pending Offers', 'Inquiries', 'Applications', 'Offers')

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
    f.grouped_status_order,
    f.grouped_status_start_date,
    f.grouped_status_end_date,
    f.days_in_grouped_status,

    c.finalsite_id as goal_name_value,

from {{ ref("int_google_sheets__finalsite__scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.goal_type
    and s.goal_name = f.goal_name
    and s.grouped_status_timeframe = f.grouped_status_timeframe
left join
    conversion_grouping_numerator as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
    and f.goal_type = c.goal_type
    and f.goal_name = c.goal_name
where s.grouped_status_timeframe = 'Ever' and s.goal_type = 'Conversion'

union all

-- overall conversion - enrolled
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

    c.finalsite_id as goal_name_value,

from {{ ref("int_google_sheets__finalsite__scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.schoolid = f.schoolid
    and s.grade_level = f.grade_level
    and s.goal_type = f.goal_type
    and s.goal_name = f.goal_name
    and s.grouped_status_timeframe = f.grouped_status_timeframe
left join
    enrolled as c
    on f.enrollment_academic_year = c.enrollment_academic_year
    and f.finalsite_id = c.finalsite_id
    and f.goal_type = c.goal_type
    and f.goal_name = c.goal_name
where s.grouped_status_timeframe = 'Ever' and s.goal_type = 'Assigned School'
