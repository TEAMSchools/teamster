with
    google_forms_pairs as (
        -- TODO: upstream at response grain, no survey-question-pair definition model
        select distinct
            fr.form_id as survey_id,
            fr.item_abbreviation as question_shortname,
            fr.question_required as is_required,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.form_id is not null and fr.item_abbreviation is not null
    ),

    scd_powerschool_pairs as (
        select
            'PowerSchool' as survey_id,
            qc.question_code as question_shortname,
            true as is_required,
        from {{ ref("stg_google_sheets__surveys__scd_question_crosswalk") }} as qc
        where qc.question_code like 'School_Survey_%'
    ),

    all_pairs as (
        select *
        from google_forms_pairs
        union all
        select *
        from scd_powerschool_pairs
    )

select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "question_shortname"]) }}
    as survey_question_bridge_key,

    {{ dbt_utils.generate_surrogate_key(["survey_id"]) }} as survey_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    survey_id,
    question_shortname,
    is_required,
from all_pairs
