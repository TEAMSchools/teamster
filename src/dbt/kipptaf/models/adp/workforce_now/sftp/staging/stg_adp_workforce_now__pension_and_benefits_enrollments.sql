with
    pension_and_benefits_enrollments as (
        select
            * except (
                employee_number,
                effective_date,
                enrollment_end_date,
                enrollment_start_date
            ),

            cast(employee_number as int) as employee_number,

            parse_date('%m/%d/%Y', effective_date) as effective_date,
            parse_date('%m/%d/%Y', enrollment_start_date) as enrollment_start_date,

            coalesce(
                parse_date('%m/%d/%Y', enrollment_end_date), '9999-12-31'
            ) as enrollment_end_date,
        from
            {{
                source(
                    "adp_workforce_now",
                    "src_adp_workforce_now__pension_and_benefits_enrollments",
                )
            }}
    )

select
    *,

    row_number() over (
        partition by employee_number, enrollment_status
        order by enrollment_end_date desc, enrollment_start_date desc
    ) as rn_enrollment_recent,
from pension_and_benefits_enrollments
