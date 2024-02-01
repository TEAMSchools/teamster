with
    group_updated as (
        select ticket_id, max(ticket_audit_created_at) as max_created_at,
        from {{ ref("stg_zendesk__ticket_audits__events") }}
        where event_field_name = 'group_id'
        group by ticket_id
    ),

    original_value as (
        select tae.ticket_id, tae.event_field_name, g.name as field_value,
        from {{ ref("stg_zendesk__ticket_audits__events") }} as tae
        left join
            {{ source("zendesk", "groups") }} as g
            on tae.event_value = safe_cast(g.id as string)
        where tae.event_type = 'Create' and tae.event_field_name = 'group_id'

        union all

        select tae.ticket_id, tae.event_field_name, u.email as field_value,
        from {{ ref("stg_zendesk__ticket_audits__events") }} as tae
        left join
            {{ source("zendesk", "users") }} as u
            on tae.event_value = safe_cast(u.id as string)
        where tae.event_type = 'Create' and tae.event_field_name = 'assignee_id'
    )

select
    t.id as ticket_id,
    t.created_at,
    t.status as ticket_status,
    t.subject as ticket_subject,
    concat('https://teamschools.zendesk.com/agent/tickets/', t.id) as ticket_url,

    cf.category,
    cf.tech_tier,
    cf.location,

    s.name as submitter_name,

    a.name as assignee,

    g.name as last_group,

    tm.assignee_updated_at,
    tm.initially_assigned_at,
    tm.solved_at,
    tm.assignee_stations,
    tm.group_stations,
    tm.replies as comments_count,
    tm.full_resolution_time_in_minutes_business as total_bh_minutes,
    tm.reply_time_in_minutes_business as reply_time_in_minutes_business,

    gu.max_created_at as group_updated,

    og.field_value as original_group,

    sx.department_home_name as submitter_dept,
    sx.job_title as submitter_job,
    sx.home_work_location_name as submitter_site,
    sx.business_unit_home_name as submitter_entity,

    c.job_title as assignee_primary_job,
    c.home_work_location_name as assignee_primary_site,
    c.business_unit_home_name as assignee_legal_entity,

    oad.preferred_name_lastfirst as original_assignee,
    oad.job_title as orig_assignee_job,
    oad.department_home_name as orig_assignee_dept,

    {{ teamster_utils.date_diff_weekday("gu.max_created_at", "t.created_at") }}
    as weekdays_created_to_last_group,
    {{ teamster_utils.date_diff_weekday("tm.solved_at", "t.created_at") }}
    as weekdays_created_to_solved,
    {{ teamster_utils.date_diff_weekday("tm.initially_assigned_at", "t.created_at") }}
    as weekdays_created_to_first_assigned,
    {{ teamster_utils.date_diff_weekday("tm.assignee_updated_at", "t.created_at") }}
    as weekdays_created_to_last_assigned,
from {{ source("zendesk", "tickets") }} as t
left join
    {{ ref("int_zendesk__tickets__custom_fields_pivot") }} as cf on t.id = cf.ticket_id
left join {{ source("zendesk", "users") }} as s on t.submitter_id = s.id
left join {{ source("zendesk", "users") }} as a on t.assignee_id = a.id
left join {{ source("zendesk", "groups") }} as g on t.group_id = g.id
left join {{ ref("int_zendesk__ticket_metrics_union") }} as tm on t.id = tm.ticket_id
left join group_updated as gu on t.id = gu.ticket_id
left join
    original_value as og on t.id = og.ticket_id and og.event_field_name = 'group_id'
left join
    original_value as oa on t.id = oa.ticket_id and oa.event_field_name = 'assignee_id'
left join
    {{ ref("base_people__staff_roster") }} as sx on s.email = sx.user_principal_name
left join {{ ref("base_people__staff_roster") }} as c on a.email = c.user_principal_name
left join
    {{ ref("base_people__staff_roster") }} as oad
    on oa.field_value = oad.user_principal_name
where t.status != 'deleted'
