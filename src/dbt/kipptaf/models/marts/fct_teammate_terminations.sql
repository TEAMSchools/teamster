with
    teammates as (select * from {{ ref("dim_teammates") }}),

    annual_roster as (select distinct employee_number, academic_year from teammates),

    terminations as (
        select
            employee_number,
            academic_year,
            effective_date_start,
            assignment_status as termination_status,
            assignment_status_reason as termination_reason
        from teammates
        where assignment_status = 'Terminated'
    ),

    {# first termination record by academic year #}
    first_termination_record as (
        select
            employee_number,
            academic_year,
            termination_status,
            termination_reason,
            min(effective_date_start) as termination_effective_date
        from terminations
        group by employee_number, academic_year, termination_status, termination_reason
    ),

    final as (
        select
            ar.employee_number,
            ar.academic_year,
            ftr.termination_status,
            ftr.termination_reason,
            ftr.termination_effective_date,
            if(ftr.employee_number is null, false, true) as is_termination
        from annual_roster as ar
        left join
            first_termination_record as ftr
            on ar.employee_number = ftr.employee_number
            and ar.academic_year = ftr.academic_year
    )

select *
from final
