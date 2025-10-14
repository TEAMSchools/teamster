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
                when 'kippmiami'
                then 'FL'
            end as state_assessment_type,

            {# TODO: refactor calcs to iready package #}
            if(
                dr.student_grade = 'K', 0, cast(dr.student_grade as int)
            ) as student_grade_int,
            if(dr.subject = 'Reading', 'ELA', 'Math') as discipline,

            if(dr.overall_relative_placement_int >= 4, true, false) as is_proficient,
            if(
                dr.percent_progress_to_annual_typical_growth_percent >= 100, true, false
            ) as is_met_typical,
            if(
                dr.percent_progress_to_annual_stretch_growth_percent >= 100, true, false
            ) as is_met_stretch,

            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.overall_scale_score, null
            ) as most_recent_overall_scale_score,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y',
                dr.overall_relative_placement,
                null
            ) as most_recent_overall_relative_placement,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.overall_placement, null
            ) as most_recent_overall_placement,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.diagnostic_gain, null
            ) as most_recent_diagnostic_gain,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.lexile_measure, null
            ) as most_recent_lexile_measure,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.lexile_range, null
            ) as most_recent_lexile_range,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.rush_flag, null
            ) as most_recent_rush_flag,
            if(
                dr.most_recent_diagnostic_ytd_y_n = 'Y', dr.completion_date, null
            ) as most_recent_completion_date,
        from union_relations as dr
        left join
            {{ ref("stg_people__location_crosswalk") }} as lc on dr.school = lc.name
    )

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
