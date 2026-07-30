with
    /* scoped to years the student spine actually covers, so a goal entered ahead
       of its academic year does not fail before enrollment exists.

       Deliberately NOT scoped by region. TODO(#4581): int_gpa__goal_student_metrics
       excludes kipppaterson pending the gpa_term / gpa_cumulative unions, and
       Paterson runs ES and MS only, so a Paterson-scoped goal targets a
       population of zero and genuinely reaches no dashboard — flagging it is
       correct, not a false positive. Revisit only if Paterson opens a high
       school BEFORE that union lands, which would make this fire on a goal that
       is merely early rather than wrong. */
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
