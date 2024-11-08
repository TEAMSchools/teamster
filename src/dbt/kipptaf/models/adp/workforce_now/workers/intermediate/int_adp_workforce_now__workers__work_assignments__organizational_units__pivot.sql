with
    organizational_units as (
        select
            associate_oid,
            item_id,
            effective_date_start,
            effective_date_end,
            effective_date_timestamp,
            is_current_record,
            name_code__code_value,
            name_code__long_name,
            name_code__short_name,

            organizational_unit_type
            || replace(type_code__code_value, ' ', '') as pivot_column,
        from
            {{
                ref(
                    "int_adp_workforce_now__workers__work_assignments__organizational_units"
                )
            }}
    )

select
    associate_oid,
    item_id,
    effective_date_start,
    effective_date_end,
    effective_date_timestamp,
    is_current_record,

    code_value_assignedbusinessunit
    as organizational_unit__assigned__business_unit__code_value,
    code_value_assignedcostnumber
    as organizational_unit__assigned__cost_number__code_value,
    code_value_assigneddepartment
    as organizational_unit__assigned__department__code_value,
    code_value_homebusinessunit as organizational_unit__home__business_unit__code_value,
    code_value_homecostnumber as organizational_unit__home__cost_number__code_value,
    code_value_homedepartment as organizational_unit__home__department__code_value,

    coalesce(
        long_name_assignedbusinessunit, short_name_assignedbusinessunit
    ) as organizational_unit__assigned__business_unit__name,
    coalesce(
        long_name_assignedcostnumber, short_name_assignedcostnumber
    ) as organizational_unit__assigned__cost_number__name,
    coalesce(
        long_name_assigneddepartment, short_name_assigneddepartment
    ) as organizational_unit__assigned__department__name,
    coalesce(
        long_name_homebusinessunit, short_name_homebusinessunit
    ) as organizational_unit__home__business_unit__name,
    coalesce(
        long_name_homecostnumber, short_name_homecostnumber
    ) as organizational_unit__home__cost_number__name,
    coalesce(
        long_name_homedepartment, short_name_homedepartment
    ) as organizational_unit__home__department__name,
from
    organizational_units pivot (
        max(name_code__code_value) as code_value,
        max(name_code__long_name) as long_name,
        max(name_code__short_name) as short_name
        for pivot_column in (
            'assignedBusinessUnit',
            'assignedCostNumber',
            'assignedDepartment',
            'homeBusinessUnit',
            'homeCostNumber',
            'homeDepartment'
        )
    )
