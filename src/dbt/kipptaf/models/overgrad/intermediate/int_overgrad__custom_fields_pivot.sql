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
    recommender1_name,
    recommender2_name,
    bgp_notes,
    wishlist_notes,
    application_audit_notes,

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
            'Wishlist Notes' as `wishlist_notes`
        )
    )
