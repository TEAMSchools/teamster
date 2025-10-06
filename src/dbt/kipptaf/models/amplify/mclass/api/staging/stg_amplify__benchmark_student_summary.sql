with
    benchmark_student_summary as (
        select
            * except (
                client_date,
                composite_score,
                correct_responses_maze_score,
                decoding_nwf_wrc_score,
                error_rate_orf_score,
                incorrect_responses_maze_score,
                letter_names_lnf_score,
                letter_sounds_nwf_cls_score,
                phonemic_awareness_psf_score,
                primary_id_student_id_district_id,
                primary_id_student_number,
                ran_score,
                reading_accuracy_orf_accu_score,
                reading_comprehension_maze_score,
                reading_fluency_orf_score,
                spelling_score,
                student_id_district_id,
                student_primary_id,
                sync_date,
                vocabulary_score,
                word_reading_wrf_score
            ),

            cast(
                primary_id_student_id_district_id as int
            ) as primary_id_student_id_district_id,
            cast(student_primary_id as int) as student_primary_id,

            /* score */
            cast(decoding_nwf_wrc_score as numeric) as decoding_nwf_wrc_score,
            cast(letter_names_lnf_score as numeric) as letter_names_lnf_score,
            cast(letter_sounds_nwf_cls_score as numeric) as letter_sounds_nwf_cls_score,
            cast(
                phonemic_awareness_psf_score as numeric
            ) as phonemic_awareness_psf_score,
            cast(ran_score as numeric) as ran_score,
            cast(
                reading_accuracy_orf_accu_score as numeric
            ) as reading_accuracy_orf_accu_score,
            cast(
                reading_comprehension_maze_score as numeric
            ) as reading_comprehension_maze_score,
            cast(reading_fluency_orf_score as numeric) as reading_fluency_orf_score,
            cast(word_reading_wrf_score as numeric) as word_reading_wrf_score,
            cast(composite_score as numeric) as composite_score,
            cast(
                correct_responses_maze_score as numeric
            ) as correct_responses_maze_score,
            cast(error_rate_orf_score as numeric) as error_rate_orf_score,
            cast(
                incorrect_responses_maze_score as numeric
            ) as incorrect_responses_maze_score,
            cast(spelling_score as numeric) as spelling_score,
            cast(vocabulary_score as numeric) as vocabulary_score,

            cast(client_date as date) as client_date,
            cast(sync_date as date) as sync_date,

            cast(
                cast(student_id_district_id as numeric) as int
            ) as student_id_district_id,
            cast(
                cast(primary_id_student_number as numeric) as int
            ) as primary_id_student_number,

            cast(left(school_year, 4) as int) as academic_year,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "student_primary_id",
                        "school_year",
                        "benchmark_period",
                        "assessment_grade",
                    ]
                )
            }} as surrogate_key,

        from {{ source("amplify", "src_amplify__benchmark_student_summary") }}
    )

