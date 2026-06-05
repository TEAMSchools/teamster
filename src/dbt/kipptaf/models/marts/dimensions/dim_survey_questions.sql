with
    google_forms_questions as (
        select
            item_abbreviation as question_shortname,
            item_title as question_text,
            question_kind as question_type,
        from {{ ref("int_google_forms__form__items") }}
        where item_abbreviation is not null and item_title is not null
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
        select
            shortname as question_shortname,
            title_english as question_text,
            cast(null as string) as question_type,
        from {{ source("alchemer", "stg_alchemer__survey_question") }}
        where shortname is not null
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
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_questions",
                partition_by="question_shortname",
                order_by="question_type desc, question_text asc",
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
