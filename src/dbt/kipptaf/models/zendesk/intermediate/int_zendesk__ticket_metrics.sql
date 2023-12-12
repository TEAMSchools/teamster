with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_zendesk__ticket_metrics"),
                    ref("stg_zendesk__ticket_metrics_archive"),
                ],
                include=[
                    "ticket_id",
                    "assignee_updated_at",
                    "initially_assigned_at",
                    "solved_at",
                    "assignee_stations",
                    "group_stations",
                    "replies",
                    "full_resolution_time_in_minutes_business",
                    "reply_time_in_minutes_business",
                ],
            )
        }}
    )

select
    ticket_id,
    assignee_updated_at,
    initially_assigned_at,
    solved_at,
    assignee_stations,
    group_stations,
    replies,
    full_resolution_time_in_minutes_business,
    reply_time_in_minutes_business,
from union_relations
