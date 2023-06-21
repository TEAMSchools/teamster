{%- set ref_person_history = ref("stg_adp_workforce_now__person_history") -%}
{%- set ref_person_preferred_salutation = ref(
    "stg_adp_workforce_now__person_preferred_salutation_pivot"
) -%}
{%- set ref_person_communication = ref(
    "stg_adp_workforce_now__person_communication_pivot"
) -%}
{%- set src_person_disability = source("adp_workforce_now", "person_disability") -%}
{# {%- set src_person_government_id = source(
    "adp_workforce_now", "person_government_id"
) -%} #}
{%- set src_other_personal_address = source(
    "adp_workforce_now", "other_personal_address"
) -%}

select
    {{
        dbt_utils.star(
            from=ref_person_history,
            except=["_fivetran_synced", "_fivetran_id"],
            relation_alias="ph",
            prefix="person_",
        )
    }},
    {{
        dbt_utils.star(
            from=ref_person_preferred_salutation,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="pps",
            prefix="preferred_salutation_",
        )
    }},
    {{
        dbt_utils.star(
            from=ref_person_communication,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="pc",
            prefix="communication_",
        )
    }},
    {{
        dbt_utils.star(
            from=src_other_personal_address,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="opa",
            prefix="personal_address_",
        )
    }},
    {{
        dbt_utils.star(
            from=src_person_disability,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="pd",
            prefix="disability_",
        )
    }},
{# {{
        dbt_utils.star(
            from=src_person_government_id,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="pgi",
            prefix="government_id_",
        )
    }}, #}
from {{ ref_person_history }} as ph
left join {{ ref_person_preferred_salutation }} pps on ph.worker_id = pps.worker_id
left join {{ ref_person_communication }} pc on ph.worker_id = pc.worker_id
left join {{ src_other_personal_address }} opa on ph.worker_id = opa.worker_id
left join
    {{ src_person_disability }} pd on ph.worker_id = pd.worker_id

    {# left join {{ src_person_government_id }} pgi on ph.worker_id = pgi.worker_id #}
    
