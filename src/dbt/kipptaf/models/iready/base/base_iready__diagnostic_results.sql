with
    diagnostic_results as (
        select
            student_id,
            academic_year,
            academic_year_int,
            state_assessment_type,
            school,
            student_grade,
            subject,
            start_date,
            completion_date,
            baseline_diagnostic_y_n,
            most_recent_diagnostic_ytd_y_n,
            overall_scale_score,
            overall_scale_score_plus_typical_growth,
            overall_scale_score_plus_stretch_growth,
            percentile,
            overall_relative_placement,
            overall_relative_placement_int,
            placement_3_level,
            rush_flag,
            mid_on_grade_level_scale_score,
            percent_progress_to_annual_typical_growth_percent,
            percent_progress_to_annual_stretch_growth_percent,
            diagnostic_gain,
            annual_typical_growth_measure,
            annual_stretch_growth_measure,
            overall_placement,

            max(
                if(most_recent_diagnostic_ytd_y_n = 'Y', overall_scale_score, null)
            ) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_overall_scale_score,
            max(
                if(
                    most_recent_diagnostic_ytd_y_n = 'Y',
                    overall_relative_placement,
                    null
                )
            ) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_overall_relative_placement,
            max(
                if(most_recent_diagnostic_ytd_y_n = 'Y', overall_placement, null)
            ) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_overall_placement,
            max(if(most_recent_diagnostic_ytd_y_n = 'Y', diagnostic_gain, null)) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_diagnostic_gain,
            max(if(most_recent_diagnostic_ytd_y_n = 'Y', lexile_measure, null)) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_lexile_measure,
            max(if(most_recent_diagnostic_ytd_y_n = 'Y', lexile_range, null)) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_lexile_range,
            max(if(most_recent_diagnostic_ytd_y_n = 'Y', rush_flag, null)) over (
                partition by student_id, academic_year, subject
                order by completion_date asc
            ) as most_recent_rush_flag,

            row_number() over (
                partition by student_id, academic_year, subject
                order by completion_date desc
            ) as rn_subj_year,
        from {{ ref("stg_iready__diagnostic_results") }}
    )

select
    dr.student_id,
    dr.academic_year,
    dr.academic_year_int,
    dr.student_grade,
    dr.subject,
    dr.start_date,
    dr.completion_date,
    dr.baseline_diagnostic_y_n,
    dr.most_recent_diagnostic_ytd_y_n,
    dr.overall_scale_score,
    dr.percentile,
    dr.overall_placement,
    dr.overall_relative_placement,
    dr.overall_relative_placement_int,
    dr.placement_3_level,
    dr.rush_flag,
    dr.mid_on_grade_level_scale_score,
    dr.percent_progress_to_annual_typical_growth_percent,
    dr.percent_progress_to_annual_stretch_growth_percent,
    dr.diagnostic_gain,
    dr.annual_typical_growth_measure,
    dr.annual_stretch_growth_measure,
    dr.most_recent_overall_scale_score,
    dr.most_recent_overall_relative_placement,
    dr.most_recent_overall_placement,
    dr.most_recent_diagnostic_gain,
    dr.most_recent_lexile_measure,
    dr.most_recent_lexile_range,
    dr.most_recent_rush_flag,
    dr.rn_subj_year,

    lc.region,
    lc.abbreviation as school_abbreviation,

    cwo.sublevel_name as projected_sublevel,
    cwo.sublevel_number as projected_sublevel_number,

    cwr.sublevel_name as projected_sublevel_recent,
    cwr.sublevel_number as projected_sublevel_number_recent,

    cwt.sublevel_name as projected_sublevel_typical,
    cwt.sublevel_number as projected_sublevel_number_typical,

    cws.sublevel_name as projected_sublevel_stretch,
    cws.sublevel_number as projected_sublevel_number_stretch,

    cwp.scale_low as proficent_scale_score,

    round(
        dr.most_recent_diagnostic_gain / dr.annual_typical_growth_measure, 2
    ) as progress_to_typical,
    round(
        dr.most_recent_diagnostic_gain / dr.annual_stretch_growth_measure, 2
    ) as progress_to_stretch,

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

    if(
        cwp.scale_low - dr.most_recent_overall_scale_score <= 0,
        0,
        cwp.scale_low - dr.most_recent_overall_scale_score
    ) as scale_points_to_proficiency,

    row_number() over (
        partition by dr.student_id, dr.academic_year, dr.subject, rt.name
        order by dr.completion_date desc
    ) as rn_subj_round,
from diagnostic_results as dr
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
    {{ ref("stg_assessments__iready_crosswalk") }} as cwr
    on dr.most_recent_overall_scale_score between cwr.scale_low and cwr.scale_high
    and dr.subject = cwr.test_name
    and dr.student_grade = cwr.grade_level_string
    and dr.state_assessment_type = cwr.destination_system
    and cwr.source_system = 'i-Ready'
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwt
    on dr.overall_scale_score_plus_typical_growth
    between cwt.scale_low and cwt.scale_high
    and dr.subject = cwt.test_name
    and dr.student_grade = cwt.grade_level_string
    and dr.state_assessment_type = cwt.destination_system
    and cwt.source_system = 'i-Ready'
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cws
    on dr.overall_scale_score_plus_stretch_growth
    between cws.scale_low and cws.scale_high
    and dr.subject = cws.test_name
    and dr.student_grade = cws.grade_level_string
    and dr.state_assessment_type = cws.destination_system
    and cws.source_system = 'i-Ready'
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cwp
    on dr.subject = cwp.test_name
    and dr.student_grade = cwp.grade_level_string
    and dr.state_assessment_type = cwp.destination_system
    and cwp.source_system = 'i-Ready'
    and cwp.sublevel_name = 'Level 3'
