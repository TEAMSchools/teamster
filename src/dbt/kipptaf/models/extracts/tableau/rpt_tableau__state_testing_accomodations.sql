with
    accommodations_unpivot as (
        select
            _dbt_source_relation,
            studentsdcid,
            asmt_exclude_ela,
            asmt_exclude_math,
            math_state_assessment_name,
            parcc_test_format,
            state_assessment_name,

            -- unpivot fields
            accommodation,
            accommodation_value,
        from
            {{ ref("stg_powerschool__s_nj_stu_x") }} unpivot include nulls
            (
                accommodation_value for accommodation in (
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
    )

select
    co.student_number,
    co.state_studentnumber,
    co.lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.school_name,
    co.grade_level,
    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.spedlep as iep_status,
    co.special_education_code as specialed_classification,
    co.lep_status,
    co.is_504 as c_504_status,

    ac.asmt_exclude_ela,
    ac.asmt_exclude_math,
    ac.math_state_assessment_name,
    ac.parcc_test_format,
    ac.state_assessment_name,
    ac.accommodation,
    ac.accommodation_value,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    accommodations_unpivot as ac
    on co.students_dcid = ac.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ac") }}
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.region in ('Newark', 'Camden')
