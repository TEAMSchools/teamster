with
    encoded as (
        select
            id,
            cast(school_level as string) as custom_100000004,
            cast(school_type as string) as custom_200000326,
            cast(technical_center as string) as custom_50000002,
        from {{ ref("stg_focus__schools") }}
    ),

    unpivoted as (
        select id, column_name, option_id,
        from
            encoded unpivot (
                option_id for column_name
                in (custom_100000004, custom_200000326, custom_50000002)
            )
    ),

    decoded as (
        select unpivoted.id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.option_id = `options`.option_id
            and `options`.source_class = 'SISSchool'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name in (
            'custom_100000004' as school_level_label,
            'custom_200000326' as school_type_label,
            'custom_50000002' as technical_center_label
        )
    )
