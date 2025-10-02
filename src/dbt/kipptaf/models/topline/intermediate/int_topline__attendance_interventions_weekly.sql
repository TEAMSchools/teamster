with
    -- trunk-ignore(sqlfluff/ST03)
    interventions as (
        select
            student_number,
            academic_year,
            dbt_valid_from,
            dbt_valid_to,
            successful_call_count,
            total_anticipated_calls,
            pct_interventions_complete,

            cast(dbt_valid_from as date) as dbt_valid_from_date,
            cast(dbt_valid_to as date) as dbt_valid_to_date,
        from {{ ref("snapshot_students__attendance_interventions_rollup") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="interventions",
                partition_by="student_number, academic_year, dbt_valid_from_date",
                order_by="dbt_valid_to desc",
            )
        }}
    )

select
    co.student_number,
    co.schoolid,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,

    ca.successful_call_count,
    ca.total_anticipated_calls,
    ca.pct_interventions_complete,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    deduplicate as ca
    on co.student_number = ca.student_number
    and co.week_start_monday between ca.dbt_valid_from_date and ca.dbt_valid_to_date
where co.is_enrolled_week
