with
    /* scoped to years the student spine actually covers, so a goal entered ahead
       of its academic year does not fail before enrollment exists */
    measured_years as (
        select distinct academic_year, from {{ ref("int_gpa__goal_student_metrics") }}
    )

select
    g.academic_year,
    g.metric,
    g.org_level,
    g.region,
    g.schoolid,
    g.grade_band,
    g.aggregation_hash,
from {{ ref("int_google_sheets__gpa_goals") }} as g
inner join measured_years as my on g.academic_year = my.academic_year
left join
    {{ ref("int_gpa__goal_aggregations") }} as a
    on g.academic_year = a.academic_year
    and g.metric = a.metric
    and g.aggregation_hash = a.aggregation_hash
where a.aggregation_hash is null
