with
    benchmark_student_summary as (
        select
            * except (
                client_date,
                composite_score,
                decoding_nwf_wrc_score,
                letter_names_lnf_score,
                letter_sounds_nwf_cls_score,
                phonemic_awareness_psf_score,
                reading_accuracy_orf_accu_score,
                reading_comprehension_maze_score,
                reading_fluency_orf_score,
                sync_date,
                word_reading_wrf_score
            ),

            /* score */
            cast(decoding_nwf_wrc_score as numeric) as decoding_nwf_wrc_score,
            cast(letter_names_lnf_score as numeric) as letter_names_lnf_score,
            cast(letter_sounds_nwf_cls_score as numeric) as letter_sounds_nwf_cls_score,
            cast(
                phonemic_awareness_psf_score as numeric
            ) as phonemic_awareness_psf_score,
            cast(
                reading_accuracy_orf_accu_score as numeric
            ) as reading_accuracy_orf_accu_score,
            cast(
                reading_comprehension_maze_score as numeric
            ) as reading_comprehension_maze_score,
            cast(reading_fluency_orf_score as numeric) as reading_fluency_orf_score,
            cast(word_reading_wrf_score as numeric) as word_reading_wrf_score,
            cast(composite_score as numeric) as composite_score,

            cast(client_date as date) as client_date,
            cast(sync_date as date) as sync_date,

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

    ),

    transformations as (
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
                decoding_nwf_wrc_national_norm_percentile
                in ('Tested Out', 'Discontinued'),
                decoding_nwf_wrc_national_norm_percentile,
                decoding_nwf_wrc_level
            ) as decoding_nwf_wrc_level,

            if(
                letter_names_lnf_national_norm_percentile
                in ('Tested Out', 'Discontinued'),
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
                reading_fluency_orf_national_norm_percentile
                in ('Tested Out', 'Discontinued'),
                reading_fluency_orf_national_norm_percentile,
                reading_fluency_orf_level
            ) as reading_fluency_orf_level,

            if(
                word_reading_wrf_national_norm_percentile
                in ('Tested Out', 'Discontinued'),
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
                letter_sounds_nwf_cls_national_norm_percentile = 'Tested Out',
                true,
                false
            ) as letter_sounds_nwf_cls_tested_out,

            if(
                phonemic_awareness_psf_national_norm_percentile = 'Tested Out',
                true,
                false
            ) as phonemic_awareness_psf_tested_out,

            if(
                reading_accuracy_orf_accu_national_norm_percentile = 'Tested Out',
                true,
                false
            ) as reading_accuracy_orf_accu_tested_out,

            if(
                reading_comprehension_maze_national_norm_percentile = 'Tested Out',
                true,
                false
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
                letter_sounds_nwf_cls_national_norm_percentile = 'Discontinued',
                true,
                false
            ) as letter_sounds_nwf_cls_discontinued,

            if(
                phonemic_awareness_psf_national_norm_percentile = 'Discontinued',
                true,
                false
            ) as phonemic_awareness_psf_discontinued,

            if(
                reading_accuracy_orf_accu_national_norm_percentile = 'Discontinued',
                true,
                false
            ) as reading_accuracy_orf_accu_discontinued,

            if(
                reading_comprehension_maze_national_norm_percentile = 'Discontinued',
                true,
                false
            ) as reading_comprehension_maze_discontinued,

            if(
                reading_fluency_orf_national_norm_percentile = 'Discontinued',
                true,
                false
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
    )

select
    d.*,

    x.abbreviation as school,
    x.powerschool_school_id as schoolid,

    initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,

from transformations as d
left join {{ ref("stg_people__location_crosswalk") }} as x on d.school_name = x.name
