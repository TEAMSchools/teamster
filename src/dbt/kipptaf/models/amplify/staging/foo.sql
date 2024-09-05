select
    student_id,

    _dagster_partition_fiscal_year - 1 as academic_year,

    coalesce(form_maze_7th_beginning, form_maze_8th_beginning) as form_maze_beginning,
    coalesce(form_maze_7th_middle, form_maze_8th_middle) as form_maze_middle,
    coalesce(form_maze_7th_end, form_maze_8th_end) as form_maze_end,
    coalesce(form_orf_7th_beginning, form_orf_8th_beginning) as form_orf_beginning,
    coalesce(form_orf_7th_middle, form_orf_8th_middle) as form_orf_middle,
    coalesce(form_orf_7th_end, form_orf_8th_end) as form_orf_end,

    coalesce(composite_7th_beginning, composite_8th_beginning) as composite_beginning,
    coalesce(composite_7th_end, composite_8th_end) as composite_end,
    coalesce(composite_7th_middle, composite_8th_middle) as composite_middle,

    coalesce(
        benchmark_status_composite_7th_beginning,
        benchmark_status_composite_8th_beginning
    ) as benchmark_status_composite_beginning,
    coalesce(
        benchmark_status_composite_7th_end, benchmark_status_composite_8th_end
    ) as benchmark_status_composite_end,
    coalesce(
        benchmark_status_composite_7th_middle, benchmark_status_composite_8th_middle
    ) as benchmark_status_composite_middle,
    coalesce(
        benchmark_status_maze_adjusted_7th_beginning,
        benchmark_status_maze_adjusted_8th_beginning
    ) as benchmark_status_maze_adjusted_beginning,
    coalesce(
        benchmark_status_maze_adjusted_7th_end, benchmark_status_maze_adjusted_8th_end
    ) as benchmark_status_maze_adjusted_end,
    coalesce(
        benchmark_status_maze_adjusted_7th_middle,
        benchmark_status_maze_adjusted_8th_middle
    ) as benchmark_status_maze_adjusted_middle,
    coalesce(
        benchmark_status_orf_accuracy_7th_beginning,
        benchmark_status_orf_accuracy_8th_beginning
    ) as benchmark_status_orf_accuracy_beginning,
    coalesce(
        benchmark_status_orf_accuracy_7th_end, benchmark_status_orf_accuracy_8th_end
    ) as benchmark_status_orf_accuracy_end,
    coalesce(
        benchmark_status_orf_accuracy_7th_middle,
        benchmark_status_orf_accuracy_8th_middle
    ) as benchmark_status_orf_accuracy_middle,
    coalesce(
        benchmark_status_orf_wordscorrect_7th_beginning,
        benchmark_status_orf_wordscorrect_8th_beginning
    ) as benchmark_status_orf_wordscorrect_beginning,
    coalesce(
        benchmark_status_orf_wordscorrect_7th_end,
        benchmark_status_orf_wordscorrect_8th_end
    ) as benchmark_status_orf_wordscorrect_end,
    coalesce(
        benchmark_status_orf_wordscorrect_7th_middle,
        benchmark_status_orf_wordscorrect_8th_middle
    ) as benchmark_status_orf_wordscorrect_middle,

    coalesce(
        maze_adjusted_7th_beginning, maze_adjusted_8th_beginning
    ) as maze_adjusted_beginning,
    coalesce(maze_adjusted_7th_end, maze_adjusted_8th_end) as maze_adjusted_end,
    coalesce(
        maze_adjusted_7th_middle, maze_adjusted_8th_middle
    ) as maze_adjusted_middle,

    coalesce(
        maze_correct_7th_beginning, maze_correct_8th_beginning
    ) as maze_correct_beginning,
    coalesce(maze_correct_7th_end, maze_correct_8th_end) as maze_correct_end,
    coalesce(maze_correct_7th_middle, maze_correct_8th_middle) as maze_correct_middle,

    coalesce(
        maze_incorrect_7th_beginning, maze_incorrect_8th_beginning
    ) as maze_incorrect_beginning,
    coalesce(maze_incorrect_7th_end, maze_incorrect_8th_end) as maze_incorrect_end,
    coalesce(
        maze_incorrect_7th_middle, maze_incorrect_8th_middle
    ) as maze_incorrect_middle,

    coalesce(
        orf_accuracy_7th_beginning, orf_accuracy_8th_beginning
    ) as orf_accuracy_beginning,
    coalesce(orf_accuracy_7th_end, orf_accuracy_8th_end) as orf_accuracy_end,
    coalesce(orf_accuracy_7th_middle, orf_accuracy_8th_middle) as orf_accuracy_middle,

    coalesce(
        orf_errors_7th_beginning, orf_errors_8th_beginning
    ) as orf_errors_beginning,
    coalesce(orf_errors_7th_end, orf_errors_8th_end) as orf_errors_end,
    coalesce(orf_errors_7th_middle, orf_errors_8th_middle) as orf_errors_middle,

    coalesce(
        orf_wordscorrect_7th_beginning, orf_wordscorrect_8th_beginning
    ) as orf_wordscorrect_beginning,
    coalesce(
        orf_wordscorrect_7th_end, orf_wordscorrect_8th_end
    ) as orf_wordscorrect_end,
    coalesce(
        orf_wordscorrect_7th_middle, orf_wordscorrect_8th_middle
    ) as orf_wordscorrect_middle,

    coalesce(
        remote_maze_7th_beginning, remote_maze_8th_beginning
    ) as remote_maze_beginning,
    coalesce(remote_maze_7th_end, remote_maze_8th_end) as remote_maze_end,
    coalesce(remote_maze_7th_middle, remote_maze_8th_middle) as remote_maze_middle,

    coalesce(
        remote_orf_7th_beginning, remote_orf_8th_beginning
    ) as remote_orf_beginning,
    coalesce(remote_orf_7th_end, remote_orf_8th_end) as remote_orf_end,
    coalesce(remote_orf_7th_middle, remote_orf_8th_middle) as remote_orf_middle,

    coalesce(
        growth_goal_composite_7th_end, growth_goal_composite_8th_end
    ) as growth_goal_composite_end,
    coalesce(
        growth_goal_met_composite_7th_end, growth_goal_met_composite_8th_end
    ) as growth_goal_met_composite_end,
    coalesce(
        growth_goal_type_composite_7th_end, growth_goal_type_composite_8th_end
    ) as growth_goal_type_composite_end,

    coalesce(
        growth_percentile_composite_7th_end, growth_percentile_composite_8th_end
    ) as growth_percentile_composite_end,

    coalesce(
        months_of_growth_composite_7th_end, months_of_growth_composite_8th_end
    ) as months_of_growth_composite_end,

    coalesce(
        national_dds_percentile_composite_7th_beginning,
        national_dds_percentile_composite_8th_beginning
    ) as national_dds_percentile_composite_beginning,
    coalesce(
        national_dds_percentile_composite_7th_end,
        national_dds_percentile_composite_8th_end
    ) as national_dds_percentile_composite_end,
    coalesce(
        national_dds_percentile_composite_7th_middle,
        national_dds_percentile_composite_8th_middle
    ) as national_dds_percentile_composite_middle,
    coalesce(
        national_dds_percentile_maze_adjusted_7th_beginning,
        national_dds_percentile_maze_adjusted_8th_beginning
    ) as national_dds_percentile_maze_adjusted_beginning,
    coalesce(
        national_dds_percentile_maze_adjusted_7th_end,
        national_dds_percentile_maze_adjusted_8th_end
    ) as national_dds_percentile_maze_adjusted_end,
    coalesce(
        national_dds_percentile_maze_adjusted_7th_middle,
        national_dds_percentile_maze_adjusted_8th_middle
    ) as national_dds_percentile_maze_adjusted_middle,
    coalesce(
        national_dds_percentile_orf_accuracy_7th_beginning,
        national_dds_percentile_orf_accuracy_8th_beginning
    ) as national_dds_percentile_orf_accuracy_beginning,
    coalesce(
        national_dds_percentile_orf_accuracy_7th_end,
        national_dds_percentile_orf_accuracy_8th_end
    ) as national_dds_percentile_orf_accuracy_end,
    coalesce(
        national_dds_percentile_orf_accuracy_7th_middle,
        national_dds_percentile_orf_accuracy_8th_middle
    ) as national_dds_percentile_orf_accuracy_middle,
    coalesce(
        national_dds_percentile_orf_wordscorrect_7th_beginning,
        national_dds_percentile_orf_wordscorrect_8th_beginning
    ) as national_dds_percentile_orf_wordscorrect_beginning,
    coalesce(
        national_dds_percentile_orf_wordscorrect_7th_end,
        national_dds_percentile_orf_wordscorrect_8th_end
    ) as national_dds_percentile_orf_wordscorrect_end,
    coalesce(
        national_dds_percentile_orf_wordscorrect_7th_middle,
        national_dds_percentile_orf_wordscorrect_8th_middle
    ) as national_dds_percentile_orf_wordscorrect_middle,

    coalesce(
        district_percentile_composite_7th_beginning,
        district_percentile_composite_8th_beginning
    ) as district_percentile_composite_beginning,
    coalesce(
        district_percentile_composite_7th_end, district_percentile_composite_8th_end
    ) as district_percentile_composite_end,
    coalesce(
        district_percentile_composite_7th_middle,
        district_percentile_composite_8th_middle
    ) as district_percentile_composite_middle,
    coalesce(
        district_percentile_maze_adjusted_7th_beginning,
        district_percentile_maze_adjusted_8th_beginning
    ) as district_percentile_maze_adjusted_beginning,
    coalesce(
        district_percentile_maze_adjusted_7th_end,
        district_percentile_maze_adjusted_8th_end
    ) as district_percentile_maze_adjusted_end,
    coalesce(
        district_percentile_maze_adjusted_7th_middle,
        district_percentile_maze_adjusted_8th_middle
    ) as district_percentile_maze_adjusted_middle,
    coalesce(
        district_percentile_maze_correct_7th_beginning,
        district_percentile_maze_correct_8th_beginning
    ) as district_percentile_maze_correct_beginning,
    coalesce(
        district_percentile_maze_correct_7th_end,
        district_percentile_maze_correct_8th_end
    ) as district_percentile_maze_correct_end,
    coalesce(
        district_percentile_maze_correct_7th_middle,
        district_percentile_maze_correct_8th_middle
    ) as district_percentile_maze_correct_middle,
    coalesce(
        district_percentile_maze_incorrect_7th_beginning,
        district_percentile_maze_incorrect_8th_beginning
    ) as district_percentile_maze_incorrect_beginning,
    coalesce(
        district_percentile_maze_incorrect_7th_end,
        district_percentile_maze_incorrect_8th_end
    ) as district_percentile_maze_incorrect_end,
    coalesce(
        district_percentile_maze_incorrect_7th_middle,
        district_percentile_maze_incorrect_8th_middle
    ) as district_percentile_maze_incorrect_middle,
    coalesce(
        district_percentile_orf_accuracy_7th_beginning,
        district_percentile_orf_accuracy_8th_beginning
    ) as district_percentile_orf_accuracy_beginning,
    coalesce(
        district_percentile_orf_accuracy_7th_end,
        district_percentile_orf_accuracy_8th_end
    ) as district_percentile_orf_accuracy_end,
    coalesce(
        district_percentile_orf_accuracy_7th_middle,
        district_percentile_orf_accuracy_8th_middle
    ) as district_percentile_orf_accuracy_middle,
    coalesce(
        district_percentile_orf_errors_7th_beginning,
        district_percentile_orf_errors_8th_beginning
    ) as district_percentile_orf_errors_beginning,
    coalesce(
        district_percentile_orf_errors_7th_end, district_percentile_orf_errors_8th_end
    ) as district_percentile_orf_errors_end,
    coalesce(
        district_percentile_orf_errors_7th_middle,
        district_percentile_orf_errors_8th_middle
    ) as district_percentile_orf_errors_middle,
    coalesce(
        district_percentile_orf_wordscorrect_7th_beginning,
        district_percentile_orf_wordscorrect_8th_beginning
    ) as district_percentile_orf_wordscorrect_beginning,
    coalesce(
        district_percentile_orf_wordscorrect_7th_end,
        district_percentile_orf_wordscorrect_8th_end
    ) as district_percentile_orf_wordscorrect_end,
    coalesce(
        district_percentile_orf_wordscorrect_7th_middle,
        district_percentile_orf_wordscorrect_8th_middle
    ) as district_percentile_orf_wordscorrect_middle,

    coalesce(
        school_percentile_composite_7th_beginning,
        school_percentile_composite_8th_beginning
    ) as school_percentile_composite_beginning,
    coalesce(
        school_percentile_composite_7th_end, school_percentile_composite_8th_end
    ) as school_percentile_composite_end,
    coalesce(
        school_percentile_composite_7th_middle, school_percentile_composite_8th_middle
    ) as school_percentile_composite_middle,
    coalesce(
        school_percentile_maze_adjusted_7th_beginning,
        school_percentile_maze_adjusted_8th_beginning
    ) as school_percentile_maze_adjusted_beginning,
    coalesce(
        school_percentile_maze_adjusted_7th_end, school_percentile_maze_adjusted_8th_end
    ) as school_percentile_maze_adjusted_end,
    coalesce(
        school_percentile_maze_adjusted_7th_middle,
        school_percentile_maze_adjusted_8th_middle
    ) as school_percentile_maze_adjusted_middle,
    coalesce(
        school_percentile_maze_correct_7th_beginning,
        school_percentile_maze_correct_8th_beginning
    ) as school_percentile_maze_correct_beginning,
    coalesce(
        school_percentile_maze_correct_7th_end, school_percentile_maze_correct_8th_end
    ) as school_percentile_maze_correct_end,
    coalesce(
        school_percentile_maze_correct_7th_middle,
        school_percentile_maze_correct_8th_middle
    ) as school_percentile_maze_correct_middle,
    coalesce(
        school_percentile_maze_incorrect_7th_beginning,
        school_percentile_maze_incorrect_8th_beginning
    ) as school_percentile_maze_incorrect_beginning,
    coalesce(
        school_percentile_maze_incorrect_7th_end,
        school_percentile_maze_incorrect_8th_end
    ) as school_percentile_maze_incorrect_end,
    coalesce(
        school_percentile_maze_incorrect_7th_middle,
        school_percentile_maze_incorrect_8th_middle
    ) as school_percentile_maze_incorrect_middle,
    coalesce(
        school_percentile_orf_accuracy_7th_beginning,
        school_percentile_orf_accuracy_8th_beginning
    ) as school_percentile_orf_accuracy_beginning,
    coalesce(
        school_percentile_orf_accuracy_7th_end, school_percentile_orf_accuracy_8th_end
    ) as school_percentile_orf_accuracy_end,
    coalesce(
        school_percentile_orf_accuracy_7th_middle,
        school_percentile_orf_accuracy_8th_middle
    ) as school_percentile_orf_accuracy_middle,
    coalesce(
        school_percentile_orf_errors_7th_beginning,
        school_percentile_orf_errors_8th_beginning
    ) as school_percentile_orf_errors_beginning,
    coalesce(
        school_percentile_orf_errors_7th_end, school_percentile_orf_errors_8th_end
    ) as school_percentile_orf_errors_end,
    coalesce(
        school_percentile_orf_errors_7th_middle, school_percentile_orf_errors_8th_middle
    ) as school_percentile_orf_errors_middle,
    coalesce(
        school_percentile_orf_wordscorrect_7th_beginning,
        school_percentile_orf_wordscorrect_8th_beginning
    ) as school_percentile_orf_wordscorrect_beginning,
    coalesce(
        school_percentile_orf_wordscorrect_7th_end,
        school_percentile_orf_wordscorrect_8th_end
    ) as school_percentile_orf_wordscorrect_end,
    coalesce(
        school_percentile_orf_wordscorrect_7th_middle,
        school_percentile_orf_wordscorrect_8th_middle
    ) as school_percentile_orf_wordscorrect_middle,

    parse_date(
        '%Y/%m/%d', coalesce(date_composite_7th_beginning, date_composite_8th_beginning)
    ) as date_composite_beginning,
    parse_date(
        '%Y/%m/%d', coalesce(date_composite_7th_middle, date_composite_8th_middle)
    ) as date_composite_middle,
    parse_date(
        '%Y/%m/%d', coalesce(date_composite_7th_end, date_composite_8th_end)
    ) as date_composite_end,
    parse_date(
        '%Y/%m/%d', coalesce(date_maze_7th_beginning, date_maze_8th_beginning)
    ) as date_maze_beginning,
    parse_date(
        '%Y/%m/%d', coalesce(date_maze_7th_middle, date_maze_8th_middle)
    ) as date_maze_middle,
    parse_date(
        '%Y/%m/%d', coalesce(date_maze_7th_end, date_maze_8th_end)
    ) as date_maze_end,
    parse_date(
        '%Y/%m/%d', coalesce(date_orf_7th_beginning, date_orf_8th_beginning)
    ) as date_orf_beginning,
    parse_date(
        '%Y/%m/%d', coalesce(date_orf_7th_middle, date_orf_8th_middle)
    ) as date_orf_middle,
    parse_date(
        '%Y/%m/%d', coalesce(date_orf_7th_end, date_orf_8th_end)
    ) as date_orf_end,
from {{ source("amplify", "src_amplify__dibels_data_farming") }}
