select
    dr.student_id,
    dr.academic_year,
    dr.student_grade,
    dr.subject,
    dr.start_date,
    dr.completion_date,
    dr.baseline_diagnostic_y_n,
    dr.most_recent_diagnostic_y_n,
    dr.overall_scale_score,
    dr.percentile,
    dr.overall_relative_placement,
    dr.overall_relative_placement_int,
    dr.placement_3_level,
    dr.rush_flag,
    dr.mid_on_grade_level_scale_score,
    dr.percent_progress_to_annual_typical_growth,
    dr.percent_progress_to_annual_stretch_growth,
    dr.diagnostic_gain,
    dr.annual_typical_growth_measure,
    dr.annual_stretch_growth_measure,

    lc.region,
    lc.abbreviation as school_abbreviation,

    right(rt.code, 1) as round_number,
    coalesce(rt.name, 'Outside Round') as test_round,
    case
        rt.name
        when 'BOY'
        then 'Fall ' || left(dr.academic_year, 4)
        when 'MOY'
        then 'Winter ' || right(dr.academic_year, 4)
        when 'EOY'
        then 'Spring ' || right(dr.academic_year, 4)
    end as test_round_date,

    cwo.sublevel_name as sa_proj_lvl,
    cwo.sublevel_number as sa_proj_lvl_num,

    cwt.sublevel_name as sa_proj_lvl_typ,
    cwt.sublevel_number as sa_proj_lvl_typ_num,
    cwt.sublevel_name as sa_proj_lvl_str,
    cwt.sublevel_number as sa_proj_lvl_str_num,

    row_number() over (
        partition by dr.student_id, dr.academic_year, dr.subject, rt.name
        order by dr.completion_date desc
    ) as rn_subj_round,

    row_number() over (
        partition by dr.student_id, dr.academic_year, dr.subject
        order by dr.completion_date desc
    ) as rn_subj_year,
from {{ ref("stg_iready__diagnostic_results") }} as dr
left join {{ ref("stg_people__location_crosswalk") }} as lc on dr.school = lc.name
left join
    {{ ref("stg_reporting__terms") }} as rt
    on dr.completion_date between rt.start_date and rt.end_date
    and lc.region = rt.region
    and rt.type = 'IR'
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwo
    on dr.overall_scale_score between cwo.scale_low and cwo.scale_high
    and dr.subject = cwo.test_name
    and dr.student_grade = cwo.grade_level_string
    and dr.state_assessment_type = cwo.destination_system
    and cwo.source_system = 'i-Ready'
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwt
    on dr.overall_scale_score_plus_typical_growth
    between cwt.scale_low and cwt.scale_high
    and dr.subject = cwt.test_name
    and dr.student_grade = cwt.grade_level_string
    and dr.state_assessment_type = cwt.destination_system
    and cwt.source_system = 'i-Ready'
    {#
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cws
    on ir.overall_scale_score_plus_stretch_growth between cws.scale_low and
    cws.scale_high
    and ir.subject = cws.test_name
    and ir.grade_level = cws.grade_level
    and ir.destination_system = cws.destination_system
    and cws.source_system = 'i-Ready' 
#}
    
