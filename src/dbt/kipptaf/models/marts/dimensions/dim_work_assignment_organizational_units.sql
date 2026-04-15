with
    org_units as (
        select
            ou.item_id,
            ou.effective_date_start,
            ou.organizational_unit_type as assignment_type,
            ou.type_code__code_value,
            ou.name_code__code_value,
            ou.name_code__long_name,
            ou.name_code__short_name,

            coalesce(ou.name_code__long_name, ou.name_code__short_name) as `name`,
        from
            {{
                ref(
                    "int_adp_workforce_now__workers__work_assignments__organizational_units"
                )
            }}
            as ou
    ),

    pivoted as (
        select
            item_id,
            effective_date_start,
            assignment_type,

            max(
                if(type_code__code_value = 'Business Unit', name_code__code_value, null)
            ) as business_unit_code,
            max(
                if(type_code__code_value = 'Business Unit', `name`, null)
            ) as business_unit_name,
            max(
                if(type_code__code_value = 'Department', name_code__code_value, null)
            ) as department_code,
            max(
                if(type_code__code_value = 'Department', `name`, null)
            ) as department_name,
            max(
                if(type_code__code_value = 'Cost Number', name_code__code_value, null)
            ) as cost_number_code,
            max(
                if(type_code__code_value = 'Cost Number', `name`, null)
            ) as cost_number_name,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "assignment_type",
                        "max(if(type_code__code_value = 'Business Unit', name_code__code_value, null))",
                        "max(if(type_code__code_value = 'Department', name_code__code_value, null))",
                        "max(if(type_code__code_value = 'Cost Number', name_code__code_value, null))",
                    ]
                )
            }}
            as attribute_hash,
        from org_units
        group by item_id, effective_date_start, assignment_type
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by item_id, assignment_type order by effective_date_start asc
            ) as attribute_hash_lag,
        from pivoted
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            assignment_type,
            business_unit_code,
            business_unit_name,
            department_code,
            department_name,
            cost_number_code,
            cost_number_name,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id, assignment_type
                        order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where attribute_hash != attribute_hash_lag
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "item_id",
                "assignment_type",
                "effective_date_start",
            ]
        )
    }} as work_assignment_organizational_unit_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    assignment_type,
    business_unit_code,
    business_unit_name,
    department_code,
    department_name,
    cost_number_code,
    cost_number_name,
    effective_date_start,
    effective_date_end,

    if(effective_date_end = '9999-12-31', true, false) as is_current_record,
from change_points
