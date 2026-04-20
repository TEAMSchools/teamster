with
    detail_records as (
        select
            'D1' as field_1,
            '' as field_2,
            coalesce(r.first_name, '') as field_3,
            '' as field_4,
            coalesce(r.last_name, '') as field_5,
            '' as field_6,
            coalesce(
                cast(format_date('%Y%m%d', r.contact_birthdate) as string), ''
            ) as field_7,
            coalesce(
                cast(
                    format_date(
                        '%Y%m%d',
                        date(
                            extract(year from r.contact_actual_hs_graduation_date),
                            8,
                            1
                        )
                    ) as string
                ),
                ''
            ) as field_8,
            '' as field_9,
            '' as field_10,
            '00' as field_11,
            coalesce(r.contact_id, '') as field_12,
        from {{ ref("int_kippadb__roster") }} as r
    ),

    record_count as (select count(*) as n from detail_records),

    header as (
        select
            'H1' as field_1,
            '601193' as field_2,
            '00' as field_3,
            'KIPP Through College New Jersey' as field_4,
            cast(
                format_date('%Y%m%d', current_date('{{ var("local_timezone") }}'))
                as string
            ) as field_5,
            'DA' as field_6,
            'S' as field_7,
            '' as field_8,
            '' as field_9,
            '' as field_10,
            '' as field_11,
            '' as field_12,
    ),

    trailer as (
        select
            'T1' as field_1,
            cast(n as string) as field_2,
            '' as field_3,
            '' as field_4,
            '' as field_5,
            '' as field_6,
            '' as field_7,
            '' as field_8,
            '' as field_9,
            '' as field_10,
            '' as field_11,
            '' as field_12,
        from record_count
    )

select
    field_1,
    field_2,
    field_3,
    field_4,
    field_5,
    field_6,
    field_7,
    field_8,
    field_9,
    field_10,
    field_11,
    field_12,
from header
union all
select
    field_1,
    field_2,
    field_3,
    field_4,
    field_5,
    field_6,
    field_7,
    field_8,
    field_9,
    field_10,
    field_11,
    field_12,
from detail_records
union all
select
    field_1,
    field_2,
    field_3,
    field_4,
    field_5,
    field_6,
    field_7,
    field_8,
    field_9,
    field_10,
    field_11,
    field_12,
from trailer
