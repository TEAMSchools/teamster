with
    positioned as (
        select
            model_type,
            academic_year,
            region,
            student_number,
            expected_measure_standard,
            expected_test,
            expected_round_number,
            measure_standard_round_verdicts,
            measure_standard_goal_status,
            met_measure_standard_goal,

            row_number() over (
                partition by
                    model_type,
                    academic_year,
                    region,
                    student_number,
                    expected_measure_standard,
                    expected_test
                order by cast(expected_round_number as int64)
            ) as round_position,

        from {{ ref("rpt_tableau__dibels_dashboard") }}
        where model_type != 'BM'
    ),

    compared as (
        select
            model_type,
            academic_year,
            region,
            student_number,
            expected_measure_standard,
            expected_test,
            expected_round_number,
            measure_standard_round_verdicts,
            measure_standard_goal_status,
            round_position,

            split(measure_standard_round_verdicts, '-')[
                safe_offset(round_position - 1)
            ] as token_at_position,

            case
                when measure_standard_goal_status = 'Not Tested'
                then '.'
                when met_measure_standard_goal = 1
                then 'A'
                when met_measure_standard_goal = 0
                then 'B'
                else '?'
            end as token_from_status,

        from positioned
    )

select *,
from compared
where token_at_position is distinct from token_from_status
