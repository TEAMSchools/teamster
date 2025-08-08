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
    ),

    transformations as (
        select
            *,

            regexp_extract(category, r'^(.*?)\s*-\s*') as category_tier,

            {{
                date_to_fiscal_year(
                    date_field="create_ts_date", start_month=7, year_source="start"
                )
            }} as create_ts_academic_year,
        from union_relations
    )

select
    *,

    case
        when category_tier in ('SW', 'SS', 'SSC')
        then 'Social Work'
        when
            (
                category_tier = 'TX'
                or category in ('School Clinic', 'Incident Report/Accident Report')
            )
        then 'Non-Behavioral'
        when
            (
                category_tier in ('T1', 'Tier 1')
                and _dbt_source_relation not like '%kippmiami%'
            )
            or (
                category_tier in ('T4', 'T3')
                and _dbt_source_relation like '%kippmiami%'
            )
        then 'Low'
        when category_tier in ('T2', 'Tier 2')
        then 'Middle'
        when
            (
                category_tier in ('T3', 'Tier 3')
                and _dbt_source_relation not like '%kippmiami%'
            )
            or (category_tier = 'T1' and _dbt_source_relation like '%kippmiami%')
        then 'High'
        when category is null
        then null
        else 'Other'
    end as referral_tier,
from transformations
