with
    original_assignee as (
        select tae.ticket_id, lower(u.email) as original_assignee_email,
        from {{ ref("stg_zendesk__ticket_audits__events") }} as tae
        left join
            {{ ref("stg_zendesk__users") }} as u
            on tae.event_value = safe_cast(u.id as string)
        where tae.event_type = 'Create' and tae.event_field_name = 'assignee_id'
    )

select
    {{ dbt_utils.generate_surrogate_key(["t.id"]) }} as support_ticket_key,

    {{ dbt_utils.generate_surrogate_key(["submitter.employee_number"]) }}
    as submitter_staff_key,

    if(
        assignee.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["assignee.employee_number"]) }},
        cast(null as string)
    ) as assignee_staff_key,

    if(
        orig_assignee.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["orig_assignee.employee_number"]) }},
        cast(null as string)
    ) as original_assignee_staff_key,

    cf.location_key,

    cast(t.created_at as date) as created_date_key,

    cast(tm.solved_at as date) as solved_date_key,

    t.status,
    t.subject,

    cf.category,
    cf.tech_tier,

    tm.replies as reply_count,
    tm.full_resolution_time_in_minutes_business as business_minutes_to_solve,
    tm.reply_time_in_minutes_business as business_minutes_to_first_reply,

    tm.assignee_stations as agent_reassignment_count,
    tm.group_stations as group_reassignment_count,

    t.created_at as created_timestamp,
    tm.initially_assigned_at as initially_assigned_timestamp,
    tm.assignee_updated_at as assignee_updated_timestamp,
    tm.solved_at as solved_timestamp,

    concat('https://teamschools.zendesk.com/agent/tickets/', t.id) as url,
from {{ source("zendesk", "tickets") }} as t
inner join {{ ref("stg_zendesk__users") }} as su on t.submitter_id = su.id
inner join
    {{ ref("int_people__staff_roster") }} as submitter
    on lower(su.email) = lower(submitter.user_principal_name)
left join {{ ref("stg_zendesk__users") }} as au on t.assignee_id = au.id
left join
    {{ ref("int_people__staff_roster") }} as assignee
    on lower(au.email) = lower(assignee.user_principal_name)
left join original_assignee as oa on t.id = oa.ticket_id
left join
    {{ ref("int_people__staff_roster") }} as orig_assignee
    on oa.original_assignee_email = lower(orig_assignee.user_principal_name)
left join
    {{ ref("int_zendesk__tickets__custom_fields_pivot") }} as cf on t.id = cf.ticket_id
left join {{ ref("stg_zendesk__ticket_metrics") }} as tm on t.id = tm.ticket_id
where t.status != 'deleted'
