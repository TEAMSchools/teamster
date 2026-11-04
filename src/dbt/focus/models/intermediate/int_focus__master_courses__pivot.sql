with
    encoded as (
        select
            course_id,
            cast(fefp as string) as custom_field_5,
            cast(course_flag_1 as string) as custom_field_6,
            cast(dual_enrollment_indicator as string) as custom_field_13,
            cast(course_history_term as string) as course_history_term,
            cast(course_level as string) as course_level,
            cast(ese as string) as ese,
            cast(ell_instruct_model as string) as ell_instruct_model,
            cast(de_inst_type as string) as de_inst_type,
            cast(online_course as string) as online_course,
            cast(distance_learning as string) as distance_learning,
            cast(career_pathway as string) as career_pathway,
        from {{ ref("stg_focus__master_courses") }}
    ),

    unpivoted as (
        select course_id, column_name, stored_value,
        from
            encoded unpivot (
                stored_value for column_name in (
                    custom_field_5,
                    custom_field_6,
                    custom_field_13,
                    course_history_term,
                    course_level,
                    ese,
                    ell_instruct_model,
                    de_inst_type,
                    online_course,
                    distance_learning,
                    career_pathway
                )
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
            'custom_field_13' as dual_enrollment_indicator_label,
            'course_history_term' as course_history_term_label,
            'course_level' as course_level_label,
            'ese' as ese_label,
            'ell_instruct_model' as ell_instruct_model_label,
            'de_inst_type' as de_inst_type_label,
            'online_course' as online_course_label,
            'distance_learning' as distance_learning_label,
            'career_pathway' as career_pathway_label
        )
    )
