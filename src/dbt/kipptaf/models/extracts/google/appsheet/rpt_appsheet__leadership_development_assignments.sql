with
    roster as (select *, from {{ ref("rpt_appsheet__leadership_development_roster") }}),

    active_users as (
        select * from {{ ref("stg_leadership_development__active_users") }}
    ),

    metrics as (
        select *,
        from {{ ref("stg_performance_management__leadership_development_metrics") }}
        where academic_year = 2025 and not disabled
    ),

    existing_assignments as (
        select assignment_id, from {{ ref("stg_leadership_development__output") }}
    ),

    leader_pm_participants as (
        select
            roster.employee_number,
            coalesce(active_users.app_selection_active, roster.active) as active,
        from roster
        left join active_users on roster.employee_number = active_users.employee_number
    ),

    -- logic to create list of assignments
    assignments as (
        select
            roster.employee_number,
            metrics.academic_year,
            metrics.metric_id,
            concat(roster.employee_number, metrics.metric_id) as assignment_id,
            cast(null as string) as notes_boy,
            cast(null as string) as rating_moy,
            cast(null as string) as rating_eoy,
            cast(null as string) as notes_moy,
            cast(null as string) as notes_eoy,
            cast(null as string) as manager_rating_moy,
            cast(null as string) as manager_rating_eoy,
            cast(null as string) as manager_notes_moy,
            cast(null as string) as manager_notes_eoy,
            cast(null as date) as edited_at,
            cast(null as string) as edited_by,
            true as active_assignment,
        from roster
        inner join metrics on metrics.role = 'All'
        left join
            leader_pm_participants
            on roster.employee_number = leader_pm_participants.employee_number
        where leader_pm_participants.active

        union all

        select
            roster.employee_number,
            metrics.academic_year,
            metrics.metric_id,
            concat(roster.employee_number, metrics.metric_id) as assignment_id,
            cast(null as string) as notes_boy,
            cast(null as string) as rating_moy,
            cast(null as string) as rating_eoy,
            cast(null as string) as notes_moy,
            cast(null as string) as notes_eoy,
            cast(null as string) as manager_rating_moy,
            cast(null as string) as manager_rating_eoy,
            cast(null as string) as manager_notes_moy,
            cast(null as string) as manager_notes_eoy,
            cast(null as date) as edited_at,
            cast(null as string) as edited_by,
            true as active_assignment,
        from roster
        inner join metrics on roster.job_title = metrics.role
        left join
            leader_pm_participants
            on roster.employee_number = leader_pm_participants.employee_number
        where leader_pm_participants.active
    ),

    -- only include assignments not already on output
    final as (
        select assignments.*,
        from assignments
        left join
            existing_assignments
            on assignments.assignment_id = existing_assignments.assignment_id
        where existing_assignments.assignment_id is null
    )

select *,
from final
order by assignment_id
