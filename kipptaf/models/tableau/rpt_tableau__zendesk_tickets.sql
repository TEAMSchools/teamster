{{ config(enabled=false) }}

with
    field_crosswalk as (
        select id, `name` as field_value, 'group_id' as field_name
        from zendesk.group

        union all

        select id, email as field_value, 'assignee_id' as field_name
        from zendesk.user
    ),

    original_value as (
        select
            fh.ticket_id,
            fh.field_name,

            fc.field_value,

            row_number() over (
                partition by fh.ticket_id, fh.field_name order by fh.updated asc
            ) as field_rn
        from zendesk.ticket_field_history as fh
        left join
            field_crosswalk as fc on fh.field_name = fc.field_name and fh.value = fc.id
        where fh.field_name in ('group_id', 'assignee_id')
    ),

    group_updated as (
        select ticket_id, max(updated) as group_updated
        from zendesk.ticket_field_history
        where field_name = 'group_id'
        group by ticket_id
    )

select
    t.id as ticket_id,
    t.created_at,
    t.status as ticket_status,
    t.custom_category as category,
    t.custom_tech_tier as tech_tier,
    t.custom_location as `location`,
    t.subject as ticket_subject,
    concat('https://teamschools.zendesk.com/agent/tickets/', t.id) as ticket_url,

    s.name as submitter_name,

    a.name as assignee,

    g.name as last_group,

    tm.assignee_updated_at,
    tm.initially_assigned_at,
    tm.solved_at,
    tm.replies as comments_count,
    tm.full_resolution_time_in_minutes_business as total_bh_minutes,
    tm.reply_time_in_minutes_business,
    tm.assignee_stations,
    tm.group_stations,

    gu.group_updated as group_updated,

    og.field_value as original_group,

    datediff(weekday, t.created_at, gu.group_updated) as weekdays_created_to_last_group,

    datediff(weekday, t.created_at, tm.solved_at) as weekdays_created_to_solved,

    datediff(
        weekday, t.created_at, tm.initially_assigned_at
    ) as weekdays_created_to_first_assigned,
    datediff(
        weekday, t.created_at, tm.assignee_updated_at
    ) as weekdays_created_to_last_assigned,

    c.primary_job as assignee_primary_job,
    c.primary_site as assignee_primary_site,
    c.legal_entity_name as assignee_legal_entity,

    sx.primary_on_site_department as submitter_dept,
    sx.primary_job as submitter_job,
    sx.primary_site as submitter_site,
    sx.legal_entity_name as submitter_entity,

    oad.preferred_name as original_assignee,
    oad.primary_job as orig_assignee_job,
    oad.primary_on_site_department as orig_assignee_dept
from zendesk.ticket as t
left join zendesk.user as s on t.submitter_id = s.id
left join zendesk.user as a on t.assignee_id = a.id
left join zendesk.group as g on t.group_id = g.id
left join zendesk.ticket_metrics_clean as tm on t.id = tm.ticket_id
left join group_updated as gu on t.id = gu.ticket_id
left join
    original_value as og
    on t.id = og.ticket_id
    and og.field_name = 'group_id'
    and og.field_rn = 1
left join
    original_value as oa
    on t.id = oa.ticket_id
    and oa.field_name = 'assignee_id'
    and oa.field_rn = 1
left join people.staff_crosswalk_static as c on a.email = c.userprincipalname
left join people.staff_crosswalk_static as sx on s.email = sx.userprincipalname
left join people.staff_crosswalk_static as oad on oa.field_value = oad.userprincipalname
where t.status != 'deleted'
