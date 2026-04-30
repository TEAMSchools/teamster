with
    google_forms_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
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

    alchemer_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
        -- Covers Alchemer + Google Forms staff/student survey questions feeding
        -- fct_survey_responses.general_responses.
        select distinct
            sr.survey_id, sr.question_shortname, cast(null as bool) as is_required,
        from {{ ref("int_surveys__survey_responses") }} as sr
        where sr.survey_id is not null and sr.question_shortname is not null
    ),

    manager_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
        select distinct
            ms.survey_id, ms.question_shortname, cast(null as bool) as is_required,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.survey_id is not null and ms.question_shortname is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_pairs as (
        select *,
        from google_forms_pairs
        union all
        select *,
        from scd_powerschool_pairs
        union all
        select *,
        from alchemer_pairs
        union all
        select *,
        from manager_pairs
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_pairs",
                partition_by="survey_id, question_shortname",
                order_by="is_required desc nulls last",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "question_shortname"]) }}
    as survey_question_bridge_key,

    {{ dbt_utils.generate_surrogate_key(["survey_id"]) }} as survey_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    question_shortname as shortname,
    is_required,
from deduped
