with
    teammates as (select *, from {{ ref("dim_teammates") }}),

    {# determining unique years in which records are present for teammate#}
    {# filtering out years with post-termination actions#}
    annual_roster as (
        select distinct employee_number, academic_year,
        from teammates
        where
            assignment_status_reason is null
            or assignment_status_reason
            not in ('Import Created Action', 'Upgrade Created Action')
    ),

    {# first termination record by academic year#}
    {# using effective start date downstream to filter post-termination actions#}
    terminations as (
        select
            employee_number,
            academic_year,
            assignment_status as termination_status,
            assignment_status_reason as termination_reason,
            min(effective_date_start) as min_effective_date,
            min(assignment_status_effective_date) as termination_effective_date,
        from teammates
        where
            assignment_status = 'Terminated'
            and assignment_status_reason
            not in ('Import Created Action', 'Upgrade Created Action')
        group by all
    ),

    final as (
        select
            ar.employee_number,
            ar.academic_year,
            tr.termination_status,
            tr.termination_reason,
            tr.termination_effective_date,
            if(tr.employee_number is null, false, true) as is_termination,
        from annual_roster as ar
        left join
            terminations as tr
            on ar.employee_number = tr.employee_number
            and ar.academic_year = tr.academic_year
        where
            tr.min_effective_date <= tr.termination_effective_date
            or tr.termination_effective_date is null
    )

select *,
from final
