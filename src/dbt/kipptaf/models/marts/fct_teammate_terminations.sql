with
    teammate_history as (
        select distinct
            assignment_status_effective_date,
            employee_number,
            assignment_status,
            assignment_status_reason,
            {{
                date_to_fiscal_year(
                    date_field="assignment_status_effective_date",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("int_people__staff_roster_history") }}
        where
            (job_title != 'Intern' or assignment_status_reason != 'Internship Ended')
            and primary_indicator
    ),

    {# determining unique years in which records are present for teammate#}
    {# filtering out years with post-termination actions#}
    annual_roster as (
        select distinct employee_number, academic_year,
        from teammate_history
        where
            assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
            or (
                assignment_status = 'Terminated'
                and assignment_status_reason
                not in ('Import Created Action', 'Upgrade Created Action')
            )
    ),

    {# first termination record by academic year#}
    {# using effective start date downstream to filter post-termination actions#}
    terminations as (
        select
            employee_number,
            academic_year,
            assignment_status as termination_status,
            assignment_status_reason as termination_reason,
            min(assignment_status_effective_date) as min_effective_date,
            min(assignment_status_effective_date) as termination_effective_date,
        from teammate_history
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
