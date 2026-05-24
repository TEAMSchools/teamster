with
    google_forms_pairs as (
        select
            form_id as survey_id,
            item_abbreviation as question_shortname,
            question_required as is_required,
        from {{ ref("int_google_forms__form__items") }}
        where form_id is not null and item_abbreviation is not null
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
        select
            safe_cast(survey_id as string) as survey_id,
            shortname as question_shortname,
            cast(null as bool) as is_required,
        from {{ source("alchemer", "stg_alchemer__survey_question") }}
        where shortname is not null
    ),

    manager_pairs as (
        -- Synthesizes pairs for the historic Manager Survey archive, whose
        -- original Alchemer survey_ids were not preserved. Live Manager
        -- Survey pairs flow through google_forms_pairs above. Sourced from
        -- the gforms items extension (not items) because the extension
        -- carries historic shortnames (e.g. Q_5) that the live form
        -- removed.
        select distinct
            'historic_alchemer_Manager_survey' as survey_id,
            abbreviation as question_shortname,
            cast(null as bool) as is_required,
        from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
        where
            form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
            and abbreviation is not null
            and abbreviation
            not in ('respondent_employee_number', 'subject_employee_number')
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
        -- order_by prefers the concrete is_required boolean from
        -- google_forms_pairs / scd_powerschool_pairs over the
        -- `cast(null as bool)` placeholder from alchemer_pairs / manager_pairs
        -- when the same (survey_id, question_shortname) appears in multiple
        -- CTEs.
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

    is_required,
from deduped
