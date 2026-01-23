with
    terminations as (
        select
            employee_number,
            academic_year,
            effective_date_start,
            assignment_status,
            assignment_status_reason,
        from {{ ref("dim_teammates") }}
        where assignment_status = 'Terminated'

    ),

    {# first termination record by academic year #}
    first_termination_record as (
        select
            employee_number,
            academic_year,
            assignment_status,
            assignment_status_reason,
            min(effective_date_start) as termination_effective_date,
        from terminations
        group by all
    ),

    final as (select *, from first_termination_record)

select *,
from final
