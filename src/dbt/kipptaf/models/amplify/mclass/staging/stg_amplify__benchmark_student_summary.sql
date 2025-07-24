with
    benchmark_student_summary as (
        select
            * except (
                assessment_grade,
                client_date,
                composite_level,
                composite_national_norm_percentile,
                composite_score,
                composite_semester_growth,
                composite_year_growth,
                decoding_nwf_wrc_level,
                decoding_nwf_wrc_national_norm_percentile,
                decoding_nwf_wrc_score,
                decoding_nwf_wrc_semester_growth,
                decoding_nwf_wrc_year_growth,
                enrollment_grade,
                letter_names_lnf_level,
                letter_names_lnf_national_norm_percentile,
                letter_names_lnf_score,
                letter_names_lnf_semester_growth,
                letter_names_lnf_year_growth,
                letter_sounds_nwf_cls_level,
                letter_sounds_nwf_cls_national_norm_percentile,
                letter_sounds_nwf_cls_score,
                letter_sounds_nwf_cls_semester_growth,
                letter_sounds_nwf_cls_year_growth,
                official_teacher_staff_id,
                phonemic_awareness_psf_level,
                phonemic_awareness_psf_national_norm_percentile,
                phonemic_awareness_psf_score,
                phonemic_awareness_psf_semester_growth,
                phonemic_awareness_psf_year_growth,
                reading_accuracy_orf_accu_level,
                reading_accuracy_orf_accu_national_norm_percentile,
                reading_accuracy_orf_accu_score,
                reading_accuracy_orf_accu_semester_growth,
                reading_accuracy_orf_accu_year_growth,
                reading_comprehension_maze_level,
                reading_comprehension_maze_national_norm_percentile,
                reading_comprehension_maze_score,
                reading_comprehension_maze_semester_growth,
                reading_comprehension_maze_year_growth,
                reading_fluency_orf_level,
                reading_fluency_orf_national_norm_percentile,
                reading_fluency_orf_score,
                reading_fluency_orf_semester_growth,
                reading_fluency_orf_year_growth,
                sync_date,
                word_reading_wrf_level,
                word_reading_wrf_national_norm_percentile,
                word_reading_wrf_score,
                word_reading_wrf_semester_growth,
                word_reading_wrf_year_growth,
                name,
                clean_name,
                grade_band,
                region,
                abbreviation,
                powerschool_school_id,
                deanslist_school_id,
                reporting_school_id,
                is_campus,
                is_pathways,
                dagster_code_location,
                head_of_schools_employee_number
            ),

            x.abbreviation as school,
            x.powerschool_school_id as schoolid,

            initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,

            cast(left(s.school_year, 4) as int) as academic_year,

            /* score */
            cast(s.decoding_nwf_wrc_score as numeric) as decoding_nwf_wrc_score,
            cast(s.letter_names_lnf_score as numeric) as letter_names_lnf_score,
            cast(
                s.letter_sounds_nwf_cls_score as numeric
            ) as letter_sounds_nwf_cls_score,
            cast(
                s.phonemic_awareness_psf_score as numeric
            ) as phonemic_awareness_psf_score,
            cast(
                s.reading_accuracy_orf_accu_score as numeric
            ) as reading_accuracy_orf_accu_score,
            cast(
                s.reading_comprehension_maze_score as numeric
            ) as reading_comprehension_maze_score,
            cast(s.reading_fluency_orf_score as numeric) as reading_fluency_orf_score,
            cast(s.word_reading_wrf_score as numeric) as word_reading_wrf_score,

            /* level */
            cast(s.composite_level as string) as composite_level,
            cast(s.decoding_nwf_wrc_level as string) as decoding_nwf_wrc_level,
            cast(s.letter_names_lnf_level as string) as letter_names_lnf_level,
            cast(
                s.letter_sounds_nwf_cls_level as string
            ) as letter_sounds_nwf_cls_level,
            cast(
                s.phonemic_awareness_psf_level as string
            ) as phonemic_awareness_psf_level,
            cast(
                s.reading_accuracy_orf_accu_level as string
            ) as reading_accuracy_orf_accu_level,
            cast(
                s.reading_comprehension_maze_level as string
            ) as reading_comprehension_maze_level,
            cast(s.reading_fluency_orf_level as string) as reading_fluency_orf_level,
            cast(s.word_reading_wrf_level as string) as word_reading_wrf_level,

            /* semester growth */
            cast(s.composite_semester_growth as string) as composite_semester_growth,
            cast(
                s.decoding_nwf_wrc_semester_growth as string
            ) as decoding_nwf_wrc_semester_growth,
            cast(
                s.letter_names_lnf_semester_growth as string
            ) as letter_names_lnf_semester_growth,
            cast(
                s.letter_sounds_nwf_cls_semester_growth as string
            ) as letter_sounds_nwf_cls_semester_growth,
            cast(
                s.phonemic_awareness_psf_semester_growth as string
            ) as phonemic_awareness_psf_semester_growth,
            cast(
                s.reading_accuracy_orf_accu_semester_growth as string
            ) as reading_accuracy_orf_accu_semester_growth,
            cast(
                s.reading_comprehension_maze_semester_growth as string
            ) as reading_comprehension_maze_semester_growth,
            cast(
                s.reading_fluency_orf_semester_growth as string
            ) as reading_fluency_orf_semester_growth,
            cast(
                s.word_reading_wrf_semester_growth as string
            ) as word_reading_wrf_semester_growth,

            /* year growth */
            cast(s.composite_year_growth as string) as composite_year_growth,
            cast(
                s.decoding_nwf_wrc_year_growth as string
            ) as decoding_nwf_wrc_year_growth,
            cast(
                s.letter_names_lnf_year_growth as string
            ) as letter_names_lnf_year_growth,
            cast(
                s.letter_sounds_nwf_cls_year_growth as string
            ) as letter_sounds_nwf_cls_year_growth,
            cast(
                s.phonemic_awareness_psf_year_growth as string
            ) as phonemic_awareness_psf_year_growth,
            cast(
                s.reading_accuracy_orf_accu_year_growth as string
            ) as reading_accuracy_orf_accu_year_growth,
            cast(
                s.reading_comprehension_maze_year_growth as string
            ) as reading_comprehension_maze_year_growth,
            cast(
                s.reading_fluency_orf_year_growth as string
            ) as reading_fluency_orf_year_growth,
            cast(
                s.word_reading_wrf_year_growth as string
            ) as word_reading_wrf_year_growth,

            /* national norm percentile */
            cast(
                s.composite_national_norm_percentile as string
            ) as composite_national_norm_percentile,
            cast(
                s.reading_comprehension_maze_national_norm_percentile as string
            ) as reading_comprehension_maze_national_norm_percentile,
            cast(
                s.decoding_nwf_wrc_national_norm_percentile as string
            ) as decoding_nwf_wrc_national_norm_percentile,
            cast(
                s.letter_sounds_nwf_cls_national_norm_percentile as string
            ) as letter_sounds_nwf_cls_national_norm_percentile,
            cast(
                s.word_reading_wrf_national_norm_percentile as string
            ) as word_reading_wrf_national_norm_percentile,

            date(s.client_date) as client_date,
            date(s.sync_date) as sync_date,

            coalesce(
                s.assessment_grade.string_value,
                cast(s.assessment_grade.long_value as string)
            ) as assessment_grade,

            coalesce(
                s.enrollment_grade.string_value,
                cast(s.enrollment_grade.long_value as string)
            ) as enrollment_grade,

            coalesce(
                s.official_teacher_staff_id.string_value,
                cast(s.official_teacher_staff_id.long_value as string),
                cast(s.official_teacher_staff_id.double_value as string)
            ) as official_teacher_staff_id,

            coalesce(
                cast(s.composite_score.double_value as numeric),
                cast(s.composite_score.long_value as numeric)
            ) as composite_score,

            coalesce(
                s.reading_accuracy_orf_accu_national_norm_percentile.string_value,
                cast(
                    s.reading_accuracy_orf_accu_national_norm_percentile.double_value
                    as string
                )
            ) as reading_accuracy_orf_accu_national_norm_percentile,

            coalesce(
                s.reading_fluency_orf_national_norm_percentile.string_value,
                cast(
                    s.reading_fluency_orf_national_norm_percentile.double_value
                    as string
                )
            ) as reading_fluency_orf_national_norm_percentile,

            coalesce(
                s.letter_names_lnf_national_norm_percentile.string_value,
                cast(s.letter_names_lnf_national_norm_percentile.double_value as string)
            ) as letter_names_lnf_national_norm_percentile,

            coalesce(
                s.phonemic_awareness_psf_national_norm_percentile.string_value,
                cast(
                    s.phonemic_awareness_psf_national_norm_percentile.double_value
                    as string
                )
            ) as phonemic_awareness_psf_national_norm_percentile,

        from {{ source("amplify", "src_amplify__benchmark_student_summary") }} as s
        left join
            {{ ref("stg_people__location_crosswalk") }} as x on s.school_name = x.name
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

from benchmark_student_summary
