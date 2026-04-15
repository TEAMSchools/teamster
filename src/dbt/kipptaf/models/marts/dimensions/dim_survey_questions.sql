with
    google_forms_questions as (
        -- TODO: upstream at response grain, no definition model (#3635)
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

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_questions as (
        select *,
        from google_forms_questions
        union all
        select *,
        from scd_questions
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

    question_shortname,
    question_text,
    question_type,
from deduped
