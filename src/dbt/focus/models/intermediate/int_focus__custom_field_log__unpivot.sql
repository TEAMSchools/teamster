with
    entries as (
        select
            id as log_entry_id,
            source_id as student_id,
            school_id,
            field_id,
            syear,
            created_at,
            updated_at,
            cast(log_field1 as string) as log_field1,
            cast(log_field2 as string) as log_field2,
            cast(log_field3 as string) as log_field3,
            cast(log_field4 as string) as log_field4,
            cast(log_field5 as string) as log_field5,
            cast(log_field6 as string) as log_field6,
            cast(log_field7 as string) as log_field7,
            cast(log_field8 as string) as log_field8,
            cast(log_field9 as string) as log_field9,
            cast(log_field10 as string) as log_field10,
            cast(log_field11 as string) as log_field11,
            cast(log_field12 as string) as log_field12,
            cast(log_field13 as string) as log_field13,
            cast(log_field14 as string) as log_field14,
            cast(log_field15 as string) as log_field15,
            cast(log_field16 as string) as log_field16,
            cast(log_field17 as string) as log_field17,
            cast(log_field18 as string) as log_field18,
            cast(log_field19 as string) as log_field19,
            cast(log_field20 as string) as log_field20,
            cast(log_field21 as string) as log_field21,
            cast(log_field22 as string) as log_field22,
            cast(log_field23 as string) as log_field23,
            cast(log_field24 as string) as log_field24,
            cast(log_field25 as string) as log_field25,
            cast(log_field26 as string) as log_field26,
            cast(log_field27 as string) as log_field27,
            cast(log_field28 as string) as log_field28,
            cast(log_field29 as string) as log_field29,
            cast(log_field30 as string) as log_field30,
        from {{ ref("stg_focus__custom_field_log_entries") }}
    ),

    unpivoted as (
        select
            log_entry_id,
            student_id,
            school_id,
            field_id,
            syear,
            created_at,
            updated_at,
            slot_column_name,
            value,
        from
            entries unpivot (
                value for slot_column_name in (
                    log_field1,
                    log_field2,
                    log_field3,
                    log_field4,
                    log_field5,
                    log_field6,
                    log_field7,
                    log_field8,
                    log_field9,
                    log_field10,
                    log_field11,
                    log_field12,
                    log_field13,
                    log_field14,
                    log_field15,
                    log_field16,
                    log_field17,
                    log_field18,
                    log_field19,
                    log_field20,
                    log_field21,
                    log_field22,
                    log_field23,
                    log_field24,
                    log_field25,
                    log_field26,
                    log_field27,
                    log_field28,
                    log_field29,
                    log_field30
                )
            )
    ),

    columns_meta as (
        select
            id as log_column_id,
            field_id,
            type as slot_type,
            title as slot_title,
            sort_order as slot_sort_order,
            lower(column_name) as slot_column_name,
        from {{ ref("stg_focus__custom_field_log_columns") }}
    ),

    fields_meta as (
        select id as field_id, title as field_title,
        from {{ ref("stg_focus__custom_fields") }}
    ),

    options as (
        select cast(id as string) as option_id, source_id, code, label,
        from {{ ref("stg_focus__custom_field_select_options") }}
        where source_class = 'CustomFieldLogColumn'
    )

select
    unpivoted.log_entry_id,
    unpivoted.student_id,
    unpivoted.school_id,
    unpivoted.field_id,
    columns_meta.log_column_id,
    columns_meta.slot_column_name,
    columns_meta.slot_type,
    columns_meta.slot_title,
    columns_meta.slot_sort_order,
    fields_meta.field_title,
    unpivoted.value,
    unpivoted.syear,
    unpivoted.created_at,
    unpivoted.updated_at,
    options.label as value_label,
from unpivoted
inner join
    columns_meta
    on unpivoted.field_id = columns_meta.field_id
    and unpivoted.slot_column_name = columns_meta.slot_column_name
left join fields_meta on unpivoted.field_id = fields_meta.field_id
left join
    options
    on columns_meta.log_column_id = options.source_id
    and unpivoted.value in (options.option_id, options.code)
