with
    organizational_units as (
        select
            associate_oid,
            item_id,
            is_current_record,
            type_code__code_value,
            name_code__code_value,

            coalesce(name_code__long_name, name_code__short_name) as name_code__name,
        from
            {{
                ref(
                    "stg_adp_workforce_now__workers__work_assignments__assigned_organizational_units"
                )
            }}
    )

select *,
from
    organizational_units pivot (
        max(name_code__code_value) as code,
        max(name_code__name) as `name`
        for type_code__code_value in (
            'Business Unit' as business_unit,
            'Department' as department,
            'Cost Number' as cost_number
        )
    )
