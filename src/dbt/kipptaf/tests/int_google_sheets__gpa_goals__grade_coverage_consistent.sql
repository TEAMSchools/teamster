with
    /* scoped to years the student spine covers, matching the sibling
       every_goal_aggregates test. Goals for a year not yet underway are entered
       school by school, so an in-progress rollout would otherwise read as an
       omission. */
    measured_years as (
        select distinct academic_year, from {{ ref("int_gpa__goal_student_metrics") }}
    ),

    goal_grades as (
        select
            g.academic_year, g.metric, g.org_level, g.region, g.schoolid, grade_level,
        from {{ ref("int_google_sheets__gpa_goals") }} as g
        inner join measured_years as my on g.academic_year = my.academic_year
        cross join unnest(generate_array(g.grade_low, g.grade_high)) as grade_level
    ),

    grains as (
        select distinct academic_year, metric, org_level, region, schoolid,
        from goal_grades
    ),

    /* pooled WITHIN org_level, never across it — a school is compared against
       what other schools cover, not against network-level coverage. Otherwise a
       school legitimately serving a narrower grade band than the network (a new
       high school still adding a grade a year) reads as an omission. */
    org_level_grades as (
        select distinct academic_year, metric, org_level, grade_level, from goal_grades
    ),

    expected as (
        select
            gr.academic_year,
            gr.metric,
            gr.org_level,
            gr.region,
            gr.schoolid,

            olg.grade_level,
        from grains as gr
        inner join
            org_level_grades as olg
            on gr.academic_year = olg.academic_year
            and gr.metric = olg.metric
            and gr.org_level = olg.org_level
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
