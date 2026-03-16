with
    state_assessment_union as (
        select
            _dbt_source_relation,
            academic_year,
            localstudentidentifier,
            statestudentidentifier as state_id,
            assessment_name,
            discipline,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,
            testperformancelevel_text as performance_band,
            test_grade,
            lep_status as state_lep_status,
            is_504 as state_is_504,
            iep_status as state_iep_status,
            race_ethnicity as state_race_ethnicity,

            'Actual' as results_type,

            if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as `subject`,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as test_code,

        from {{ ref("int_pearson__all_assessments") }}
        where
            academic_year >= {{ var("current_academic_year") - 7 }}
            and testscalescore is not null

        union all

        select
            _dbt_source_relation,
            academic_year,
            null as localstudentidentifier,
            student_id as state_id,
            assessment_name,
            discipline,
            scale_score as score,
            performance_level as performance_band_level,
            is_proficient,
            achievement_level as performance_band,
            cast(assessment_grade as int) as test_grade,
            null as state_lep_status,
            null as state_is_504,
            null as state_iep_status,
            null as state_race_ethnicity,

            'Actual' as results_type,

            administration_window as `admin`,

            season,

            assessment_subject as `subject`,

            test_code,

        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    )

select
    _dbt_source_relation,
    academic_year,
    localstudentidentifier,
    state_id,
    assessment_name,
    discipline,
    score,
    performance_band_level,
    is_proficient,
    performance_band,
    test_grade,
    state_lep_status,
    state_is_504,
    state_iep_status,
    state_race_ethnicity,
    results_type,
    `admin`,
    season,
    `subject`,
    test_code,

    {{
        dbt_utils.generate_surrogate_key(
            ["_dbt_source_relation", "state_id", "academic_year", "admin", "subject"]
        )
    }} as state_assessments_key,
from state_assessment_union
