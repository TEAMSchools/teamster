with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__benchmark_student_summary"),
                    source(
                        "amplify",
                        "stg_amplify__mclass__api__benchmark_student_summary",
                    ),
                ]
            )
        }}
    ),

    location_xref as (
        select
            ur.*,

            x.abbreviation as school,
            x.powerschool_school_id as schoolid,

            initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,
        from union_relations as ur
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on ur.school_name = x.name
    )

select
    * except (
        basic_comprehension_maze_local_percentile,
        enrollment_teacher_staff_id,
        official_teacher_staff_id,
        enrollment_teacher_name,
        official_teacher_name,
        device_date,
        client_date,
        composite_score_lexile,
        dibels_composite_score_lexile,
        basic_comprehension_maze_score,
        reading_comprehension_maze_score,
        basic_comprehension_maze_semester_growth,
        reading_comprehension_maze_semester_growth,
        basic_comprehension_maze_year_growth,
        reading_comprehension_maze_year_growth,
        basic_comprehension_maze_national_norm_percentile,
        reading_comprehension_maze_national_norm_percentile,
        basic_comprehension_maze_level,
        reading_comprehension_maze_level,
        basic_comprehension_maze_tested_out,
        reading_comprehension_maze_tested_out,
        basic_comprehension_maze_discontinued,
        reading_comprehension_maze_discontinued
    ),

    basic_comprehension_maze_local_percentile
    as reading_comprehension_maze_local_percentile,

    coalesce(
        enrollment_teacher_staff_id, official_teacher_staff_id
    ) as official_teacher_staff_id,
    coalesce(enrollment_teacher_name, official_teacher_name) as official_teacher_name,
    coalesce(device_date, client_date) as client_date,
    coalesce(
        composite_score_lexile, dibels_composite_score_lexile
    ) as dibels_composite_score_lexile,
    coalesce(
        basic_comprehension_maze_score, reading_comprehension_maze_score
    ) as reading_comprehension_maze_score,
    coalesce(
        basic_comprehension_maze_semester_growth,
        reading_comprehension_maze_semester_growth
    ) as reading_comprehension_maze_semester_growth,
    coalesce(
        basic_comprehension_maze_year_growth, reading_comprehension_maze_year_growth
    ) as reading_comprehension_maze_year_growth,
    coalesce(
        basic_comprehension_maze_national_norm_percentile,
        reading_comprehension_maze_national_norm_percentile
    ) as reading_comprehension_maze_national_norm_percentile,
    coalesce(
        basic_comprehension_maze_level, reading_comprehension_maze_level
    ) as reading_comprehension_maze_level,
    coalesce(
        basic_comprehension_maze_tested_out, reading_comprehension_maze_tested_out
    ) as reading_comprehension_maze_tested_out,
    coalesce(
        basic_comprehension_maze_discontinued, reading_comprehension_maze_discontinued
    ) as reading_comprehension_maze_discontinued,

from location_xref
