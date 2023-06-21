{%- set ref_worker = ref("base_adp_workforce_now__worker") -%}
{%- set ref_person = ref("base_adp_workforce_now__person") -%}

select
    {{ dbt_utils.star(from=ref_worker, relation_alias="w") }},
    {{
        dbt_utils.star(
            from=ref_person, relation_alias="p", except=["person_worker_id"]
        )
    }},
from {{ ref_worker }} as w
inner join {{ ref_person }} as p on w.work_assignment_worker_id = p.person_worker_id
