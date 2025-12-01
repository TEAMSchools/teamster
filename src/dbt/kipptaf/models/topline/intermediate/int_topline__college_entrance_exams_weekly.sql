with
    -- trunk-ignore(sqlfluff/ST03)
    sat_total as (
        select
            school_specific_id as student_number,
            dbt_valid_to,
            test_type,
            score,

            cast(dbt_valid_from as date) as dbt_valid_from_date,
            cast(dbt_valid_to as date) as dbt_valid_to_date,
        from {{ ref("snapshot_kippadb__standardized_test_rollup") }}
        where
            test_type in ('SAT', 'PSAT NMSQT', 'PSAT 8/9') and test_subject = 'Combined'
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="sat_total",
                partition_by="student_number, test_type, dbt_valid_from_date",
                order_by="dbt_valid_to desc",
            )
        }}
    )

select
    co.student_number,
    co.academic_year,
    co.schoolid,
    co.week_start_monday,
    co.week_end_sunday,

    sat.test_type,
    sat.score,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    deduplicate as sat
    on co.student_number = sat.student_number
    and co.week_start_monday between sat.dbt_valid_from_date and sat.dbt_valid_to_date
where co.is_enrolled_week and co.school_level = 'HS' and sat.score is not null
