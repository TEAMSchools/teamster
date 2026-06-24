with
    cf as (
        select id, source_class, lower(column_name) as column_name,
        from {{ ref("stg_focus__custom_fields") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    opt as (
        select source_id, code, label, updated_at,
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomField' and code is not null
    ),

    opt_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="opt",
                partition_by="source_id, code",
                order_by="updated_at desc",
            )
        }}
    )

select cf.source_class, cf.column_name, opt_deduped.code, opt_deduped.label,
from opt_deduped
inner join cf on opt_deduped.source_id = cf.id
