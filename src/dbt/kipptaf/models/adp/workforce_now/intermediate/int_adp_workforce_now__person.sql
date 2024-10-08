{%- set ref_person_history = ref("stg_adp_workforce_now__person_history") -%}
{%- set ref_person_disability = ref("stg_adp_workforce_now__person_disability") -%}
{%- set ref_other_personal_address = ref(
    "stg_adp_workforce_now__other_personal_address"
) -%}
{%- set ref_person_preferred_salutation = ref(
    "int_adp_workforce_now__person_preferred_salutation_pivot"
) -%}
{%- set ref_person_communication = ref(
    "int_adp_workforce_now__person_communication_pivot"
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
            from=ref_other_personal_address,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="opa",
            prefix="other_personal_address_",
        )
    }},

    {{
        dbt_utils.star(
            from=ref_person_disability,
            except=["_fivetran_synced", "worker_id"],
            relation_alias="pd",
            prefix="disability_",
        )
    }},
from {{ ref_person_history }} as ph
left join {{ ref_person_preferred_salutation }} as pps on ph.worker_id = pps.worker_id
left join {{ ref_person_communication }} as pc on ph.worker_id = pc.worker_id
left join {{ ref_other_personal_address }} as opa on ph.worker_id = opa.worker_id
left join {{ ref_person_disability }} as pd on ph.worker_id = pd.worker_id
