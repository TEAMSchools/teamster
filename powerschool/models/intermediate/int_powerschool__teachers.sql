{% set ref_users = ref("stg_powerschool__users") %}
{% set ref_schoolstaff = ref("stg_powerschool__schoolstaff") %}

select
    {{
        dbt_utils.star(
            from=ref_users,
            except=[
                "executionid",
                "ip_address",
                "psguid",
                "transaction_date",
                "whencreated",
                "whenmodified",
                "whocreated",
                "whomodified",
                "whomodifiedid",
                "whomodifiedtype",
            ],
            relation_alias="u",
        )
    }},
    {{
        dbt_utils.star(
            from=ref_schoolstaff,
            except=[
                "users_dcid",
                "dcid",
                "executionid",
                "ip_address",
                "psguid",
                "transaction_date",
                "whencreated",
                "whenmodified",
                "whocreated",
                "whomodified",
                "whomodifiedid",
                "whomodifiedtype",
            ],
            relation_alias="ss",
        )
    }},
from {{ ref_users }} as u
inner join {{ ref_schoolstaff }} as ss on u.dcid = ss.users_dcid
