{%- set src_work_assignment_history = source(
    "adp_workforce_now", "work_assignment_history"
) -%}
{%- set src_worker = source("adp_workforce_now", "worker") -%}
{%- set src_worker_group = source("adp_workforce_now", "worker_group") -%}
{%- set src_groups = source("adp_workforce_now", "groups") -%}
{%- set src_worker_additional_remuneration = source(
    "adp_workforce_now",
    "worker_additional_remuneration",
) -%}
{%- set src_worker_assigned_location = source(
    "adp_workforce_now", "worker_assigned_location"
) -%}
{%- set src_location = source("adp_workforce_now", "location") -%}

{%- set ref_worker_organizational_unit = ref(
    "stg_adp_workforce_now__worker_organizational_unit_pivot"
) -%}
{%- set ref_work_assignments = ref(
    "stg_adp_workforce_now__workers__work_assignments"
) -%}

with
    source as (
        select
            {{
                dbt_utils.star(
                    from=src_work_assignment_history,
                    except=["_fivetran_synced"],
                    relation_alias="wah",
                    prefix="work_assignment_",
                )
            }},

            {{
                dbt_utils.star(
                    from=src_worker,
                    except=["_fivetran_synced", "worker_id"],
                    relation_alias="w",
                    prefix="worker_",
                )
            }},

            {{
                dbt_utils.star(
                    from=src_groups,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="grp",
                    prefix="group_",
                )
            }},

            {{
                dbt_utils.star(
                    from=src_worker_additional_remuneration,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="war",
                    prefix="additional_remuneration_",
                )
            }},

            {{
                dbt_utils.star(
                    from=src_location,
                    except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
                    relation_alias="loc",
                    prefix="location_",
                )
            }},

            {{-
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
        from {{ src_work_assignment_history }} as wah
        inner join {{ src_worker }} as w on wah.worker_id = w.id
        left join {{ src_worker_group }} as wg on wah.id = wg.worker_assignment_id
        left join {{ src_groups }} as grp on wg.id = grp.id
        left join
            {{ src_worker_additional_remuneration }} as war
            on wah.id = war.worker_assignment_id
            and war.effective_date
            between extract(date from wah._fivetran_start) and extract(
                date from wah._fivetran_end
            )
        left join
            {{ src_worker_assigned_location }} as wal
            on wah.id = wal.worker_assignment_id
        left join {{ src_location }} as loc on wal.id = loc.id
        left join
            {{ ref_worker_organizational_unit }} as wou
            on wah.id = wou.worker_assignment_id
    ),

    -- trunk-ignore(sqlfluff/ST03)
    with_work_assignments as (
        select
            s.*,

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
            and wa.as_of_date_timestamp
            between s.work_assignment__fivetran_start
            and s.work_assignment__fivetran_end
    ),

    deduplicate_work_assignments as (
        {{
            dbt_utils.deduplicate(
                relation="with_work_assignments",
                partition_by="work_assignment_id, work_assignment__fivetran_start, work_assignment__fivetran_end, work_assignment__surrogate_key",
                order_by="work_assignment__as_of_date_timestamp desc",
            )
        }}
    ),

    with_as_of_date_timestamp_lag as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,
            lag(work_assignment__as_of_date_timestamp, 1) over (
                partition by work_assignment_id
                order by work_assignment__as_of_date_timestamp
            ) as work_assignment__as_of_date_timestamp_lag,
        from deduplicate_work_assignments
    ),

    with_final_dates as (
        select
            * except (work_assignment__fivetran_start, work_assignment__fivetran_end),

            coalesce(
                timestamp_add(
                    work_assignment__as_of_date_timestamp_lag, interval 1 millisecond
                ),
                work_assignment__fivetran_start
            ) as work_assignment_start_date,

            (
                select min(col),
                from
                    unnest(
                        [
                            work_assignment__fivetran_end,
                            work_assignment__as_of_date_timestamp
                        ]
                    ) as col
            ) as work_assignment_end_date,
        from with_as_of_date_timestamp_lag
    )

select *,
from with_final_dates
where work_assignment_start_date <= work_assignment_end_date
