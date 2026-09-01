with
    njgpa as (
        select
            american_indian_or_alaska_native,
            asian,
            assessment_grade,
            assessment_year,
            black_or_african_american,
            first_name,
            hispanic_or_latino_ethnicity,
            last_or_surname,
            multilingual_learner,
            native_hawaiian_or_other_pacific_islander,
            `period`,
            student_test_uuid,
            student_with_disabilities,
            `subject`,
            test_code,
            test_status,
            two_or_more_races,
            white,

            cast(grade_level_when_assessed as int) as grade_level_when_assessed,
            cast(local_student_identifier as int) as local_student_identifier,
            cast(state_student_identifier as int) as state_student_identifier,

            cast(test_performance_level as numeric) as test_performance_level,
            cast(test_scale_score as numeric) as test_scale_score,

            cast(test_score_complete as numeric) as test_score_complete,

            cast(left(assessment_year, 4) as int) as academic_year,

            /* MMDDYYYYHHMM. safe_cast to timestamp returns NULL on this
               format, so an explicit parse_datetime format is required. */
            safe.parse_datetime(
                '%m%d%Y%H%M', assessmentsessionactualstartdatetime
            ) as session_start_datetime,

            safe_cast(
                unit_1_online_test_start_date_time as timestamp
            ) as unit_1_start_timestamp,
            safe_cast(
                unit_2_online_test_start_date_time as timestamp
            ) as unit_2_start_timestamp,
            safe_cast(
                unit_3_online_test_start_date_time as timestamp
            ) as unit_3_start_timestamp,
            safe_cast(
                unit_4_online_test_start_date_time as timestamp
            ) as unit_4_start_timestamp,

        from {{ source("cambium", "src_cambium__njgpa") }}
        where summative_flag = 'Y' and test_attemptedness_flag = 'Y'
    ),

    earliest_test_start as (
        select
            * except (
                unit_1_start_timestamp,
                unit_2_start_timestamp,
                unit_3_start_timestamp,
                unit_4_start_timestamp
            ),

            (
                select min(s),
                from
                    unnest(
                        [
                            unit_1_start_timestamp,
                            unit_2_start_timestamp,
                            unit_3_start_timestamp,
                            unit_4_start_timestamp
                        ]
                    ) as s
            ) as earliest_test_start_timestamp,

        from njgpa
    )

select
    * except (earliest_test_start_timestamp, session_start_datetime),

    /* Unit start wins where present, preserving ELA behavior; the session
       fallback fills Mathematics, whose unit timestamps are all null. */
    coalesce(
        date(earliest_test_start_timestamp), date(session_start_datetime)
    ) as test_date,

from earliest_test_start
