{%- set src_work_assignment_history = source(
    "adp_workforce_now", "work_assignment_history"
) -%}
{%- set src_worker_report_to = source("adp_workforce_now", "worker_report_to") -%}
{%- set src_worker_group = source("adp_workforce_now", "worker_group") -%}
{%- set src_groups = source("adp_workforce_now", "groups") -%}
{%- set src_worker_base_remuneration = source(
    "adp_workforce_now", "worker_base_remuneration"
) -%}
{%- set src_worker_additional_remuneration = source(
    "adp_workforce_now", "worker_additional_remuneration"
) -%}
{%- set src_worker_assigned_location = source(
    "adp_workforce_now", "worker_assigned_location"
) -%}
{%- set src_location = source("adp_workforce_now", "location") -%}
{%- set ref_worker_organizational_unit = ref(
    "base_adp_workforce_now__worker_organizational_unit_pivot"
) -%}

select
    {{ dbt_utils.star(from=src_work_assignment_history) }},
    {{ dbt_utils.star(from=src_worker_report_to) }},
    {{ dbt_utils.star(from=src_worker_group) }},
    {{ dbt_utils.star(from=src_groups) }},
    {{ dbt_utils.star(from=src_worker_base_remuneration) }},
    {{ dbt_utils.star(from=src_worker_additional_remuneration) }},
    {{ dbt_utils.star(from=src_worker_assigned_location) }},
    {{ dbt_utils.star(from=src_location) }},
    {{ dbt_utils.star(from=ref_worker_organizational_unit) }},
from {{ src_work_assignment_history }} as wah
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
left join {{ ref_worker_organizational_unit }} as ou on wah.id = ou.worker_assignment_id
