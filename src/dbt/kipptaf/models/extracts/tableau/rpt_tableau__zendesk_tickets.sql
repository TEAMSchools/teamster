with
    group_updated as (
        select ticket_id, max(created_at) as max_created_at,
        from {{ ref("int_zendesk__ticket_events") }}
        where event_type = 'Audit' and group_id is not null
        group by ticket_id
    ),

    ticket_audit_create as (
        select
            ticket_id,

            max(group_name) as group_name,
            max(assignee_email) as assignee_email,
        from {{ ref("int_zendesk__ticket_events") }}
        where event_type = 'Audit' and child_event_type = 'Create'
        group by ticket_id
    ),

    original_value as (
        select
            tac.ticket_id,
            tac.group_name,

            a.formatted_name,
            a.job_title,
            a.home_department_name,
        from ticket_audit_create as tac
        left join
            {{ ref("int_people__staff_roster") }} as a
            on tac.assignee_email = a.user_principal_name
    )

select
    t.id as ticket_id,
    t.created_at,
    t.status as ticket_status,
    t.subject as ticket_subject,
    t.category,
    t.tech_tier,
    t.location,
    t.ticket_url,
    t.submitter_name,
    t.assignee_name as assignee,
    t.group_name as last_group,

    tm.assignee_updated_at,
    tm.initially_assigned_at,
    tm.solved_at,
    tm.assignee_stations,
    tm.group_stations,
    tm.replies as comments_count,
    tm.full_resolution_time_in_minutes__business as total_bh_minutes,
    tm.reply_time_in_minutes__business as reply_time_in_minutes_business,

    gu.max_created_at as group_updated,

    ov.group_name as original_group,
    ov.formatted_name as original_assignee,
    ov.job_title as orig_assignee_job,
    ov.home_department_name as orig_assignee_dept,

    s.home_department_name as submitter_dept,
    s.job_title as submitter_job,
    s.home_work_location_name as submitter_site,
    s.home_business_unit_name as submitter_entity,

    a.job_title as assignee_primary_job,
    a.home_work_location_name as assignee_primary_site,
    a.home_business_unit_name as assignee_legal_entity,

    {{ date_diff_weekday("gu.max_created_at", "t.created_at") }}
    as weekdays_created_to_last_group,
    {{ date_diff_weekday("tm.solved_at", "t.created_at") }}
    as weekdays_created_to_solved,
    {{ date_diff_weekday("tm.initially_assigned_at", "t.created_at") }}
    as weekdays_created_to_first_assigned,
    {{ date_diff_weekday("tm.assignee_updated_at", "t.created_at") }}
    as weekdays_created_to_last_assigned,
from {{ ref("int_zendesk__tickets") }} as t
left join {{ ref("stg_zendesk__ticket_metrics") }} as tm on t.id = tm.ticket_id
left join group_updated as gu on t.id = gu.ticket_id
left join original_value as ov on t.id = ov.ticket_id
left join
    {{ ref("int_people__staff_roster") }} as s
    on t.submitter_email = s.user_principal_name
left join
    {{ ref("int_people__staff_roster") }} as a
    on t.assignee_email = a.user_principal_name
