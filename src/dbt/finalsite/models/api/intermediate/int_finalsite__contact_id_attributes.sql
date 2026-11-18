with
    attributes as (
        select
            c.finalsite_enrollment_id,
            c.school_year_start,
            c.application_submit_date,

            a.field_name,
            a.value.string_value as value_string,
        from {{ ref("stg_finalsite__contacts") }} as c
        cross join unnest(c.id_attributes) as a
    ),

    pivoted as (
        select
            finalsite_enrollment_id,
            school_year_start,
            application_submit_date,
            power_school_contact_id,
            powerschool_student_number,
            focus_student_id,
        from
            attributes pivot (
                max(value_string)
                for field_name in (
                    'power_school_contact_id',
                    'powerschool_student_number',
                    'focus_student_id'
                )
            )
    ),

    ranked as (
        select
            finalsite_enrollment_id,
            power_school_contact_id,
            powerschool_student_number,
            focus_student_id,

            concat('8400', focus_student_id) as focus_student_id_prefixed,

            row_number() over (
                partition by powerschool_student_number
                order by
                    school_year_start desc,
                    application_submit_date desc,
                    finalsite_enrollment_id desc
            ) as rn_powerschool_student_number,
        from pivoted
    )

select
    finalsite_enrollment_id,
    power_school_contact_id,
    powerschool_student_number,
    focus_student_id,
    focus_student_id_prefixed,

    powerschool_student_number is not null
    and rn_powerschool_student_number = 1 as is_latest_powerschool_student_number,
from ranked
