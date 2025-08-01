with
    bm_unpivot as (
        select
            surrogate_key,

            /* unpivot cols */
            measure as measure_standard,
            score as measure_standard_score,
            `level` as measure_standard_level,
            national_norm_percentile as measure_percentile,
            semester_growth as measure_semester_growth,
            year_growth as measure_year_growth,

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Reading Comprehension (Maze)'
                then 'Comprehension'
                else regexp_extract(measure, r'\((.{3})')
            end as measure_name_code,

            case
                `level`
                when 'Above Benchmark'
                then 4
                when 'At Benchmark'
                then 3
                when 'Below Benchmark'
                then 2
                when 'Well Below Benchmark'
                then 1
            end as measure_standard_level_int,
        from
            {{ ref("stg_amplify__benchmark_student_summary") }} unpivot (
                (
                    `level`,
                    national_norm_percentile,
                    score,
                    semester_growth,
                    year_growth
                ) for measure in (
                    (
                        decoding_nwf_wrc_level,
                        decoding_nwf_wrc_national_norm_percentile,
                        decoding_nwf_wrc_score,
                        decoding_nwf_wrc_semester_growth,
                        decoding_nwf_wrc_year_growth
                    ) as 'Decoding (NWF-WRC)',
                    (
                        letter_names_lnf_level,
                        letter_names_lnf_national_norm_percentile,
                        letter_names_lnf_score,
                        letter_names_lnf_semester_growth,
                        letter_names_lnf_year_growth
                    ) as 'Letter Names (LNF)',
                    (
                        letter_sounds_nwf_cls_level,
                        letter_sounds_nwf_cls_national_norm_percentile,
                        letter_sounds_nwf_cls_score,
                        letter_sounds_nwf_cls_semester_growth,
                        letter_sounds_nwf_cls_year_growth
                    ) as 'Letter Sounds (NWF-CLS)',
                    (
                        phonemic_awareness_psf_level,
                        phonemic_awareness_psf_national_norm_percentile,
                        phonemic_awareness_psf_score,
                        phonemic_awareness_psf_semester_growth,
                        phonemic_awareness_psf_year_growth
                    ) as 'Phonemic Awareness (PSF)',
                    (
                        reading_accuracy_orf_accu_level,
                        reading_accuracy_orf_accu_national_norm_percentile,
                        reading_accuracy_orf_accu_score,
                        reading_accuracy_orf_accu_semester_growth,
                        reading_accuracy_orf_accu_year_growth
                    ) as 'Reading Accuracy (ORF-Accu)',
                    (
                        reading_comprehension_maze_level,
                        reading_comprehension_maze_national_norm_percentile,
                        reading_comprehension_maze_score,
                        reading_comprehension_maze_semester_growth,
                        reading_comprehension_maze_year_growth
                    ) as 'Reading Comprehension (Maze)',
                    (
                        reading_fluency_orf_level,
                        reading_fluency_orf_national_norm_percentile,
                        reading_fluency_orf_score,
                        reading_fluency_orf_semester_growth,
                        reading_fluency_orf_year_growth
                    ) as 'Reading Fluency (ORF)',
                    (
                        word_reading_wrf_level,
                        word_reading_wrf_national_norm_percentile,
                        word_reading_wrf_score,
                        word_reading_wrf_semester_growth,
                        word_reading_wrf_year_growth
                    ) as 'Word Reading (WRF)',
                    (
                        composite_level,
                        composite_national_norm_percentile,
                        composite_score,
                        composite_semester_growth,
                        composite_year_growth
                    ) as 'Composite'
                )
            )
    )

select
    *,
    case
        measure_name_code
        when 'LNF'
        then 'Letter Names'
        when 'PSF'
        then 'Phonological Awareness'
        when 'NWF'
        then 'Nonsense Word Fluency'
        when 'WRF'
        then 'Word Reading Fluency'
        when 'ORF'
        then 'Oral Reading Fluency'
        else measure_name_code
    end as measure_name,
from bm_unpivot
