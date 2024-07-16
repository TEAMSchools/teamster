with
    assigned_organizational_units as (
        select
            wa.associate_oid,
            wa.as_of_date_timestamp,
            wa.item_id,

            aou.namecode.effectivedate as name_code__effective_date,
            aou.namecode.codevalue as name_code__code_value,
            aou.namecode.longname as name_code__long_name,
            aou.namecode.shortname as name_code__short_name,

            aou.typecode.effectivedate as type_code__effective_date,
            aou.typecode.codevalue as type_code__code_value,
            aou.typecode.longname as type_code__long_name,
            aou.typecode.shortname as type_code__short_name,

            {{ dbt_utils.generate_surrogate_key(["to_json_string(aou)"]) }}
            as surrogate_key,
        from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
        cross join unnest(wa.assigned_organizational_units) as aou
    )

    {{
        dbt_utils.deduplicate(
            relation="assigned_organizational_units",
            partition_by="associate_oid, item_id, surrogate_key",
            order_by="as_of_date_timestamp asc",
        )
    }}
