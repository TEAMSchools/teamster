select
    m.academic_year,
    m.student_number,
    m.studentid,
    m.student_name,
    m.grade_level,
    m.region,
    m.schoolid,
    m.school,
    m.iep_status,
    m.lep_status,
    m.is_504,
    m.year_in_network,
    m.is_retained_year,
    m.gender,
    m.ethnicity,
    m.entrydate,
    m.exitdate,
    m.is_enrolled_week,
    m.is_current_week,
    m.layer,
    m.indicator,
    m.discipline,
    m.term,

    safe_divide(sum(m.numerator), sum(m.denominator)) as metric_product,
    avg(m.metric_value) as metric_average,
    sum(m.metric_value) as metric_sum,
from {{ ref("int_topline__student_metrics") }} as m
left join
    {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
    on m.region = g.entity
    and m.schoolid = g.schoolid
    and m.grade_level between g.grade_low and g.grade_high
    and m.layer = g.layer
    and m.indicator = g.topline_indicator
    and g.org_level = 'school'
group by
m.academic_year,
    m.student_number,
    m.studentid,
    m.student_name,
    m.grade_level,
    m.region,
    m.schoolid,
    m.school,
    m.iep_status,
    m.lep_status,
    m.is_504,
    m.year_in_network,
    m.is_retained_year,
    m.gender,
    m.ethnicity,
    m.entrydate,
    m.exitdate,
    m.is_enrolled_week,
    m.is_current_week,
    m.layer,
    m.indicator,
    m.discipline,
    m.term
    