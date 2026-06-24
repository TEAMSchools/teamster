with
    cf as (
        select id, source_class, lower(column_name) as column_name,
        from {{ ref("stg_focus__custom_fields") }}
    ),

    opt as (
        select cast(id as string) as option_id, source_id, code, label,
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomField'  -- owner-type filter; keep inactive
    )

select opt.option_id, cf.source_class, cf.column_name, opt.code, opt.label,
from opt
inner join cf on opt.source_id = cf.id
