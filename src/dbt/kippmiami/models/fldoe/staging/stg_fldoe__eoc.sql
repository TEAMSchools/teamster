with
    eoc as (
        select
            _dagster_partition_grade_level_subject as test_name,
            student_id,
            local_id,
            student_name,
            student_dob,
            ethnicity,
            english_language_learner_ell_status,
            gender_k_12,
            gender_postsecondary_only,
            primary_exceptionality,
            section_504,
            enrolled_district,
            enrolled_school,
            date_taken,
            test_completion_date,
            test_oppnumber,
            test_reason,
            testing_location,
            field_1_origins_and_purposes_of_law_and_government_performance
            as origins_and_purposes_of_law_and_government_performance,
            field_2_roles_rights_and_responsibilities_of_citizens_performance
            as roles_rights_and_responsibilities_of_citizens_performance,
            field_3_government_policies_and_political_processes_performance
            as government_policies_and_political_processes_performance,
            field_4_organization_and_function_of_government_performance
            as organization_and_function_of_government_performance,
            field_1_expressions_functions_and_data_analysis_performance
            as expressions_functions_and_data_analysis_performance,
            field_2_linear_relationships_performance
            as linear_relationships_performance,
            field_3_non_linear_relationships_performance
            as non_linear_relationships_performance,

            'PM3' as administration_window,
            'Spring' as season,

            cast(_dagster_partition_school_year_term as int) as academic_year,
            cast(enrolled_grade as int) as enrolled_grade,

            coalesce(
                b_e_s_t_algebra_1_eoc_scale_score, civics_eoc_scale_score
            ) as scale_score,
            coalesce(
                b_e_s_t_algebra_1_eoc_achievement_level, civics_eoc_achievement_level
            ) as achievement_level,

            if(
                _dagster_partition_grade_level_subject = 'B.E.S.T.Algebra1',
                'Math',
                'Civics'
            ) as discipline,

            if(
                _dagster_partition_grade_level_subject = 'B.E.S.T.Algebra1',
                'Algebra I',
                'Civics'
            ) as assessment_subject,

            case
                _dagster_partition_grade_level_subject
                when 'B.E.S.T.Algebra1'
                then 'ALG01'
                when 'Civics'
                then 'SOC08'
            end as test_code,
        from {{ source("fldoe", "src_fldoe__eoc") }}
    ),

    with_achievement_level_int as (
        select
            * except (scale_score),

            cast(scale_score as int) as scale_score,

            cast(right(achievement_level, 1) as int) as achievement_level_int,
        from eoc
        where scale_score != 'Invalidated'
    )

select *, if(achievement_level_int >= 3, true, false) as is_proficient,
from with_achievement_level_int
