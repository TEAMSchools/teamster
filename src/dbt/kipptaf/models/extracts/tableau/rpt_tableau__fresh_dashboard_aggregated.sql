with
    scaffold as (
        -- join for school/grade level
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
            {{ ref("stg_google_sheets__finalsite_goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.schoolid = g.schoolid
            and b.grade_level = g.grade_level

        union all

        -- join for school
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
            {{ ref("stg_google_sheets__finalsite_goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.schoolid = g.schoolid

        union all

        -- join for region/grade level
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
            {{ ref("stg_google_sheets__finalsite_goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.grade_level = g.grade_level
    )

select
    academic_year,
    org,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    goal_name,
    goal_value,

from scaffold
