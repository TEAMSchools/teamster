select
    * except (
        client_date,
        dibels_composite_score_lexile,
        official_teacher_name,
        official_teacher_staff_id,
        reading_comprehension_maze_discontinued,
        reading_comprehension_maze_level,
        reading_comprehension_maze_national_norm_percentile,
        reading_comprehension_maze_score,
        reading_comprehension_maze_semester_growth,
        reading_comprehension_maze_tested_out,
        reading_comprehension_maze_year_growth,
        surrogate_key
    ),

    client_date as device_date,
    dibels_composite_score_lexile as composite_score_lexile,
    official_teacher_name as enrollment_teacher_name,
    official_teacher_staff_id as enrollment_teacher_staff_id,
    reading_comprehension_maze_discontinued as basic_comprehension_maze_discontinued,
    reading_comprehension_maze_level as basic_comprehension_maze_level,
    reading_comprehension_maze_national_norm_percentile
    as basic_comprehension_maze_national_norm_percentile,
    reading_comprehension_maze_score as basic_comprehension_maze_score,
    reading_comprehension_maze_semester_growth
    as basic_comprehension_maze_semester_growth,
    reading_comprehension_maze_tested_out as basic_comprehension_maze_tested_out,
    reading_comprehension_maze_year_growth as basic_comprehension_maze_year_growth,
from {{ source("amplify", "stg_amplify__mclass__api__benchmark_student_summary") }}
