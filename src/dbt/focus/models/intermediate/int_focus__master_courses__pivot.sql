with
    encoded as (
        select
            course_id,
            cast(fefp as string) as custom_field_5,
            cast(course_flag_1 as string) as custom_field_6,
            cast(dual_enrollment_indicator as string) as custom_field_13,
        from {{ ref("stg_focus__master_courses") }}
    ),

    unpivoted as (
        select course_id, column_name, stored_value,
        from
            encoded unpivot (
                stored_value for column_name
                in (custom_field_5, custom_field_6, custom_field_13)
            )
    ),

    decoded as (
        select unpivoted.course_id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.stored_value in (`options`.option_id, `options`.code)
            and `options`.source_class = 'CourseCatalog'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name in (
            'custom_field_5' as fefp_label,
            'custom_field_6' as course_flag_1_label,
            'custom_field_13' as dual_enrollment_indicator_label
        )
    )
