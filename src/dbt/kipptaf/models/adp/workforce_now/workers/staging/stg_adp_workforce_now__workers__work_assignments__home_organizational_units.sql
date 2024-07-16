with
    -- trunk-ignore(sqlfluff/ST03)
    assigned_organizational_units as (
        select
            wa.associate_oid,
            wa.item_id,
            wa.effective_date_start,
            wa.effective_date_timestamp,

            hou.typecode.effectivedate as type_code__effective_date,
            hou.typecode.codevalue as type_code__code_value,
            hou.typecode.longname as type_code__long_name,
            hou.typecode.shortname as type_code__short_name,

            hou.namecode.effectivedate as name_code__effective_date,
            hou.namecode.codevalue as name_code__code_value,
            hou.namecode.longname as name_code__long_name,
            hou.namecode.shortname as name_code__short_name,

            {{ dbt_utils.generate_surrogate_key(["to_json_string(hou)"]) }}
            as surrogate_key,
        from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
        cross join unnest(wa.home_organizational_units) as hou
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="assigned_organizational_units",
                partition_by="associate_oid, item_id, surrogate_key",
                order_by="effective_date_timestamp asc",
            )
        }}
    ),

    with_end_date as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            coalesce(
                date_sub(
                    lead(effective_date_start, 1) over (
                        partition by associate_oid, item_id, type_code__code_value
                        order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                '9999-12-31'
            ) as effective_date_end,
        from deduplicate
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date_start and effective_date_end,
        true,
        false
    ) as is_current_record,
from with_end_date
