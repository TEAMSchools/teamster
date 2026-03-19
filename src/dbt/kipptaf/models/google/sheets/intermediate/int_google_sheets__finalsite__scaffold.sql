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
            g.goal_type in (
                'Inquiries',
                'Applications',
                'Offers',
                'Assigned School',
                'Accepted',
                'Conversion'
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
