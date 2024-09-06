with
    df_unpivot as (
        select
            student_id,
            academic_year,

            `date`,
            form,
            `remote`,
            score,
            benchmark_status,
            national_dds_percentile,
            district_percentile,
            school_percentile,

            split(name_column, '|')[0] as measure,
            split(name_column, '|')[1] as assessment_period,
        from
            {{ ref("stg_amplify__dibels_data_farming") }} unpivot (
                (
                    `date`,
                    form,
                    `remote`,
                    score,
                    benchmark_status,
                    national_dds_percentile,
                    district_percentile,
                    school_percentile
                ) for name_column in (
                    (
                        date_composite_beginning,
                        form_composite_beginning,
                        remote_composite_beginning,
                        composite_beginning,
                        benchmark_status_composite_beginning,
                        national_dds_percentile_composite_beginning,
                        district_percentile_composite_beginning,
                        school_percentile_composite_beginning
                    ) as 'Composite|Beginning',
                    (
                        date_composite_middle,
                        form_composite_middle,
                        remote_composite_middle,
                        composite_middle,
                        benchmark_status_composite_middle,
                        national_dds_percentile_composite_middle,
                        district_percentile_composite_middle,
                        school_percentile_composite_middle
                    ) as 'Composite|Middle',
                    (
                        date_composite_end,
                        form_composite_end,
                        remote_composite_end,
                        composite_end,
                        benchmark_status_composite_end,
                        national_dds_percentile_composite_end,
                        district_percentile_composite_end,
                        school_percentile_composite_end
                    ) as 'Composite|End',
                    (
                        date_maze_adjusted_beginning,
                        form_maze_adjusted_beginning,
                        remote_maze_adjusted_beginning,
                        maze_adjusted_beginning,
                        benchmark_status_maze_adjusted_beginning,
                        national_dds_percentile_maze_adjusted_beginning,
                        district_percentile_maze_adjusted_beginning,
                        school_percentile_maze_adjusted_beginning
                    ) as 'Reading Comprehension (Maze)|Beginning',
                    (
                        date_maze_adjusted_middle,
                        form_maze_adjusted_middle,
                        remote_maze_adjusted_middle,
                        maze_adjusted_middle,
                        benchmark_status_maze_adjusted_middle,
                        national_dds_percentile_maze_adjusted_middle,
                        district_percentile_maze_adjusted_middle,
                        school_percentile_maze_adjusted_middle
                    ) as 'Reading Comprehension (Maze)|Middle',
                    (
                        date_maze_adjusted_end,
                        form_maze_adjusted_end,
                        remote_maze_adjusted_end,
                        maze_adjusted_end,
                        benchmark_status_maze_adjusted_end,
                        national_dds_percentile_maze_adjusted_end,
                        district_percentile_maze_adjusted_end,
                        school_percentile_maze_adjusted_end
                    ) as 'Reading Comprehension (Maze)|End',
                    (
                        date_maze_correct_beginning,
                        form_maze_correct_beginning,
                        remote_maze_correct_beginning,
                        maze_correct_beginning,
                        benchmark_status_maze_correct_beginning,
                        national_dds_percentile_maze_correct_beginning,
                        district_percentile_maze_correct_beginning,
                        school_percentile_maze_correct_beginning
                    ) as 'maze_correct|Beginning',
                    (
                        date_maze_correct_middle,
                        form_maze_correct_middle,
                        remote_maze_correct_middle,
                        maze_correct_middle,
                        benchmark_status_maze_correct_middle,
                        national_dds_percentile_maze_correct_middle,
                        district_percentile_maze_correct_middle,
                        school_percentile_maze_correct_middle
                    ) as 'maze_correct|Middle',
                    (
                        date_maze_correct_end,
                        form_maze_correct_end,
                        remote_maze_correct_end,
                        maze_correct_end,
                        benchmark_status_maze_correct_end,
                        national_dds_percentile_maze_correct_end,
                        district_percentile_maze_correct_end,
                        school_percentile_maze_correct_end
                    ) as 'maze_correct|End',
                    (
                        date_maze_incorrect_beginning,
                        form_maze_incorrect_beginning,
                        remote_maze_incorrect_beginning,
                        maze_incorrect_beginning,
                        benchmark_status_maze_incorrect_beginning,
                        national_dds_percentile_maze_incorrect_beginning,
                        district_percentile_maze_incorrect_beginning,
                        school_percentile_maze_incorrect_beginning
                    ) as 'maze_incorrect|Beginning',
                    (
                        date_maze_incorrect_middle,
                        form_maze_incorrect_middle,
                        remote_maze_incorrect_middle,
                        maze_incorrect_middle,
                        benchmark_status_maze_incorrect_middle,
                        national_dds_percentile_maze_incorrect_middle,
                        district_percentile_maze_incorrect_middle,
                        school_percentile_maze_incorrect_middle
                    ) as 'maze_incorrect|Middle',
                    (
                        date_maze_incorrect_end,
                        form_maze_incorrect_end,
                        remote_maze_incorrect_end,
                        maze_incorrect_end,
                        benchmark_status_maze_incorrect_end,
                        national_dds_percentile_maze_incorrect_end,
                        district_percentile_maze_incorrect_end,
                        school_percentile_maze_incorrect_end
                    ) as 'maze_incorrect|End',
                    (
                        date_orf_accuracy_beginning,
                        form_orf_accuracy_beginning,
                        remote_orf_accuracy_beginning,
                        orf_accuracy_beginning,
                        benchmark_status_orf_accuracy_beginning,
                        national_dds_percentile_orf_accuracy_beginning,
                        district_percentile_orf_accuracy_beginning,
                        school_percentile_orf_accuracy_beginning
                    ) as 'Reading Fluency (ORF)|Beginning',
                    (
                        date_orf_accuracy_middle,
                        form_orf_accuracy_middle,
                        remote_orf_accuracy_middle,
                        orf_accuracy_middle,
                        benchmark_status_orf_accuracy_middle,
                        national_dds_percentile_orf_accuracy_middle,
                        district_percentile_orf_accuracy_middle,
                        school_percentile_orf_accuracy_middle
                    ) as 'Reading Fluency (ORF)|Middle',
                    (
                        date_orf_accuracy_end,
                        form_orf_accuracy_end,
                        remote_orf_accuracy_end,
                        orf_accuracy_end,
                        benchmark_status_orf_accuracy_end,
                        national_dds_percentile_orf_accuracy_end,
                        district_percentile_orf_accuracy_end,
                        school_percentile_orf_accuracy_end
                    ) as 'Reading Fluency (ORF)|End',
                    (
                        date_orf_wordscorrect_beginning,
                        form_orf_wordscorrect_beginning,
                        remote_orf_wordscorrect_beginning,
                        orf_wordscorrect_beginning,
                        benchmark_status_orf_wordscorrect_beginning,
                        national_dds_percentile_orf_wordscorrect_beginning,
                        district_percentile_orf_wordscorrect_beginning,
                        school_percentile_orf_wordscorrect_beginning
                    ) as 'orf_wordscorrect|Beginning',
                    (
                        date_orf_wordscorrect_middle,
                        form_orf_wordscorrect_middle,
                        remote_orf_wordscorrect_middle,
                        orf_wordscorrect_middle,
                        benchmark_status_orf_wordscorrect_middle,
                        national_dds_percentile_orf_wordscorrect_middle,
                        district_percentile_orf_wordscorrect_middle,
                        school_percentile_orf_wordscorrect_middle
                    ) as 'orf_wordscorrect|Middle',
                    (
                        date_orf_wordscorrect_end,
                        form_orf_wordscorrect_end,
                        remote_orf_wordscorrect_end,
                        orf_wordscorrect_end,
                        benchmark_status_orf_wordscorrect_end,
                        national_dds_percentile_orf_wordscorrect_end,
                        district_percentile_orf_wordscorrect_end,
                        school_percentile_orf_wordscorrect_end
                    ) as 'orf_wordscorrect|End',
                    (
                        date_orf_errors_beginning,
                        form_orf_errors_beginning,
                        remote_orf_errors_beginning,
                        orf_errors_beginning,
                        benchmark_status_orf_errors_beginning,
                        national_dds_percentile_orf_errors_beginning,
                        district_percentile_orf_errors_beginning,
                        school_percentile_orf_errors_beginning
                    ) as 'orf_errors|Beginning',
                    (
                        date_orf_errors_middle,
                        form_orf_errors_middle,
                        remote_orf_errors_middle,
                        orf_errors_middle,
                        benchmark_status_orf_errors_middle,
                        national_dds_percentile_orf_errors_middle,
                        district_percentile_orf_errors_middle,
                        school_percentile_orf_errors_middle
                    ) as 'orf_errors|Middle',
                    (
                        date_orf_errors_end,
                        form_orf_errors_end,
                        remote_orf_errors_end,
                        orf_errors_end,
                        benchmark_status_orf_errors_end,
                        national_dds_percentile_orf_errors_end,
                        district_percentile_orf_errors_end,
                        school_percentile_orf_errors_end
                    ) as 'orf_errors|End'
                )
            )
    )

select
    *,

    case
        assessment_period
        when 'Beginning'
        then 'BOY'
        when 'Middle'
        then 'MOY'
        when 'End'
        then 'EOY'
    end as mclass_period,

    case
        benchmark_status
        when 'Core^ Support'
        then 'Above Benchmark'
        when 'Core Support'
        then 'At Benchmark'
        when 'Strategic Support'
        then 'Below Benchmark'
        when 'Intensive Support'
        then 'Well Below Benchmark'
    end as mclass_measure_level,

    case
        benchmark_status
        when 'Core^ Support'
        then 4
        when 'Core Support'
        then 3
        when 'Strategic Support'
        then 2
        when 'Intensive Support'
        then 1
    end as mclass_measure_level_int,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_id", "academic_year", "assessment_period"]
        )
    }} as surrogate_key,
from df_unpivot