select
    * except (
        composite_level,
        decoding_nwf_wrc_level,
        letter_names_lnf_level,
        letter_sounds_nwf_cls_level,
        phonemic_awareness_psf_level,
        reading_accuracy_orf_accu_level,
        reading_comprehension_maze_level,
        reading_fluency_orf_level,
        word_reading_wrf_level,
        composite_national_norm_percentile,
        decoding_nwf_wrc_national_norm_percentile,
        letter_names_lnf_national_norm_percentile,
        letter_sounds_nwf_cls_national_norm_percentile,
        phonemic_awareness_psf_national_norm_percentile,
        reading_accuracy_orf_accu_national_norm_percentile,
        reading_comprehension_maze_national_norm_percentile,
        reading_fluency_orf_national_norm_percentile,
        word_reading_wrf_national_norm_percentile
    ),

    safe_cast(
        composite_national_norm_percentile as numeric
    ) as composite_national_norm_percentile,
    safe_cast(
        decoding_nwf_wrc_national_norm_percentile as numeric
    ) as decoding_nwf_wrc_national_norm_percentile,
    safe_cast(
        letter_names_lnf_national_norm_percentile as numeric
    ) as letter_names_lnf_national_norm_percentile,
    safe_cast(
        letter_sounds_nwf_cls_national_norm_percentile as numeric
    ) as letter_sounds_nwf_cls_national_norm_percentile,
    safe_cast(
        phonemic_awareness_psf_national_norm_percentile as numeric
    ) as phonemic_awareness_psf_national_norm_percentile,
    safe_cast(
        reading_accuracy_orf_accu_national_norm_percentile as numeric
    ) as reading_accuracy_orf_accu_national_norm_percentile,
    safe_cast(
        reading_comprehension_maze_national_norm_percentile as numeric
    ) as reading_comprehension_maze_national_norm_percentile,
    safe_cast(
        reading_fluency_orf_national_norm_percentile as numeric
    ) as reading_fluency_orf_national_norm_percentile,
    safe_cast(
        word_reading_wrf_national_norm_percentile as numeric
    ) as word_reading_wrf_national_norm_percentile,

    if(
        composite_national_norm_percentile in ('Tested Out', 'Discontinued'),
        composite_national_norm_percentile,
        composite_level
    ) as composite_level,

    if(
        decoding_nwf_wrc_national_norm_percentile in ('Tested Out', 'Discontinued'),
        decoding_nwf_wrc_national_norm_percentile,
        decoding_nwf_wrc_level
    ) as decoding_nwf_wrc_level,

    if(
        letter_names_lnf_national_norm_percentile in ('Tested Out', 'Discontinued'),
        letter_names_lnf_national_norm_percentile,
        letter_names_lnf_level
    ) as letter_names_lnf_level,

    if(
        letter_sounds_nwf_cls_national_norm_percentile
        in ('Tested Out', 'Discontinued'),
        letter_sounds_nwf_cls_national_norm_percentile,
        letter_sounds_nwf_cls_level
    ) as letter_sounds_nwf_cls_level,

    if(
        phonemic_awareness_psf_national_norm_percentile
        in ('Tested Out', 'Discontinued'),
        phonemic_awareness_psf_national_norm_percentile,
        phonemic_awareness_psf_level
    ) as phonemic_awareness_psf_level,

    if(
        reading_accuracy_orf_accu_national_norm_percentile
        in ('Tested Out', 'Discontinued'),
        reading_accuracy_orf_accu_national_norm_percentile,
        reading_accuracy_orf_accu_level
    ) as reading_accuracy_orf_accu_level,

    if(
        reading_comprehension_maze_national_norm_percentile
        in ('Tested Out', 'Discontinued'),
        reading_comprehension_maze_national_norm_percentile,
        reading_comprehension_maze_level
    ) as reading_comprehension_maze_level,

    if(
        reading_fluency_orf_national_norm_percentile in ('Tested Out', 'Discontinued'),
        reading_fluency_orf_national_norm_percentile,
        reading_fluency_orf_level
    ) as reading_fluency_orf_level,

    if(
        word_reading_wrf_national_norm_percentile in ('Tested Out', 'Discontinued'),
        word_reading_wrf_national_norm_percentile,
        word_reading_wrf_level
    ) as word_reading_wrf_level,

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
        reading_comprehension_maze_national_norm_percentile = 'Tested Out', true, false
    ) as reading_comprehension_maze_tested_out,

    if(
        reading_fluency_orf_national_norm_percentile = 'Tested Out', true, false
    ) as reading_fluency_orf_tested_out,

    if(
        word_reading_wrf_national_norm_percentile = 'Tested Out', true, false
    ) as word_reading_wrf_tested_out,

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
        reading_comprehension_maze_national_norm_percentile = 'Discontinued',
        true,
        false
    ) as reading_comprehension_maze_discontinued,

    if(
        reading_fluency_orf_national_norm_percentile = 'Discontinued', true, false
    ) as reading_fluency_orf_discontinued,

    if(
        word_reading_wrf_national_norm_percentile = 'Discontinued', true, false
    ) as word_reading_wrf_discontinued,

    if(
        assessment_grade = 'K', 0, safe_cast(assessment_grade as int)
    ) as assessment_grade_int,

    if(
        enrollment_grade = 'K', 0, safe_cast(enrollment_grade as int)
    ) as enrollment_grade_int,

from benchmark_student_summary
