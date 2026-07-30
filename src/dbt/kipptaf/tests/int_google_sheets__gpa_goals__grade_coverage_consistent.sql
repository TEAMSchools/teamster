with
    goal_grades as (
        select academic_year, metric, org_level, region, schoolid, grade_level,
        from {{ ref("int_google_sheets__gpa_goals") }}
        cross join unnest(generate_array(grade_low, grade_high)) as grade_level
    ),

    grains as (
        select distinct academic_year, metric, org_level, region, schoolid,
        from goal_grades
    ),

    metric_grades as (
        select distinct academic_year, metric, grade_level, from goal_grades
    ),

    /* every grade any grain covers for a metric is expected at every grain that
       has goals for that same metric */
    expected as (
        select
            gr.academic_year,
            gr.metric,
            gr.org_level,
            gr.region,
            gr.schoolid,

            mg.grade_level,
        from grains as gr
        inner join
            metric_grades as mg
            on gr.academic_year = mg.academic_year
            and gr.metric = mg.metric
    )

select e.academic_year, e.metric, e.org_level, e.region, e.schoolid, e.grade_level,
from expected as e
left join
    goal_grades as gg
    on e.academic_year = gg.academic_year
    and e.metric = gg.metric
    and e.org_level = gg.org_level
    and e.grade_level = gg.grade_level
    and e.region is not distinct from gg.region
    and e.schoolid is not distinct from gg.schoolid
where gg.grade_level is null
