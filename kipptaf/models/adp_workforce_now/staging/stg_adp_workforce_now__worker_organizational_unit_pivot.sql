with
    ou_unpivot as (
        select
            id,
            lower(regexp_replace(type_short_name, r'\W', '_')) as type_short_name,
            name_column,
            values_column,
        from
            {{ source("adp_workforce_now", "organizational_unit") }}
            unpivot exclude nulls(
                values_column for name_column
                in (`name`, name_long_name, name_short_name)
            )
    ),

    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "adp_workforce_now",
                        "worker_assigned_organizational_unit",
                    ),
                    source(
                        "adp_workforce_now",
                        "worker_home_organizational_unit",
                    ),
                ],
                exclude=["_fivetran_synced"],
            )
        }}
    ),

    wou_join as (
        select
            ur.worker_assignment_id,

            ouu.values_column,
            lower(regexp_replace(ouu.type_short_name, r'\W', '_'))
            || '_'
            || regexp_extract(
                ur._dbt_source_relation, r'worker_(\w+)_organizational_unit'
            )
            || '_'
            || ouu.name_column as input_column,
        from union_relations as ur
        inner join ou_unpivot as ouu on ur.id = ouu.id
    )

select *
from
    wou_join pivot (
        max(values_column) for input_column in (
            'business_unit_assigned_name_long_name',
            'business_unit_assigned_name_short_name',
            'business_unit_assigned_name',
            'business_unit_home_name_long_name',
            'business_unit_home_name_short_name',
            'business_unit_home_name',
            'cost_number_assigned_name_short_name',
            'cost_number_assigned_name',
            'cost_number_home_name_short_name',
            'cost_number_home_name',
            'department_assigned_name_long_name',
            'department_assigned_name_short_name',
            'department_assigned_name',
            'department_home_name_long_name',
            'department_home_name_short_name',
            'department_home_name'
        )
    )
