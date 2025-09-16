select
    * except (
        student_primary_id,
        student_primary_id_studentnumber,
        device_date,
        sync_date,
        basic_comprehension_maze_score,
        composite_score,
        correct_responses_maze_score,
        decoding_nwf_wrc_score,
        error_rate_orf_score,
        incorrect_responses_maze_score,
        letter_names_lnf_score,
        letter_sounds_nwf_cls_score,
        oral_language_score,
        phonemic_awareness_psf_score,
        ran_score,
        reading_accuracy_orf_accu_score,
        reading_fluency_orf_score,
        spelling_score,
        vocabulary_score,
        word_reading_wrf_score,
        composite_local_percentile,
        letter_names_lnf_local_percentile,
        phonemic_awareness_psf_local_percentile,
        letter_sounds_nwf_cls_local_percentile,
        decoding_nwf_wrc_local_percentile,
        word_reading_wrf_local_percentile,
        reading_accuracy_orf_accu_local_percentile,
        reading_fluency_orf_local_percentile,
        basic_comprehension_maze_local_percentile,
        composite_national_norm_percentile,
        letter_names_lnf_national_norm_percentile,
        phonemic_awareness_psf_national_norm_percentile,
        letter_sounds_nwf_cls_national_norm_percentile,
        decoding_nwf_wrc_national_norm_percentile,
        word_reading_wrf_national_norm_percentile,
        reading_accuracy_orf_accu_national_norm_percentile,
        reading_fluency_orf_national_norm_percentile,
        basic_comprehension_maze_national_norm_percentile
    ),

    cast(left(school_year, 4) as int) as academic_year,
    cast(student_primary_id_studentnumber as int) as student_primary_id,

    cast(device_date as date) as device_date,
    cast(sync_date as date) as sync_date,

    -- scores
    cast(basic_comprehension_maze_score as numeric) as basic_comprehension_maze_score,
    cast(composite_score as numeric) as composite_score,
    cast(correct_responses_maze_score as numeric) as correct_responses_maze_score,
    cast(decoding_nwf_wrc_score as numeric) as decoding_nwf_wrc_score,
    cast(error_rate_orf_score as numeric) as error_rate_orf_score,
    cast(incorrect_responses_maze_score as numeric) as incorrect_responses_maze_score,
    cast(letter_names_lnf_score as numeric) as letter_names_lnf_score,
    cast(letter_sounds_nwf_cls_score as numeric) as letter_sounds_nwf_cls_score,
    cast(oral_language_score as numeric) as oral_language_score,
    cast(phonemic_awareness_psf_score as numeric) as phonemic_awareness_psf_score,
    cast(ran_score as numeric) as ran_score,
    cast(reading_accuracy_orf_accu_score as numeric) as reading_accuracy_orf_accu_score,
    cast(reading_fluency_orf_score as numeric) as reading_fluency_orf_score,
    cast(spelling_score as numeric) as spelling_score,
    cast(vocabulary_score as numeric) as vocabulary_score,
    cast(word_reading_wrf_score as numeric) as word_reading_wrf_score,

    if(
        assessment_grade = 'K', 0, safe_cast(assessment_grade as int)
    ) as assessment_grade_int,

    if(
        enrollment_grade = 'K', 0, safe_cast(enrollment_grade as int)
    ) as enrollment_grade_int,

    -- Tested Out
    if(
        composite_national_norm_percentile = 'Tested Out', true, false
    ) as composite_tested_out,

    if(
        decoding_nwf_wrc_national_norm_percentile = 'Tested Out', true, false
    ) as decoding_nwf_wrc_tested_out,

    if(
        letter_names_lnf_national_norm_percentile = 'Tested Out', true, false
    ) as letter_names_lnf_tested_out,

    if(
        letter_sounds_nwf_cls_national_norm_percentile = 'Tested Out', true, false
    ) as letter_sounds_nwf_cls_tested_out,

    if(
        phonemic_awareness_psf_national_norm_percentile = 'Tested Out', true, false
    ) as phonemic_awareness_psf_tested_out,

    if(
        reading_accuracy_orf_accu_national_norm_percentile = 'Tested Out', true, false
    ) as reading_accuracy_orf_accu_tested_out,

    if(
        basic_comprehension_maze_national_norm_percentile = 'Tested Out', true, false
    ) as basic_comprehension_maze_tested_out,

    if(
        reading_fluency_orf_national_norm_percentile = 'Tested Out', true, false
    ) as reading_fluency_orf_tested_out,

    if(
        word_reading_wrf_national_norm_percentile = 'Tested Out', true, false
    ) as word_reading_wrf_tested_out,

    -- Discontinued
    if(
        composite_national_norm_percentile = 'Discontinued', true, false
    ) as composite_discontinued,
    if(
        decoding_nwf_wrc_national_norm_percentile = 'Discontinued', true, false
    ) as decoding_nwf_wrc_discontinued,
    if(
        letter_names_lnf_national_norm_percentile = 'Discontinued', true, false
    ) as letter_names_lnf_discontinued,
    if(
        letter_sounds_nwf_cls_national_norm_percentile = 'Discontinued', true, false
    ) as letter_sounds_nwf_cls_discontinued,
    if(
        phonemic_awareness_psf_national_norm_percentile = 'Discontinued', true, false
    ) as phonemic_awareness_psf_discontinued,
    if(
        reading_accuracy_orf_accu_national_norm_percentile = 'Discontinued', true, false
    ) as reading_accuracy_orf_accu_discontinued,
    if(
        basic_comprehension_maze_national_norm_percentile = 'Discontinued', true, false
    ) as basic_comprehension_maze_discontinued,
    if(
        reading_fluency_orf_national_norm_percentile = 'Discontinued', true, false
    ) as reading_fluency_orf_discontinued,
    if(
        word_reading_wrf_national_norm_percentile = 'Discontinued', true, false
    ) as word_reading_wrf_discontinued,

    -- Local Percentiles
    safe_cast(composite_local_percentile as numeric) as composite_local_percentile,
    safe_cast(
        letter_names_lnf_local_percentile as numeric
    ) as letter_names_lnf_local_percentile,
    safe_cast(
        phonemic_awareness_psf_local_percentile as numeric
    ) as phonemic_awareness_psf_local_percentile,
    safe_cast(
        letter_sounds_nwf_cls_local_percentile as numeric
    ) as letter_sounds_nwf_cls_local_percentile,
    safe_cast(
        decoding_nwf_wrc_local_percentile as numeric
    ) as decoding_nwf_wrc_local_percentile,
    safe_cast(
        word_reading_wrf_local_percentile as numeric
    ) as word_reading_wrf_local_percentile,
    safe_cast(
        reading_accuracy_orf_accu_local_percentile as numeric
    ) as reading_accuracy_orf_accu_local_percentile,
    safe_cast(
        reading_fluency_orf_local_percentile as numeric
    ) as reading_fluency_orf_local_percentile,
    safe_cast(
        basic_comprehension_maze_local_percentile as numeric
    ) as basic_comprehension_maze_local_percentile,

    -- National Percentiles
    safe_cast(
        composite_national_norm_percentile as numeric
    ) as composite_national_norm_percentile,
    safe_cast(
        letter_names_lnf_national_norm_percentile as numeric
    ) as letter_names_lnf_national_norm_percentile,
    safe_cast(
        phonemic_awareness_psf_national_norm_percentile as numeric
    ) as phonemic_awareness_psf_national_norm_percentile,
    safe_cast(
        letter_sounds_nwf_cls_national_norm_percentile as numeric
    ) as letter_sounds_nwf_cls_national_norm_percentile,
    safe_cast(
        decoding_nwf_wrc_national_norm_percentile as numeric
    ) as decoding_nwf_wrc_national_norm_percentile,
    safe_cast(
        word_reading_wrf_national_norm_percentile as numeric
    ) as word_reading_wrf_national_norm_percentile,
    safe_cast(
        reading_accuracy_orf_accu_national_norm_percentile as numeric
    ) as reading_accuracy_orf_accu_national_norm_percentile,
    safe_cast(
        reading_fluency_orf_national_norm_percentile as numeric
    ) as reading_fluency_orf_national_norm_percentile,
    safe_cast(
        basic_comprehension_maze_national_norm_percentile as numeric
    ) as basic_comprehension_maze_national_norm_percentile,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_primary_id_studentnumber",
                "school_year",
                "benchmark_period",
                "assessment_grade",
            ]
        )
    }} as surrogate_key,
from {{ source("amplify", "src_amplify__mclass__sftp__benchmark_student_summary") }}
