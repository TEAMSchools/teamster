{%- set ref_contact = ref("stg_kippadb__contact") -%}
{%- set ref_user = ref("stg_kippadb__user") -%}
{%- set ref_record_type = ref("stg_kippadb__record_type") -%}

select
    {{ dbt_utils.star(from=ref_contact, relation_alias="c", prefix="contact_") }},

    {{
        dbt_utils.star(
            from=ref_user,
            relation_alias="u",
            prefix="contact_owner_",
            except=["id"],
        )
    }},

    {{
        dbt_utils.star(
            from=ref_record_type,
            relation_alias="rt",
            prefix="record_type_",
            except=["id"],
        )
    }},
from {{ ref_contact }} as c
left join {{ ref_user }} as u on c.owner_id = u.id
left join {{ ref_record_type }} as rt on c.record_type_id = rt.id
