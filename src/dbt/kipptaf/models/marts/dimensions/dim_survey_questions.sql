with
    google_forms_questions as (
        -- DISTINCT projects from response grain to question grain.
        select distinct
            fr.item_abbreviation as question_shortname,
            fr.item_title as question_text,
            fr.question_kind as question_type,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.item_abbreviation is not null and fr.item_title is not null
    ),

    scd_questions as (
        select
            qc.question_code as question_shortname,
            qc.question_text,
            'SCALE' as question_type,
        from {{ ref("stg_google_sheets__surveys__scd_question_crosswalk") }} as qc
        where qc.question_code like 'School_Survey_%'
    ),

    alchemer_questions as (
        -- DISTINCT projects from response grain to question grain.
        -- Sources Alchemer + Google Forms staff/student survey questions that
        -- feed fct_survey_responses.general_responses.
        select distinct
            sr.question_shortname,
            sr.question_title as question_text,
            cast(null as string) as question_type,
        from {{ ref("int_surveys__survey_responses") }} as sr
        where sr.question_shortname is not null
    ),

    manager_questions as (
        -- DISTINCT projects from response grain to question grain.
        select distinct
            ms.question_shortname,
            ms.question_title as question_text,
            cast(null as string) as question_type,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.question_shortname is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_questions as (
        select *,
        from google_forms_questions
        union all
        select *,
        from scd_questions
        union all
        select *,
        from alchemer_questions
        union all
        select *,
        from manager_questions
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_questions",
                partition_by="question_shortname",
                order_by="question_text asc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    question_shortname as shortname,
    question_text as `text`,
    question_type as `type`,
from deduped
