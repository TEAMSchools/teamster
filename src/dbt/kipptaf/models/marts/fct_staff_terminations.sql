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
            primary_indicator
            and (
                job_title != 'Intern' or assignment_status_reason != 'Internship Ended'
            )
    ),

    /* determining unique years in which records are present for teammate */
    /* filtering out years with post-termination actions */
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

    /* first termination record by academic year */
    terminations as (
        select
            employee_number,
            academic_year,
            assignment_status as termination_status,
            assignment_status_reason as termination_reason,
            cast(
                assignment_status_effective_date as timestamp
            ) as termination_effective_date,
        from teammate_history
        where
            assignment_status = 'Terminated'
            and assignment_status_reason
            not in ('Import Created Action', 'Upgrade Created Action')
        qualify
            row_number() over (
                partition by employee_number, academic_year
                order by assignment_status_effective_date asc
            )
            = 1
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
    )

select
    employee_number,
    academic_year,
    termination_status,
    termination_reason,
    termination_effective_date,
    is_termination,

    {{ dbt_utils.generate_surrogate_key(["employee_number", "academic_year"]) }}
    as staff_terminations_key,
from final
