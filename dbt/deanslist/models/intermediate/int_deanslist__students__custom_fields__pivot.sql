with
    pivot_source as (
        select student_school_id, field_name, `value` as field_value,
        from {{ ref("stg_deanslist__students__custom_fields") }}
    )

select *,
from
    pivot_source pivot (
        max(field_value) for field_name in (
            '10th hours' as `10th_hours`,
            '11th hours' as `11th_hours`,
            '12th hours' as `12th_hours`,
            '9th hours' as `9th_hours`,
            'Asset tag' as `asset_tag`,
            'Date deployed' as `date_deployed`,
            'Example Checkbox' as `example_checkbox`,
            'Graduation Date' as `graduation_date`,
            'Hotspot info' as `hotspot_info`,
            'Locker Combo' as `locker_combo`,
            'Locker Number' as `locker_number`
        )
    )
