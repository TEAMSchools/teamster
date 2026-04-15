with
    survey_terms as (
        -- TODO: upstream at response grain, not admin grain (#3629)
        select distinct
            sr.survey_id,
            sr.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where sr.academic_year is not null
    ),

    manager_terms as (
        -- TODO: upstream at response grain, not admin grain (#3629)
        select distinct
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
        where ms.campaign_academic_year is not null
    ),

    support_terms as (
        -- TODO: upstream at response grain, not admin grain (#3629)
        select distinct
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
            {{ ref("int_surveys__survey_responses") }} as ss
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

    all_administrations as (
        select *,
        from survey_terms
        union all
        select *,
        from manager_terms
        union all
        select *,
        from support_terms
    ),

    -- TODO: upstream response-grain models produce duplicates;
    -- distinct until definition-grain upstreams exist (#3629, #3635)
    deduped as (
        select distinct
            survey_id,
            survey_title,
            term_type,
            term_code,
            term_name,
            term_start_date,
            term_end_date,
            academic_year,
            region,
            school_id,
        from all_administrations
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

    survey_id,
    survey_title as survey_name,
    term_code,
    term_name,
    academic_year,

    case
        when term_end_date < current_date('{{ var("local_timezone") }}')
        then 'closed'
        when term_start_date <= current_date('{{ var("local_timezone") }}')
        then 'open'
        else 'upcoming'
    end as administration_status,

    term_end_date as response_deadline,
from deduped
