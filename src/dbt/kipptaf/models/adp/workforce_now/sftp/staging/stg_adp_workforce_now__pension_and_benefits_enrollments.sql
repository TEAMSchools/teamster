select
    * except (enrollment_end_date) replace (
        cast(employee_number as int) as employee_number,
        parse_date('%m/%d/%Y', effective_date) as effective_date,
        parse_date('%m/%d/%Y', enrollment_start_date) as enrollment_start_date
    ),

    coalesce(
        parse_date('%m/%d/%Y', enrollment_end_date), '9999-12-31'
    ) as enrollment_end_date,

    -- not like 'NJ Pension - %': that also matches each plan's Contributory
    -- Insurance row
    plan_name in (
        'NJ Pension - DCRP:Eligible Employees(Prudential Financial)',
        'NJ Pension - PERS:Eligible Employees(NJ Pension)',
        'NJ Pension - TPAF:Eligible Employees(NJ Pension)'
    ) as is_nj_pension,
from
    {{
        source(
            "adp_workforce_now",
            "src_adp_workforce_now__pension_and_benefits_enrollments",
        )
    }}
