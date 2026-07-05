with
    encoded as (
        select
            course_id,
            cast(course_sequence as string) as custom_4,
            cast(ocp as string) as custom_3,
        from {{ ref("stg_focus__courses") }}
    ),

    unpivoted as (
        select course_id, column_name, stored_value,
        from encoded unpivot (stored_value for column_name in (custom_4, custom_3))
    ),

    decoded as (
        select unpivoted.course_id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.stored_value in (`options`.option_id, `options`.code)
            and `options`.source_class = 'Course'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name
        in ('custom_4' as course_sequence_label, 'custom_3' as ocp_label)
    )
