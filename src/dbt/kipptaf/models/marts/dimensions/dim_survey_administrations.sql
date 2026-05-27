with
    /*
     * Submission-grain projection of int_surveys__survey_responses.
     * One row per (survey_id, survey_response_id); the order_by choice does
     * not affect correctness because projected columns don't vary across
     * questions of a submission.
     * TODO: #3918 — extract int_surveys__survey_submissions intermediate.
     */
    submissions_grain as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_surveys__survey_responses"),
                partition_by="survey_id, survey_response_id",
                order_by="survey_question_id",
            )
        }}
    ),

    /* SCD + Manager Survey admin-grain rows */
    survey_terms as (
        select
            sg.survey_id,
            sg.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where sg.academic_year is not null
    ),

    /* Historic Alchemer Manager archive admin rows */
    historic_archive_terms as (
        select
            ms.survey_id,
            ms.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and ms.campaign_academic_year = rt.academic_year
            and ms.campaign_reporting_term = rt.code
            and rt.type = 'SURVEY'
        where
            ms.survey_id = 'historic_alchemer_Manager_survey'
            and ms.campaign_academic_year is not null
    ),

    support_terms as (
        select
            ss.survey_id,
            ss.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from {{ source("surveys", "int_surveys__response_identifiers") }} as ri
        inner join
            submissions_grain as ss
            on ri.survey_id = safe_cast(ss.survey_id as int64)
            and ri.response_id = safe_cast(ss.survey_response_id as int64)
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Support Survey'
            and ss.academic_year = rt.academic_year
            and ss.term_code = rt.code
            and rt.type = 'SURVEY'
        where ss.survey_title = 'Support Survey' and ss.academic_year is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    all_administrations as (
        select *,
        from survey_terms
        union all
        select *,
        from historic_archive_terms
        union all
        select *,
        from support_terms
    ),

    /*
     * Collapse to admin grain. submissions_grain is row-grained, so several
     * submissions roll up to one admin row across all union arms.
     * TODO: #3918 — when extracted, the upstream will already be admin-grain.
     */
    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_administrations",
                partition_by=(
                    "survey_id, term_type, term_code, term_name,"
                    " term_start_date, region, school_id"
                ),
                order_by="academic_year",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "term_type",
                "term_code",
                "term_name",
                "term_start_date",
                "region",
                "school_id",
            ]
        )
    }} as survey_administration_key,

    {{ dbt_utils.generate_surrogate_key(["survey_id"]) }} as survey_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "term_type",
                "term_code",
                "term_name",
                "term_start_date",
                "region",
                "school_id",
            ]
        )
    }} as term_key,

    academic_year,

    term_end_date as response_deadline_date,

    case
        when term_end_date < current_date('{{ var("local_timezone") }}')
        then 'closed'
        when term_start_date <= current_date('{{ var("local_timezone") }}')
        then 'open'
        else 'upcoming'
    end as status,
from deduped
