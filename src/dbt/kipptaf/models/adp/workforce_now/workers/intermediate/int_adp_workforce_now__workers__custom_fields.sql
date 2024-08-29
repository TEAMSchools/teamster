with
    workers_current_record as (
        select
            associate_oid,
            custom_field_group__code_fields,
            custom_field_group__date_fields,
            custom_field_group__indicator_fields,
            custom_field_group__multi_code_fields,
            custom_field_group__number_fields,
            custom_field_group__string_fields,
            person__custom_field_group__code_fields,
            person__custom_field_group__date_fields,
            person__custom_field_group__indicator_fields,
            person__custom_field_group__multi_code_fields,
            person__custom_field_group__number_fields,
            person__custom_field_group__string_fields,
        from {{ ref("stg_adp_workforce_now__workers") }}
        where is_current_record
    ),

    multi_code_fields as (
        select
            wcr.associate_oid,

            cfg.itemid as item_id,
            cfg.namecode.codevalue as name_code__code_value,
            cfg.namecode.longname as name_code__long_name,
            cfg.namecode.shortname as name_code__short_name,
            cfg.namecode.effectivedate as name_code__effective_date,

            cfg.codes,
        from workers_current_record as wcr
        cross join unnest(wcr.custom_field_group__multi_code_fields) as cfg

        union all

        select
            wcr.associate_oid,

            cfg.itemid as item_id,
            cfg.namecode.codevalue as name_code__code_value,
            cfg.namecode.longname as name_code__long_name,
            cfg.namecode.shortname as name_code__short_name,
            cfg.namecode.effectivedate as name_code__effective_date,

            cfg.codes,
        from workers_current_record as wcr
        cross join unnest(wcr.person__custom_field_group__multi_code_fields) as cfg
    )

select
    wcr.associate_oid,

    cfg.itemid as item_id,
    cfg.namecode.codevalue as name_code__code_value,
    cfg.namecode.longname as name_code__long_name,
    cfg.namecode.shortname as name_code__short_name,
    cfg.namecode.effectivedate as name_code__effective_date,

    cfg.datevalue as date_value,

    null as indicator_value,
    null as number_value,
    null as string_value,
    null as code_value,
    null as long_name,
    null as short_name,
    null as effective_date,
from workers_current_record as wcr
cross join unnest(wcr.custom_field_group__date_fields) as cfg

union all

select
    wcr.associate_oid,

    cfg.itemid as item_id,
    cfg.namecode.codevalue as name_code__code_value,
    cfg.namecode.longname as name_code__long_name,
    cfg.namecode.shortname as name_code__short_name,
    cfg.namecode.effectivedate as name_code__effective_date,

    null as date_value,

    cfg.indicatorvalue as indicator_value,

    null as number_value,
    null as string_value,
    null as code_value,
    null as long_name,
    null as short_name,
    null as effective_date,
from workers_current_record as wcr
cross join unnest(wcr.custom_field_group__indicator_fields) as cfg

union all

select
    wcr.associate_oid,

    cfg.itemid as item_id,
    cfg.namecode.codevalue as name_code__code_value,
    cfg.namecode.longname as name_code__long_name,
    cfg.namecode.shortname as name_code__short_name,
    cfg.namecode.effectivedate as name_code__effective_date,

    null as date_value,
    null as indicator_value,

    cfg.numbervalue as number_value,

    null as string_value,
    null as code_value,
    null as long_name,
    null as short_name,
    null as effective_date,
from workers_current_record as wcr
cross join unnest(wcr.custom_field_group__number_fields) as cfg

union all

select
    wcr.associate_oid,

    cfg.itemid as item_id,
    cfg.namecode.codevalue as name_code__code_value,
    cfg.namecode.longname as name_code__long_name,
    cfg.namecode.shortname as name_code__short_name,
    cfg.namecode.effectivedate as name_code__effective_date,

    null as date_value,
    null as indicator_value,
    null as number_value,

    cfg.stringvalue as string_value,

    null as code_value,
    null as long_name,
    null as short_name,
    null as effective_date,
from workers_current_record as wcr
cross join unnest(wcr.custom_field_group__string_fields) as cfg

union all

select
    wcr.associate_oid,

    cfg.itemid as item_id,
    cfg.namecode.codevalue as name_code__code_value,
    cfg.namecode.longname as name_code__long_name,
    cfg.namecode.shortname as name_code__short_name,
    cfg.namecode.effectivedate as name_code__effective_date,

    null as date_value,
    null as indicator_value,
    null as number_value,
    null as string_value,

    cfg.codevalue as code_value,
    cfg.longname as long_name,
    cfg.shortname as short_name,
    cfg.effectivedate as effective_date,
from workers_current_record as wcr
cross join unnest(wcr.custom_field_group__code_fields) as cfg

union all

select
    mcf.associate_oid,
    mcf.item_id,
    mcf.name_code__code_value,
    mcf.name_code__long_name,
    mcf.name_code__short_name,
    mcf.name_code__effective_date,

    null as date_value,
    null as indicator_value,
    null as number_value,
    null as string_value,

    c.codevalue as code_value,
    c.longname as long_name,
    c.shortname as short_name,
    c.effectivedate as effective_date,
from multi_code_fields as mcf
cross join unnest(codes) as c
