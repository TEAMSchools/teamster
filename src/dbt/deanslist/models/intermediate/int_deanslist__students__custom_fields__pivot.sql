with
    pivot_source as (
        select student_school_id, field_name, `value` as field_value,
        from {{ ref("stg_deanslist__students__custom_fields") }}
    )

select *,
from
    pivot_source pivot (
        max(field_value) for field_name in (
            'Date deployed' as `date_deployed`,
            'Asset tag' as `asset_tag`,
            'Hotspot info' as `hotspot_info`,
            'Example Checkbox' as `example_checkbox`
        )
    )
