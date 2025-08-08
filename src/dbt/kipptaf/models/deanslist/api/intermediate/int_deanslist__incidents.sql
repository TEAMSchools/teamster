with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    ),

    transformations as (
        -- trunk-ignore(sqlfluff/AM04)
        select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as source_project,
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
            (category_tier in ('T1', 'Tier 1') and source_project != 'kippmiami')
            or (category_tier in ('T4', 'T3') and source_project = 'kippmiami')
        then 'Low'
        when category_tier in ('T2', 'Tier 2')
        then 'Middle'
        when
            (category_tier in ('T3', 'Tier 3') and source_project != 'kippmiami')
            or (category_tier = 'T1' and source_project = 'kippmiami')
        then 'High'
        when category is null
        then null
        else 'Other'
    end as referral_tier,
from transformations
