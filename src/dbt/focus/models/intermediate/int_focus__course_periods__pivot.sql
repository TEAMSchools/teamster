with
    encoded as (
        select
            course_period_id,
            cast(fefp_number as string) as custom_2,
            cast(scheduling_method as string) as custom_4,
            cast(facility_type as string) as custom_6,
            cast(cert_licensure_qual_status as string) as custom_28,
            cast(highly_qualified as string) as custom_5,
            cast(reading_intervention_component as string) as custom_25,
            cast(location_of_student as string) as custom_33,
            cast(eoc_exam_term as string) as custom_34,
            cast(basic_skills_exam as string) as custom_22,
        from {{ ref("stg_focus__course_periods") }}
    ),

    unpivoted as (
        select course_period_id, column_name, stored_value,
        from
            encoded unpivot (
                stored_value for column_name in (
                    custom_2,
                    custom_4,
                    custom_6,
                    custom_28,
                    custom_5,
                    custom_25,
                    custom_33,
                    custom_34,
                    custom_22
                )
            )
    ),

    decoded as (
        select unpivoted.course_period_id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.stored_value in (`options`.option_id, `options`.code)
            and `options`.source_class = 'CoursePeriod'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name in (
            'custom_2' as fefp_number_label,
            'custom_4' as scheduling_method_label,
            'custom_6' as facility_type_label,
            'custom_28' as cert_licensure_qual_status_label,
            'custom_5' as highly_qualified_label,
            'custom_25' as reading_intervention_component_label,
            'custom_33' as location_of_student_label,
            'custom_34' as eoc_exam_term_label,
            'custom_22' as basic_skills_exam_label
        )
    )
