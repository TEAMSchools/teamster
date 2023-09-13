{% set src_bss = source("amplify", "src_amplify__benchmark_student_summary") %}

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_primary_id", "school_year", "benchmark_period"]
        )
    }} as surrogate_key,

    {{
        dbt_utils.star(
            from=src_bss,
            except=[
                "client_date",
                "composite_level",
                "composite_national_norm_percentile",
                "composite_score",
                "composite_semester_growth",
                "composite_year_growth",
                "decoding_nwf_wrc_level",
                "decoding_nwf_wrc_national_norm_percentile",
                "decoding_nwf_wrc_score",
                "decoding_nwf_wrc_semester_growth",
                "decoding_nwf_wrc_year_growth",
                "letter_names_lnf_level",
                "letter_names_lnf_national_norm_percentile",
                "letter_names_lnf_score",
                "letter_names_lnf_semester_growth",
                "letter_names_lnf_year_growth",
                "letter_sounds_nwf_cls_level",
                "letter_sounds_nwf_cls_national_norm_percentile",
                "letter_sounds_nwf_cls_score",
                "letter_sounds_nwf_cls_semester_growth",
                "letter_sounds_nwf_cls_year_growth",
                "official_teacher_staff_id",
                "phonemic_awareness_psf_level",
                "phonemic_awareness_psf_national_norm_percentile",
                "phonemic_awareness_psf_score",
                "phonemic_awareness_psf_semester_growth",
                "phonemic_awareness_psf_year_growth",
                "reading_accuracy_orf_accu_level",
                "reading_accuracy_orf_accu_national_norm_percentile",
                "reading_accuracy_orf_accu_score",
                "reading_accuracy_orf_accu_semester_growth",
                "reading_accuracy_orf_accu_year_growth",
                "reading_comprehension_maze_level",
                "reading_comprehension_maze_national_norm_percentile",
                "reading_comprehension_maze_score",
                "reading_comprehension_maze_semester_growth",
                "reading_comprehension_maze_year_growth",
                "reading_fluency_orf_level",
                "reading_fluency_orf_national_norm_percentile",
                "reading_fluency_orf_score",
                "reading_fluency_orf_semester_growth",
                "reading_fluency_orf_year_growth",
                "sync_date",
                "word_reading_wrf_level",
                "word_reading_wrf_national_norm_percentile",
                "word_reading_wrf_score",
                "word_reading_wrf_semester_growth",
                "word_reading_wrf_year_growth",
            ],
        )
    }},

    safe_cast(client_date as date) as client_date,
    safe_cast(sync_date as date) as sync_date,

    safe_cast(left(school_year, 4) as int) as academic_year,

    coalesce(
        official_teacher_staff_id.string_value,
        safe_cast(official_teacher_staff_id.long_value as string)
    ) as official_teacher_staff_id,
    coalesce(
        safe_cast(composite_score.double_value as numeric),
        safe_cast(composite_score.long_value as numeric)
    ) as composite_score,

    safe_cast(decoding_nwf_wrc_score as numeric) as decoding_nwf_wrc_score,
    safe_cast(letter_names_lnf_score as numeric) as letter_names_lnf_score,
    safe_cast(letter_sounds_nwf_cls_score as numeric) as letter_sounds_nwf_cls_score,
    safe_cast(phonemic_awareness_psf_score as numeric) as phonemic_awareness_psf_score,
    safe_cast(
        reading_accuracy_orf_accu_score as numeric
    ) as reading_accuracy_orf_accu_score,
    safe_cast(
        reading_comprehension_maze_score as numeric
    ) as reading_comprehension_maze_score,
    safe_cast(reading_fluency_orf_score as numeric) as reading_fluency_orf_score,
    safe_cast(word_reading_wrf_score as numeric) as word_reading_wrf_score,

    safe_cast(composite_level as string) as composite_level,
    safe_cast(decoding_nwf_wrc_level as string) as decoding_nwf_wrc_level,
    safe_cast(letter_names_lnf_level as string) as letter_names_lnf_level,
    safe_cast(letter_sounds_nwf_cls_level as string) as letter_sounds_nwf_cls_level,
    safe_cast(phonemic_awareness_psf_level as string) as phonemic_awareness_psf_level,
    safe_cast(
        reading_accuracy_orf_accu_level as string
    ) as reading_accuracy_orf_accu_level,
    safe_cast(
        reading_comprehension_maze_level as string
    ) as reading_comprehension_maze_level,
    safe_cast(reading_fluency_orf_level as string) as reading_fluency_orf_level,
    safe_cast(word_reading_wrf_level as string) as word_reading_wrf_level,

    safe_cast(composite_semester_growth as string) as composite_semester_growth,
    safe_cast(
        decoding_nwf_wrc_semester_growth as string
    ) as decoding_nwf_wrc_semester_growth,
    safe_cast(
        letter_names_lnf_semester_growth as string
    ) as letter_names_lnf_semester_growth,
    safe_cast(
        letter_sounds_nwf_cls_semester_growth as string
    ) as letter_sounds_nwf_cls_semester_growth,
    safe_cast(
        phonemic_awareness_psf_semester_growth as string
    ) as phonemic_awareness_psf_semester_growth,
    safe_cast(
        reading_accuracy_orf_accu_semester_growth as string
    ) as reading_accuracy_orf_accu_semester_growth,
    safe_cast(
        reading_comprehension_maze_semester_growth as string
    ) as reading_comprehension_maze_semester_growth,
    safe_cast(
        reading_fluency_orf_semester_growth as string
    ) as reading_fluency_orf_semester_growth,
    safe_cast(
        word_reading_wrf_semester_growth as string
    ) as word_reading_wrf_semester_growth,

    safe_cast(composite_year_growth as string) as composite_year_growth,
    safe_cast(decoding_nwf_wrc_year_growth as string) as decoding_nwf_wrc_year_growth,
    safe_cast(letter_names_lnf_year_growth as string) as letter_names_lnf_year_growth,
    safe_cast(
        letter_sounds_nwf_cls_year_growth as string
    ) as letter_sounds_nwf_cls_year_growth,
    safe_cast(
        phonemic_awareness_psf_year_growth as string
    ) as phonemic_awareness_psf_year_growth,
    safe_cast(
        reading_accuracy_orf_accu_year_growth as string
    ) as reading_accuracy_orf_accu_year_growth,
    safe_cast(
        reading_comprehension_maze_year_growth as string
    ) as reading_comprehension_maze_year_growth,
    safe_cast(
        reading_fluency_orf_year_growth as string
    ) as reading_fluency_orf_year_growth,
    safe_cast(word_reading_wrf_year_growth as string) as word_reading_wrf_year_growth,

    safe_cast(
        composite_national_norm_percentile as numeric
    ) as composite_national_norm_percentile,
    coalesce(
        safe_cast(
            reading_accuracy_orf_accu_national_norm_percentile.double_value as numeric
        ),
        safe_cast(
            reading_accuracy_orf_accu_national_norm_percentile.string_value as numeric
        )
    ) as reading_accuracy_orf_accu_national_norm_percentile,
    safe_cast(
        reading_comprehension_maze_national_norm_percentile as numeric
    ) as reading_comprehension_maze_national_norm_percentile,
    coalesce(
        safe_cast(reading_fluency_orf_national_norm_percentile.double_value as numeric),
        safe_cast(reading_fluency_orf_national_norm_percentile.string_value as numeric)
    ) as reading_fluency_orf_national_norm_percentile,

    safe_cast(
        nullif(decoding_nwf_wrc_national_norm_percentile, 'Tested Out') as numeric
    ) as decoding_nwf_wrc_national_norm_percentile,
    coalesce(
        safe_cast(letter_names_lnf_national_norm_percentile.double_value as numeric),
        safe_cast(
            nullif(
                letter_names_lnf_national_norm_percentile.string_value, 'Tested Out'
            ) as numeric
        )
    ) as letter_names_lnf_national_norm_percentile,
    safe_cast(
        nullif(letter_sounds_nwf_cls_national_norm_percentile, 'Tested Out') as numeric
    ) as letter_sounds_nwf_cls_national_norm_percentile,
    coalesce(
        safe_cast(
            phonemic_awareness_psf_national_norm_percentile.double_value as numeric
        ),
        safe_cast(
            nullif(
                phonemic_awareness_psf_national_norm_percentile.string_value,
                'Tested Out'
            ) as numeric
        )
    ) as phonemic_awareness_psf_national_norm_percentile,
    safe_cast(
        nullif(word_reading_wrf_national_norm_percentile, 'Tested Out') as numeric
    ) as word_reading_wrf_national_norm_percentile,
from {{ src_bss }}
