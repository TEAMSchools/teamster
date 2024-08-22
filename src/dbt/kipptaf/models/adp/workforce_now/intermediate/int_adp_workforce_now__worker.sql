{%- set ref_work_assignment_history = ref(
    "stg_adp_workforce_now__work_assignment_history"
) -%}
{%- set ref_worker = ref("stg_adp_workforce_now__worker") -%}
{%- set ref_worker_group = ref("stg_adp_workforce_now__worker_group") -%}
{%- set ref_groups = ref("stg_adp_workforce_now__groups") -%}
{%- set ref_worker_additional_remuneration = ref(
    "stg_adp_workforce_now__worker_additional_remuneration"
) -%}
{%- set ref_worker_assigned_location = ref(
    "stg_adp_workforce_now__worker_assigned_location"
) -%}
{%- set ref_location = ref("stg_adp_workforce_now__location") -%}
{%- set ref_work_assignments = ref(
    "stg_adp_workforce_now__workers__work_assignments"
) -%}
{%- set ref_reports_to = ref(
    "stg_adp_workforce_now__workers__work_assignments__reports_to"
) -%}
{%- set ref_worker_organizational_unit = ref(
    "int_adp_workforce_now__worker_organizational_unit_pivot"
) -%}

with
    source as (
        select
            timestamp(
                datetime(wah._fivetran_start), 'America/New_York'
            ) as work_assignment__fivetran_start,

            coalesce(
                safe.timestamp(datetime(wah._fivetran_end), 'America/New_York'),
                timestamp('9999-12-31 23:59:59.999999')
            ) as work_assignment__fivetran_end,

            {{
                dbt_utils.star(
                    from=ref_work_assignment_history,
                    except=["_fivetran_start", "_fivetran_end", "_fivetran_synced"],
                    relation_alias="wah",
                    prefix="work_assignment_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_worker,
                    except=["_fivetran_synced", "worker_id"],
                    relation_alias="w",
                    prefix="worker_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_groups,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="grp",
                    prefix="group_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_worker_additional_remuneration,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="war",
                    prefix="additional_remuneration_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_location,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="loc",
                    prefix="location_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_worker_organizational_unit,
                    except=["_fivetran_synced", "worker_assignment_id"],
                    relation_alias="wou",
                    prefix="organizational_unit_",
                )
            }},

            lag(wah.assignment_status_long_name) over (
                partition by wah.worker_id
                order by wah.assignment_status_effective_date asc
            ) as work_assignment_assignment_status_long_name_prev,
        from {{ ref_work_assignment_history }} as wah
        inner join {{ ref_worker }} as w on wah.worker_id = w.id
        left join {{ ref_worker_group }} as wg on wah.id = wg.worker_assignment_id
        left join {{ ref_groups }} as grp on wg.id = grp.id
        left join
            {{ ref_worker_additional_remuneration }} as war
            on wah.id = war.worker_assignment_id
            and war.effective_date
            between extract(date from wah._fivetran_start) and extract(
                date from wah._fivetran_end
            )
        left join
            {{ ref_worker_assigned_location }} as wal
            on wah.id = wal.worker_assignment_id
        left join {{ ref_location }} as loc on wal.id = loc.id
        left join
            {{ ref_worker_organizational_unit }} as wou
            on wah.id = wou.worker_assignment_id
    ),

    -- trunk-ignore(sqlfluff/ST03)
    with_work_assignments as (
        select
            s.*,

            rt.reports_to_associate_oid,
            rt.reports_to_position_id,
            rt.reports_to_worker_name__formatted_name,
            rt.reports_to_worker_id__id_value,
            rt.reports_to_worker_id__scheme_code__code_value,
            rt.reports_to_worker_id__scheme_code__short_name,

            {{
                dbt_utils.star(
                    from=ref_work_assignments,
                    except=["item_id", "associate_oid"],
                    relation_alias="wa",
                    prefix="work_assignment__",
                )
            }},
        from source as s
        left join
            {{ ref_work_assignments }} as wa
            on s.work_assignment_id = wa.item_id
            and wa.effective_date_timestamp
            between s.work_assignment__fivetran_start
            and s.work_assignment__fivetran_end
        left join
            {{ ref_reports_to }} as rt
            on wa.item_id = rt.item_id
            and rt.is_current_record
    ),

    deduplicate_work_assignments as (
        {{
            dbt_utils.deduplicate(
                relation="with_work_assignments",
                partition_by="work_assignment_id, work_assignment__fivetran_start, work_assignment__fivetran_end, work_assignment__surrogate_key",
                order_by="work_assignment__effective_date_timestamp asc",
            )
        }}
    ),

    with_work_assignment_start as (
        select
            *,

            coalesce(
                timestamp_trunc(
                    work_assignment__effective_date_timestamp,
                    day,
                    '{{ var("local_timezone") }}'
                ),
                work_assignment__fivetran_start
            ) as work_assignment_start_timestamp,
        from deduplicate_work_assignments
    ),

    with_work_assignment_end as (
        select
            *,

            timestamp_sub(
                lead(
                    work_assignment_start_timestamp,
                    1,
                    timestamp(date(9999, 12, 31), '{{ var("local_timezone") }}')
                ) over (
                    partition by work_assignment_id
                    order by work_assignment_start_timestamp asc
                ),
                interval 1 millisecond
            ) as work_assignment_end_timestamp,
        from with_work_assignment_start
    )

select
    *,

    date(
        work_assignment_start_timestamp, '{{ var("local_timezone") }}'
    ) as work_assignment_start_date,
    date(
        work_assignment_end_timestamp, '{{ var("local_timezone") }}'
    ) as work_assignment_end_date,
from with_work_assignment_end
