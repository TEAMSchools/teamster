with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "stg_deanslist__incidents"),
                    source("kippcamden_deanslist", "stg_deanslist__incidents"),
                    source("kippmiami_deanslist", "stg_deanslist__incidents"),
                ]
            )
        }}
    )

select
    *,

    case
        when category_tier in ('SW', 'SS', 'SSC')
        then 'Social Work'
        when category_tier = 'TX'
        then 'Non-Behavioral'
        when category in ('School Clinic', 'Incident Report/Accident Report')
        then 'Non-Behavioral'
        /* Miami-only */
        when category_tier in ('T4', 'T3') and _dbt_source_relation like '%kippmiami%'
        then 'Low'
        when category_tier = 'T1' and _dbt_source_relation like '%kippmiami%'
        then 'High'
        /* all other regions */
        when category_tier in ('T1', 'Tier 1')
        then 'Low'
        when category_tier in ('T2', 'Tier 2')
        then 'Middle'
        when category_tier in ('T3', 'Tier 3')
        then 'High'
        when category is not null
        then 'Other'
    end as referral_tier,
from transformations
