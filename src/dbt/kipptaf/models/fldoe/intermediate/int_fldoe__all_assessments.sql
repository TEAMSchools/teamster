with
    source as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_fldoe", "int_fldoe__all_assessments")]
            )
        }}
    ),

    scale_crosswalk as (
        select
            administration_window,
            academic_year,

            'FAST_NEW' as source_system,
            'FL' as destination_system,

        from
            unnest(
                generate_array(2023, {{ var("current_academic_year") }})
            ) as academic_year
        cross join unnest(['PM1', 'PM2', 'PM3']) as administration_window

        union all

        select
            administration_window,

            2022 as academic_year,
            'FAST' as source_system,
            'FL' as destination_system,

        from unnest(['PM1', 'PM2']) as administration_window

        union all

        select
            'PM3' as administration_window,
            2022 as academic_year,
            'FAST_NEW' as source_system,
            'FL' as destination_system,
    )

select
    fl._dbt_source_relation,
    fl.test_code,
    fl.academic_year,
    fl.administration_window,
    fl.season,
    fl.discipline,
    fl.assessment_subject,
    fl.scale_score,
    fl.achievement_level,
    fl.is_proficient,
    fl.assessment_grade,
    fl.performance_level,
    fl.student_id,
    fl.assessment_name,
    fl.performance_level as achievement_level_int,
    fl.student_number,

    {{ extract_code_location("fl") }} as _dbt_source_project,

    cw1.sublevel_number,
    cw1.sublevel_name,

    'Actual' as results_type,
    'KTAF FL' as district_state,

    case
        when fl.test_code = 'ALG01' and fl.assessment_grade = '8'
        then concat(fl.test_code, '_', 'MS')
        when fl.test_code = 'ALG01' and fl.assessment_grade in ('9', '10', '11', '12')
        then concat(fl.test_code, '_', 'HS')
        else fl.test_code
    end as aligned_level_test_code,

    case
        when fl.assessment_subject like 'English Language Arts%'
        then 'Text Study'
        when fl.assessment_subject in ('Algebra I', 'Algebra II', 'Geometry')
        then 'Mathematics'
        else fl.assessment_subject
    end as illuminate_subject,

    case
        when fl.performance_level = 1
        then 'Below/Far Below'
        when fl.performance_level = 2
        then 'Approaching'
        when fl.performance_level >= 3
        then 'At/Above'
    end as fast_aggregated_proficiency,

    case
        when fl.performance_level = 1
        then 'Not Proficient (1)'
        when fl.performance_level = 2
        then 'Bubble (2)'
        when fl.performance_level >= 3
        then 'Proficient (3-5)'
    end as fast_performance_band_group_label,

    case
        when fl.achievement_level in ('Inadequate', 'Level 1')
        then 'Lvl 1'
        when fl.achievement_level in ('Below Satisfactory', 'Level 2')
        then 'Lvl 2'
        when fl.achievement_level in ('Satisfactory', 'Level 3')
        then 'Lvl 3'
        when fl.achievement_level in ('Proficient', 'Level 4')
        then 'Lvl 4'
        when fl.achievement_level in ('Mastery', 'Level 5')
        then 'Lvl 5'
    end as aligned_performance_band_group,

    if(fl.is_proficient, 1, 0) as is_proficient_int,

    if(fl.performance_level = 2, 1, 0) as is_approaching_int,

    if(fl.performance_level < 2, 1, 0) as is_below_int,

    if(cw1.sublevel_number >= 6, null, cw2.scale_low) as scale_for_proficiency,

    if(
        cw1.sublevel_number >= 6, null, cw2.scale_low - fl.scale_score
    ) as points_to_proficiency,

    if(cw1.sublevel_number = 8, null, cw1.scale_high + 1) as scale_for_growth,

    if(
        cw1.sublevel_number = 8, null, (cw1.scale_high + 1) - fl.scale_score
    ) as points_to_growth,

    lag(fl.scale_score, 1) over (
        partition by fl.student_id, fl.academic_year, fl.assessment_subject
        order by fl.administration_window asc
    ) as scale_score_prev,

    case
        fl.assessment_name
        when 'FAST'
        then 'state_fl_fast'
        when 'FSA'
        then 'state_fl_fsa'
        when 'EOC'
        then 'state_fl_eoc'
        when 'Science'
        then 'state_fl_science'
        else 'state_fl_unknown'
    end as assessment_type,
from source as fl
left join
    scale_crosswalk as sc
    on fl.academic_year = sc.academic_year
    and fl.administration_window = sc.administration_window
/* gets FL sublevels & scale for growth */
left join
    {{ ref("stg_google_sheets__iready__crosswalk") }} as cw1
    on sc.source_system = cw1.source_system
    and sc.destination_system = cw1.destination_system
    and fl.assessment_subject = cw1.test_name
    and fl.assessment_grade = cw1.grade_level_string
    and fl.scale_score between cw1.scale_low and cw1.scale_high
/* gets proficient scale score for current-year scores */
left join
    {{ ref("stg_google_sheets__iready__crosswalk") }} as cw2
    on sc.source_system = cw2.source_system
    and sc.destination_system = cw2.destination_system
    and fl.assessment_subject = cw2.test_name
    and fl.assessment_grade = cw2.grade_level_string
    and cw2.sublevel_number = 6
