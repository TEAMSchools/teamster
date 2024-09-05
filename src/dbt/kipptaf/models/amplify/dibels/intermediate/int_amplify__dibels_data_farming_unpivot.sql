select
    student_id,
    academic_year,

    date_composite_beginning,
    composite_beginning,
    benchmark_status_composite_beginning,
    national_dds_percentile_composite_beginning,
    district_percentile_composite_beginning,
    school_percentile_composite_beginning,

    date_composite_middle,
    composite_middle,
    benchmark_status_composite_middle,
    national_dds_percentile_composite_middle,
    district_percentile_composite_middle,
    school_percentile_composite_middle,

    date_composite_end,
    composite_end,
    benchmark_status_composite_end,
    national_dds_percentile_composite_end,
    district_percentile_composite_end,
    school_percentile_composite_end,
    growth_goal_type_composite_end,
    growth_goal_composite_end,
    growth_percentile_composite_end,
    growth_goal_met_composite_end,
    months_of_growth_composite_end,

    date_maze_beginning,
    form_maze_beginning,
    remote_maze_beginning,

    date_maze_middle,
    form_maze_middle,
    remote_maze_middle,

    date_maze_end,
    form_maze_end,
    remote_maze_end,

    date_orf_beginning,
    form_orf_beginning,
    remote_orf_beginning,

    date_orf_middle,
    form_orf_middle,
    remote_orf_middle,

    date_orf_end,
    form_orf_end,
    remote_orf_end,

    maze_adjusted_beginning,
    benchmark_status_maze_adjusted_beginning,
    national_dds_percentile_maze_adjusted_beginning,
    district_percentile_maze_adjusted_beginning,
    school_percentile_maze_adjusted_beginning,

    maze_adjusted_middle,
    benchmark_status_maze_adjusted_middle,
    national_dds_percentile_maze_adjusted_middle,
    district_percentile_maze_adjusted_middle,
    school_percentile_maze_adjusted_middle,

    maze_adjusted_end,
    benchmark_status_maze_adjusted_end,
    national_dds_percentile_maze_adjusted_end,
    district_percentile_maze_adjusted_end,
    school_percentile_maze_adjusted_end,

    maze_correct_beginning,
    district_percentile_maze_correct_beginning,
    school_percentile_maze_correct_beginning,

    maze_correct_middle,
    district_percentile_maze_correct_middle,
    school_percentile_maze_correct_middle,

    maze_correct_end,
    district_percentile_maze_correct_end,
    school_percentile_maze_correct_end,

    maze_incorrect_beginning,
    district_percentile_maze_incorrect_beginning,
    school_percentile_maze_incorrect_beginning,

    maze_incorrect_middle,
    district_percentile_maze_incorrect_middle,
    school_percentile_maze_incorrect_middle,

    maze_incorrect_end,
    district_percentile_maze_incorrect_end,
    school_percentile_maze_incorrect_end,

    orf_accuracy_beginning,
    benchmark_status_orf_accuracy_beginning,
    national_dds_percentile_orf_accuracy_beginning,
    district_percentile_orf_accuracy_beginning,
    school_percentile_orf_accuracy_beginning,

    orf_accuracy_middle,
    benchmark_status_orf_accuracy_middle,
    national_dds_percentile_orf_accuracy_middle,
    district_percentile_orf_accuracy_middle,
    school_percentile_orf_accuracy_middle,

    orf_accuracy_end,
    benchmark_status_orf_accuracy_end,
    national_dds_percentile_orf_accuracy_end,
    district_percentile_orf_accuracy_end,
    school_percentile_orf_accuracy_end,

    orf_wordscorrect_beginning,
    benchmark_status_orf_wordscorrect_beginning,
    national_dds_percentile_orf_wordscorrect_beginning,
    district_percentile_orf_wordscorrect_beginning,
    school_percentile_orf_wordscorrect_beginning,

    orf_wordscorrect_middle,
    benchmark_status_orf_wordscorrect_middle,
    national_dds_percentile_orf_wordscorrect_middle,
    district_percentile_orf_wordscorrect_middle,
    school_percentile_orf_wordscorrect_middle,

    orf_wordscorrect_end,
    benchmark_status_orf_wordscorrect_end,
    national_dds_percentile_orf_wordscorrect_end,
    district_percentile_orf_wordscorrect_end,
    school_percentile_orf_wordscorrect_end,

    orf_errors_beginning,
    district_percentile_orf_errors_beginning,
    school_percentile_orf_errors_beginning,

    orf_errors_middle,
    district_percentile_orf_errors_middle,
    school_percentile_orf_errors_middle,

    orf_errors_end,
    district_percentile_orf_errors_end,
    school_percentile_orf_errors_end,
from {{ ref("stg_amplify__dibels_data_farming") }}
