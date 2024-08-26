with
    work_assignments as (
        select
            associate_oid,
            item_id,
            effective_date_start,
            effective_date_end,
            effective_date_timestamp,
            is_current_record,
            custom_field_group__code_fields,
            custom_field_group__date_fields,
            custom_field_group__indicator_fields,
            custom_field_group__multi_code_fields,
            custom_field_group__number_fields,
            custom_field_group__string_fields,
        from {{ ref("stg_adp_workforce_now__workers__work_assignments") }}
    ),

    multi_code_fields as (
        select
            wa.associate_oid,
            wa.item_id,
            wa.effective_date_start,
            wa.effective_date_end,
            wa.effective_date_timestamp,
            wa.is_current_record,

            cfg.itemid as custom_field_item_id,
            cfg.namecode.codevalue as name_code__code_value,
            cfg.namecode.longname as name_code__long_name,
            cfg.namecode.shortname as name_code__short_name,
            cfg.namecode.effectivedate as name_code__effective_date,

            cfg.codes,
        from work_assignments as wa
        cross join unnest(wa.custom_field_group__multi_code_fields) as cfg
    )

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    cfg.itemid as custom_field_item_id,
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
from work_assignments as wa
cross join unnest(wa.custom_field_group__date_fields) as cfg

union all

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    cfg.itemid as custom_field_item_id,
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
from work_assignments as wa
cross join unnest(wa.custom_field_group__indicator_fields) as cfg

union all

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    cfg.itemid as custom_field_item_id,
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
from work_assignments as wa
cross join unnest(wa.custom_field_group__number_fields) as cfg

union all

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    cfg.itemid as custom_field_item_id,
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
from work_assignments as wa
cross join unnest(wa.custom_field_group__string_fields) as cfg

union all

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    cfg.itemid as custom_field_item_id,
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
from work_assignments as wa
cross join unnest(wa.custom_field_group__code_fields) as cfg

union all

select
    mcf.associate_oid,
    mcf.item_id,
    mcf.effective_date_start,
    mcf.effective_date_end,
    mcf.effective_date_timestamp,
    mcf.is_current_record,
    mcf.custom_field_item_id,
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
