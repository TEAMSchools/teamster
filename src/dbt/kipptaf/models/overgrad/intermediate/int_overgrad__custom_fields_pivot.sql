with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_overgrad__admissions__custom_field_values"),
                    ref("stg_overgrad__students__custom_field_values"),
                ]
            )
        }}
    ),

    translations as (

        select
            ur._dbt_source_relation,
            ur.id,

            cf.name,

            case
                when cf.field_type = 'date'
                then ur.date
                when cf.field_type = 'number'
                then cast(ur.number as string)
                when cf.field_type = 'select'
                then cfo.label
            end as `value`,
        from union_relations as ur
        inner join
            {{ ref("stg_overgrad__custom_fields") }} as cf on ur.custom_field_id = cf.id
        left join
            {{ ref("stg_overgrad__custom_fields__custom_field_options") }} as cfo
            on ur.custom_field_id = cfo.id
            and ur.select = cfo.option_id
    )

select
    id,

    fafsa_verification_status,
    intended_degree_type,
    eof_status,
    is_ed_ea,
    recommender1_name,
    recommender2_name,
    recommendation_1_status,
    recommendation_2_status,
    desired_pathway,
    best_guess_pathway,
    bgp_notes,
    wishlist_goal,
    wishlist_signed_off_by_counselor,
    wishlist_notes,
    activities_sheet_status,
    application_audit_status,
    application_audit_notes,
    applied_to_ed_ea_scholarships,
    css_profile_complete,
    created_fsa_id_parent,
    created_fsa_id_student,
    fafsa_opt_out,
    fafsa_status,
    intended_major,
    personal_statement_status,
    personal_statatement_essay_completion_status,
    personal_statment_essay_edit_status,
    supplemental_essay_status,
    teacher_lor_status,

    cast(student_aid_index as numeric) as student_aid_index,

    date(fafsa_submission_date) as fafsa_submission_date,
    date(
        state_aid_application_submission_date
    ) as state_aid_application_submission_date,

    regexp_extract(
        _dbt_source_relation, r'`(stg_overgrad__\w+)__custom_field_values`'
    ) as _dbt_source_model,
from
    translations pivot (
        max(`value`) for `name` in (
            'Application Audit Notes' as `application_audit_notes`,
            'BGP Notes' as `bgp_notes`,
            'FAFSA submission date' as `fafsa_submission_date`,
            'FAFSA verification status' as `fafsa_verification_status`,
            'Intended Degree Type' as `intended_degree_type`,
            'Recommender 1 Name' as `recommender1_name`,
            'Recommender 2 Name' as `recommender2_name`,
            'SAI (Student Aid Index)' as `student_aid_index`,
            'State aid application submission date'
            as `state_aid_application_submission_date`,
            'Wishlist Notes' as `wishlist_notes`,
            'Activities Sheet Status' as `activities_sheet_status`,
            'Application Audit Status' as `application_audit_status`,
            'Applied to any ED/EA Scholarships' as `applied_to_ed_ea_scholarships`,
            'Best Guess Pathway' as `best_guess_pathway`,
            'CSS Profile Complete' as `css_profile_complete`,
            'Created FSA ID (Parent)' as `created_fsa_id_parent`,
            'Created FSA ID (Student)' as `created_fsa_id_student`,
            'Desired Pathway' as `desired_pathway`,
            'EOF Status' as `eof_status`,
            'FAFSA Opt-out' as `fafsa_opt_out`,
            'FAFSA Status' as `fafsa_status`,
            'Intended Major' as `intended_major`,
            'Is ED/EA' as `is_ed_ea`,
            'Personal Statement Status' as `personal_statement_status`,
            'Personal statatement: Essay completion Status'
            as `personal_statatement_essay_completion_status`,
            'Personal statment: Essay edit status'
            as `personal_statment_essay_edit_status`,
            'Recommendation 1 Status' as `recommendation_1_status`,
            'Recommendation 2 Status' as `recommendation_2_status`,
            'Supplemental Essay Status' as `supplemental_essay_status`,
            'Teacher LOR Status' as `teacher_lor_status`,
            'Wishlist Goal' as `wishlist_goal`,
            'Wishlist Signed Off by Counselor' as `wishlist_signed_off_by_counselor`
        )
    )
