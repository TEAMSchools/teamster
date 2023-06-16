with
    ou_union as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "adp_workforce_now", "worker_assigned_organizational_unit"
                    ),
                    source("adp_workforce_now", "worker_home_organizational_unit"),
                ],
                exclude=["_fivetran_synced"],
            )
        }}
    ),
    ou_coalesce as (
        select
            id, type_short_name, coalesce(name_short_name, name_long_name, name) as name
        from {{ source("adp_workforce_now", "organizational_unit") }}
    ),
    ou_join as (
        select
            ouu.worker_assignment_id,
            ouc.name,
            (
                lower(regexp_replace(ouc.type_short_name, r'\W', '_'))
                || '_'
                || regexp_extract(
                    ouu._dbt_source_relation, r'worker_(\w+)_organizational_unit'
                )
            ) as input_column,
        from ou_union as ouu
        inner join ou_coalesce as ouc on ouu.id = ouc.id
    )

select *
from
    ou_join pivot (
        max(name) for input_column in (
            'business_unit_assigned',
            'business_unit_home',
            'cost_number_assigned',
            'cost_number_home',
            'department_assigned',
            'department_home'
        )
    )
