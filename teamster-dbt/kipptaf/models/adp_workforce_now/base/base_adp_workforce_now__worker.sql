{%- set src_work_assignment_history = source(
    "adp_workforce_now", "work_assignment_history"
) -%}
{%- set src_worker = source("adp_workforce_now", "worker") -%}
{%- set src_worker_report_to = source("adp_workforce_now", "worker_report_to") -%}
{%- set src_worker_group = source("adp_workforce_now", "worker_group") -%}
{%- set src_groups = source("adp_workforce_now", "groups") -%}
{%- set src_worker_base_remuneration = source(
    "adp_workforce_now", "worker_base_remuneration"
) -%}
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

select
    {{
        dbt_utils.star(
            from=src_work_assignment_history,
            except=["_fivetran_synced"],
            relation_alias="wah",
            prefix="work_assignment_",
        )
    }},
    lag(wah.assignment_status_long_name) over (
        partition by wah.worker_id order by wah.assignment_status_effective_date asc
    ) as work_assignment_assignment_status_long_name_prev,

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
            from=src_worker_report_to,
            except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
            relation_alias="wrt",
            prefix="report_to_",
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
            from=src_worker_base_remuneration,
            except=["_fivetran_synced", "worker_assignment_id", "worker_id"],
            relation_alias="wbr",
            prefix="base_remuneration_",
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
from {{ src_work_assignment_history }} as wah
inner join {{ src_worker }} as w on wah.worker_id = w.id
left join {{ src_worker_report_to }} as wrt on wah.id = wrt.worker_assignment_id
left join {{ src_worker_group }} as wg on wah.id = wg.worker_assignment_id
left join {{ src_groups }} as grp on wg.id = grp.id
left join {{ src_worker_base_remuneration }} as wbr on wah.id = wbr.worker_assignment_id
left join
    {{ src_worker_additional_remuneration }} as war
    on wah.id = war.worker_assignment_id
    and war.effective_date between extract(date from wah._fivetran_start) and extract(
        date from wah._fivetran_end
    )
left join {{ src_worker_assigned_location }} as wal on wah.id = wal.worker_assignment_id
left join {{ src_location }} as loc on wal.id = loc.id
left join
    {{ ref_worker_organizational_unit }} as wou on wah.id = wou.worker_assignment_id
