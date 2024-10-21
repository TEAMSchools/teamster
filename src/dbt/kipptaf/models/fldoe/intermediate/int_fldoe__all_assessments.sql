with
    source as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_fldoe", model.name)]
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
    fl.*,

    cw1.sublevel_number,
    cw1.sublevel_name,

    cast(regexp_extract(fl.achievement_level, r'\d+') as int) as achievement_level_int,

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
from source as fl
left join
    scale_crosswalk as sc
    on fl.academic_year = sc.academic_year
    and fl.administration_window = sc.administration_window
/* gets FL sublevels & scale for growth */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw1
    on sc.source_system = cw1.source_system
    and sc.destination_system = cw1.destination_system
    and fl.assessment_subject = cw1.test_name
    and fl.assessment_grade = cw1.grade_level_string
    and fl.scale_score between cw1.scale_low and cw1.scale_high
/* gets proficient scale score for current-year scores */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw2
    on sc.source_system = cw2.source_system
    and sc.destination_system = cw2.destination_system
    and fl.assessment_subject = cw2.test_name
    and fl.assessment_grade = cw2.grade_level_string
    and cw2.sublevel_number = 6
