with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_fldoe__eoc"),
                    ref("stg_fldoe__fast"),
                    ref("stg_fldoe__science"),
                    source("fldoe", "stg_fldoe__fsa"),
                ]
            )
        }}
    ),

    transformed as (
        select
            test_code,
            academic_year,
            administration_window,
            season,
            discipline,
            assessment_subject,
            scale_score,
            achievement_level,
            is_proficient,
            performance_level as achievement_level_int,

            cast(
                coalesce(assessment_grade, test_grade, enrolled_grade) as string
            ) as assessment_grade,

            coalesce(student_id, fleid) as student_id,

            regexp_extract(
                _dbt_source_relation, r'stg_fldoe__(\w+)'
            ) as assessment_name,

        from union_relations
    )

select
    * except (assessment_name),

    'Actual' as results_type,
    'KTAF FL' as district_state,

    if(
        assessment_name = 'science', 'Science', upper(assessment_name)
    ) as assessment_name,

    case
        when assessment_subject like 'English Language Arts%'
        then 'Text Study'
        when assessment_subject in ('Algebra I', 'Algebra II', 'Geometry')
        then 'Mathematics'
        else assessment_subject
    end as illuminate_subject,

    case
        when achievement_level_int = 1
        then 'Below/Far Below'
        when achievement_level_int = 2
        then 'Approaching'
        when achievement_level_int >= 3
        then 'At/Above'
    end as fast_aggregated_proficiency,

from transformed
