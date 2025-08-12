select
    {{
        dbt_utils.star(
            from=ref("stg_kippadb__contact"), relation_alias="c", prefix="contact_"
        )
    }},

    {{
        dbt_utils.star(
            from=ref("stg_kippadb__user"),
            relation_alias="u",
            prefix="contact_owner_",
            except=["id"],
        )
    }},

    {{
        dbt_utils.star(
            from=ref("stg_kippadb__record_type"),
            relation_alias="rt",
            prefix="record_type_",
            except=["id"],
        )
    }},

    c.last_name || ', ' || c.first_name as contact_lastfirst,

    (
        {{ var("current_fiscal_year") }}
        - extract(year from c.actual_hs_graduation_date)
    ) as years_out_of_hs,
from {{ ref("stg_kippadb__contact") }} as c
left join {{ ref("stg_kippadb__user") }} as u on c.owner_id = u.id
left join {{ ref("stg_kippadb__record_type") }} as rt on c.record_type_id = rt.id
