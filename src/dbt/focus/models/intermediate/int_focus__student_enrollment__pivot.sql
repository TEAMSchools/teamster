with
    encoded as (
        select
            id,
            cast(prior_district as string) as custom_1,
            cast(prior_state as string) as custom_2,
            cast(prior_country as string) as custom_3,
            cast(educational_choice as string) as custom_4,
            cast(student_offender_transfer as string) as custom_6,
            cast(resident_status_state_county as string) as custom_18,
            cast(disaster_affected_student as string) as custom_5,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    unpivoted as (
        select id, column_name, stored_value,
        from
            encoded unpivot (
                stored_value for column_name in (
                    custom_1,
                    custom_2,
                    custom_3,
                    custom_4,
                    custom_6,
                    custom_18,
                    custom_5
                )
            )
    ),

    decoded as (
        select unpivoted.id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.stored_value in (`options`.option_id, `options`.code)
            and `options`.source_class = 'StudentEnrollment'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name in (
            'custom_1' as prior_district_label,
            'custom_2' as prior_state_label,
            'custom_3' as prior_country_label,
            'custom_4' as educational_choice_label,
            'custom_6' as student_offender_transfer_label,
            'custom_18' as resident_status_state_county_label,
            'custom_5' as disaster_affected_student_label
        )
    )
