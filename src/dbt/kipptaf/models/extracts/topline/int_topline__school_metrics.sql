with
    grade_band as (
        select 'K-2' as grade_band, grade_level,
        from unnest([0, 2]) as grade_level

        union all

        select '3-4' as grade_band, grade_level,
        from unnest([3, 4]) as grade_level

        union all

        select 'MS' as grade_band, grade_level,
        from unnest([5, 6, 7, 8]) as grade_level

        union all

        select 'HS' as grade_band, grade_level,
        from unnest([9, 10, 11, 12]) as grade_level
    ),

    school_grade_agg as (
        select
            'School/Grade' as org_level,

            schoolid,
            school_abbreviation,
            school_name,
            cast(grade_level as string) as grade_level,
            academic_year,

            metric_category,
            metric_subcategory,
            metric_subject,
            metric_period,
            metric_name,
            round(avg(metric_value_float), 2) as metric_value_float
        from {{ ref("int_topline__student_metrics") }}
        group by all

        union all

        select
            'School' as org_level,

            schoolid,
            school_abbreviation,
            school_name,
            'All' as grade_level,
            academic_year,

            metric_category,
            metric_subcategory,
            metric_subject,
            metric_period,
            metric_name,
            round(avg(metric_value_float), 2) as metric_value_float
        from {{ ref("int_topline__student_metrics") }}
        group by all

        union all

        select
            'School/Grade Band' as org_level,

            sm.schoolid,
            sm.school_abbreviation,
            sm.school_name,
            gb.grade_band as grade_level,
            sm.academic_year,

            sm.metric_category,
            sm.metric_subcategory,
            sm.metric_subject,
            sm.metric_period,
            sm.metric_name,
            round(avg(sm.metric_value_float), 2) as metric_value_float
        from {{ ref("int_topline__student_metrics") }} as sm
        inner join grade_band as gb on sm.grade_level = gb.grade_level
        group by all
    )

select sg.*,

-- ts.goal_float,
-- if(sg.metric_value_float >= ts.goal_float, 1, 0) as goal_met_int
from
    school_grade_agg as sg
    -- inner join
    -- `topline_scratch.topline_scaffold` as ts
    -- on sg.academic_year = ts.academic_year
    -- and sg.schoolid = ts.location
    -- and sg.org_level = ts.org_level
    -- and sg.grade_level = ts.level_id
    -- and sg.metric_period = ts.period
    
