with
    matriculation_metrics as (
        select
            applicant,
            dbt_valid_from,
            dbt_valid_to,
            is_submitted_ba,
            is_accepted_ba,
            is_matriculated_ba,
            is_submitted_quality_bar_4yr_int,

            cast(dbt_valid_from as date) as dbt_valid_from_date,
            cast(dbt_valid_to as date) as dbt_valid_to_date,
        from {{ ref("snapshot_kippadb__app_rollup") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="matriculation_metrics",
                partition_by="applicant, dbt_valid_from_date",
                order_by="dbt_valid_to desc",
            )
        }}
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    m.is_submitted_ba,
    m.is_accepted_ba,
    m.is_matriculated_ba,
    m.is_submitted_quality_bar_4yr_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    deduplicate as m
    on co.salesforce_id = m.applicant
    and co.week_start_monday between m.dbt_valid_from_date and m.dbt_valid_to_date
where
    co.is_enrolled_week
    and co.grade_level = 12
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
