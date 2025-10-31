select
    _dbt_source_relation,
    studentsdcid,

    name_column,
    values_column,

    if(values_column = 'N', true, false) as is_portfolio_eligible,
    if(values_column = 'M', true, false) as is_iep_eligible,
    if(values_column in ('M', 'N'), true, false) as met_requirement,

    case
        when name_column in ('graduation_pathway_ela', 'graduation_pathway_math')
        then 'Graduation Pathway'
        when name_column in ('state_assessment_name', 'math_state_assessment_name')
        then 'State Assessment Name'
        when
            name_column in (
                'access_test_format_override',
                'alternate_access',
                'asmt_alt_rep_paper',
                'asmt_alternate_location',
                'asmt_answer_masking',
                'asmt_answers_recorded_paper',
                'asmt_asl_video',
                'asmt_closed_caption_ela',
                'asmt_directions_aloud',
                'asmt_directions_clarified',
                'asmt_extended_time_math',
                'asmt_extended_time',
                'asmt_frequent_breaks',
                'asmt_human_signer',
                'asmt_humanreader_signer',
                'asmt_math_response_el',
                'asmt_math_response',
                'asmt_monitor_response',
                'asmt_non_screen_reader',
                'asmt_read_aloud',
                'asmt_refresh_braille_ela',
                'asmt_selected_response_ela',
                'asmt_small_group',
                'asmt_special_equip',
                'asmt_specified_area',
                'asmt_time_of_day',
                'asmt_unique_accommodation',
                'asmt_word_prediction',
                'calculation_device_math_tools',
                'parcc_constructed_response_ela',
                'parcc_ell_paper_accom',
                'parcc_large_print_paper',
                'parcc_text_to_speech_math',
                'parcc_text_to_speech',
                'parcc_translation_math_paper'
            )
        then 'Accomodation'
    end as value_type,

    case
        when name_column in ('graduation_pathway_ela', 'state_assessment_name')
        then 'ELA'
        when name_column in ('graduation_pathway_math', 'math_state_assessment_name')
        then 'Math'
    end as discipline,

    max(if(name_column = 'math_state_assessment_name', values_column, null)) over (
        partition by _dbt_source_relation, studentsdcid
    ) as math_state_assessment_name,
    max(if(name_column = 'parcc_test_format', values_column, null)) over (
        partition by _dbt_source_relation, studentsdcid
    ) as parcc_test_format,
    max(if(name_column = 'state_assessment_name', values_column, null)) over (
        partition by _dbt_source_relation, studentsdcid
    ) as state_assessment_name,

    max(if(name_column = 'asmt_exclude_ela', cast(values_column as int), null)) over (
        partition by _dbt_source_relation, studentsdcid
    ) as asmt_exclude_ela,
    max(if(name_column = 'asmt_exclude_math', cast(values_column as int), null)) over (
        partition by _dbt_source_relation, studentsdcid
    ) as asmt_exclude_math,
from
    {{ ref("stg_powerschool__s_nj_stu_x") }} unpivot include nulls
    (
        values_column for name_column in (
            graduation_pathway_ela,
            graduation_pathway_math,
            math_state_assessment_name,
            state_assessment_name,
            access_test_format_override,
            alternate_access,
            asmt_alt_rep_paper,
            asmt_alternate_location,
            asmt_answer_masking,
            asmt_answers_recorded_paper,
            asmt_asl_video,
            asmt_closed_caption_ela,
            asmt_directions_aloud,
            asmt_directions_clarified,
            asmt_extended_time_math,
            asmt_extended_time,
            asmt_frequent_breaks,
            asmt_human_signer,
            asmt_humanreader_signer,
            asmt_math_response_el,
            asmt_math_response,
            asmt_monitor_response,
            asmt_non_screen_reader,
            asmt_read_aloud,
            asmt_refresh_braille_ela,
            asmt_selected_response_ela,
            asmt_small_group,
            asmt_special_equip,
            asmt_specified_area,
            asmt_time_of_day,
            asmt_unique_accommodation,
            asmt_word_prediction,
            calculation_device_math_tools,
            parcc_constructed_response_ela,
            parcc_ell_paper_accom,
            parcc_large_print_paper,
            parcc_text_to_speech_math,
            parcc_text_to_speech,
            parcc_translation_math_paper
        )
    )
