with
    today as (
        select
            current_date('{{ var("local_timezone") }}') as today,
            if(
                extract(month from current_date('{{ var("local_timezone") }}')) >= 9,
                extract(year from current_date('{{ var("local_timezone") }}')),
                extract(year from current_date('{{ var("local_timezone") }}')) - 1
            ) as max_graduation_year,
    ),

    search_begin_date as (
        select
            {%- if var("nsc_search_begin_date", none) is not none %}
                date('{{ var("nsc_search_begin_date") }}') as search_begin_date,
            {%- else %}
                case
                    when extract(month from today) between 7 and 11
                    then date(extract(year from today), 6, 1)
                    when extract(month from today) = 12
                    then date(extract(year from today), 11, 1)
                    when extract(month from today) between 4 and 6
                    then date(extract(year from today), 3, 1)
                    else date(extract(year from today) - 1, 11, 1)
                end as search_begin_date,
            {%- endif %}
        from today
    ),

    detail_records as (
        select
            r.contact_id,
            r.first_name,
            r.last_name,
            r.contact_birthdate,

            s.search_begin_date,
        from {{ ref("int_kippadb__roster") }} as r
        cross join search_begin_date as s
        cross join today as t
        where
            r.contact_id is not null
            and r.contact_graduation_year >= t.max_graduation_year - 5
            and r.contact_graduation_year <= t.max_graduation_year
    ),

    record_count as (select count(*) as n from detail_records),

    -- trunk-ignore(sqlfluff/ST06): positional NSC file format requires fixed column
    -- order
    header as (
        select
            1 as row_order,
            'H1' as field_1,
            '601193' as field_2,
            '00' as field_3,
            'KIPP Through College New Jersey' as field_4,
            cast(format_date('%Y%m%d', t.today) as string) as field_5,
            'DA' as field_6,
            'S' as field_7,
            '' as field_8,
            '' as field_9,
            '' as field_10,
            '' as field_11,
            '' as field_12,
        from today as t
    ),

    -- trunk-ignore(sqlfluff/ST06): positional NSC file format requires fixed column
    -- order
    formatted_details as (
        select
            2 as row_order,
            'D1' as field_1,
            '' as field_2,
            coalesce(first_name, '') as field_3,
            '' as field_4,
            coalesce(last_name, '') as field_5,
            '' as field_6,
            coalesce(
                cast(format_date('%Y%m%d', contact_birthdate) as string), ''
            ) as field_7,
            coalesce(
                cast(format_date('%Y%m%d', search_begin_date) as string), ''
            ) as field_8,
            '' as field_9,
            '' as field_10,
            '00' as field_11,
            coalesce(contact_id, '') as field_12,
        from detail_records
    ),

    -- trunk-ignore(sqlfluff/ST06): positional NSC file format requires fixed column
    -- order
    trailer as (
        select
            3 as row_order,
            'T1' as field_1,
            cast(n + 2 as string) as field_2,
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
    row_order,
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
    row_order,
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
from formatted_details
union all
select
    row_order,
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
