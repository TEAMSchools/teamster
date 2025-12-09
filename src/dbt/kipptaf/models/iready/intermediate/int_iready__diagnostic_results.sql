with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "stg_iready__diagnostic_results"),
                    source("kippmiami_iready", "stg_iready__diagnostic_results"),
                ]
            )
        }}
    ),

    transformations as (
        select
            dr.* except (_dbt_source_relation),

            lc.region,
            lc.abbreviation as school_abbreviation,
            lc.powerschool_school_id as schoolid,

            regexp_replace(
                dr._dbt_source_relation, r'kipp[a-z]+_', lc.dagster_code_location || '_'
            ) as _dbt_source_relation,

            case
                lc.dagster_code_location
                when 'kippnewark'
                then 'NJSLA'
                when 'kippcamden'
                then 'NJSLA'
                when 'kipppaterson'
                then 'NJSLA'
                when 'kippmiami'
                then 'FL'
            end as state_assessment_type,
        from union_relations as dr
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on dr.school = lc.name
    ),

    window_calcs as (
        select
            * except (
                most_recent_completion_date,
                most_recent_diagnostic_gain,
                most_recent_lexile_measure,
                most_recent_lexile_range,
                most_recent_overall_placement,
                most_recent_overall_relative_placement,
                most_recent_overall_scale_score,
                most_recent_rush_flag
            ),

            max(most_recent_overall_scale_score) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_overall_scale_score,

            max(most_recent_overall_relative_placement) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_overall_relative_placement,

            max(most_recent_overall_placement) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_overall_placement,

            max(most_recent_diagnostic_gain) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_diagnostic_gain,

            max(most_recent_lexile_measure) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_lexile_measure,

            max(most_recent_lexile_range) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_lexile_range,

            max(most_recent_rush_flag) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_rush_flag,

            max(most_recent_completion_date) over (
                partition by _dbt_source_relation, student_id, academic_year, subject
            ) as most_recent_completion_date,

            row_number() over (
                partition by _dbt_source_relation, student_id, academic_year, subject
                order by completion_date desc
            ) as rn_subj_year,
        from transformations
    )

select
    wc.*,

    cwo.sublevel_name as projected_sublevel,
    cwo.sublevel_number as projected_sublevel_number,
    cwo.is_proficient as projected_is_proficient,
    cwo.level as projected_level_number,

    cwr.sublevel_name as projected_sublevel_recent,
    cwr.sublevel_number as projected_sublevel_number_recent,
    cwr.is_proficient as projected_is_proficient_recent,
    cwr.level as projected_level_number_recent,

    cwt.sublevel_name as projected_sublevel_typical,
    cwt.sublevel_number as projected_sublevel_number_typical,
    cwt.is_proficient as projected_is_proficient_typical,
    cwt.level as projected_level_number_typical,

    cws.sublevel_name as projected_sublevel_stretch,
    cws.sublevel_number as projected_sublevel_number_stretch,
    cws.is_proficient as projected_is_proficient_stretch,
    cws.level as projected_level_number_stretch,

    cwi.sublevel_name as sublevel_with_typical,
    cwi.sublevel_number as sublevel_number_with_typical,
    cwi.is_proficient as is_proficient_with_typical,
    cwi.level as level_number_with_typical,

    cwp.scale_low as proficent_scale_score,

    coalesce(rt.name, 'Outside Round') as test_round,

    right(rt.code, 1) as round_number,

    case
        when wc.overall_relative_placement_int <= 2
        then 'Below/Far Below'
        when wc.overall_relative_placement_int = 3
        then 'Approaching'
        when wc.overall_relative_placement_int >= 4
        then 'At/Above'
    end as iready_proficiency,

    if(
        cwp.scale_low - wc.most_recent_overall_scale_score <= 0,
        0,
        cwp.scale_low - wc.most_recent_overall_scale_score
    ) as scale_points_to_proficiency,

    round(
        wc.most_recent_diagnostic_gain / wc.annual_typical_growth_measure, 2
    ) as progress_to_typical,

    round(
        wc.most_recent_diagnostic_gain / wc.annual_stretch_growth_measure, 2
    ) as progress_to_stretch,

    row_number() over (
        partition by
            wc._dbt_source_relation,
            wc.student_id,
            wc.academic_year,
            wc.subject,
            rt.name
        order by wc.completion_date desc
    ) as rn_subj_round,

from window_calcs as wc
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on wc.region = rt.region
    and wc.completion_date between rt.start_date and rt.end_date
    and rt.type = 'IR'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cwo
    on wc.subject = cwo.test_name
    and wc.student_grade = cwo.grade_level_string
    and wc.state_assessment_type = cwo.destination_system
    and wc.overall_scale_score between cwo.scale_low and cwo.scale_high
    and cwo.source_system = 'i-Ready'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cwr
    on wc.subject = cwr.test_name
    and wc.student_grade = cwr.grade_level_string
    and wc.state_assessment_type = cwr.destination_system
    and wc.most_recent_overall_scale_score between cwr.scale_low and cwr.scale_high
    and cwr.source_system = 'i-Ready'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cwt
    on wc.subject = cwt.test_name
    and wc.student_grade = cwt.grade_level_string
    and wc.state_assessment_type = cwt.destination_system
    and wc.overall_scale_score_plus_typical_growth
    between cwt.scale_low and cwt.scale_high
    and cwt.source_system = 'i-Ready'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cws
    on wc.subject = cws.test_name
    and wc.student_grade = cws.grade_level_string
    and wc.state_assessment_type = cws.destination_system
    and wc.overall_scale_score_plus_stretch_growth
    between cws.scale_low and cws.scale_high
    and cws.source_system = 'i-Ready'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cwi
    on wc.subject = cwi.test_name
    and wc.student_grade_int = cwi.grade_level
    and wc.overall_scale_score_plus_typical_growth
    between cwi.scale_low and cwi.scale_high
    and cwi.destination_system = 'i-Ready'
left join
    {{ ref("stg_google_sheets__assessments__iready_crosswalk") }} as cwp
    on wc.subject = cwp.test_name
    and wc.student_grade = cwp.grade_level_string
    and wc.state_assessment_type = cwp.destination_system
    and cwp.source_system = 'i-Ready'
    and cwp.sublevel_name = 'Level 3'
