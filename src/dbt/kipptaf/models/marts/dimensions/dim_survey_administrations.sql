with
    /*
     * The historic Alchemer archive is excluded here and handled by
     * historic_archive_terms below, which matches term_code as well. This leg
     * deliberately does not, so a survey administered in several terms of one
     * year yields an administration per term rather than only the terms that
     * happen to carry a submission. 35 of the 57 administrations have no
     * submissions, and bridge_survey_expectations needs them to produce the
     * missed side of expected-versus-taken.
     */
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
        from {{ ref("int_surveys__survey_submissions") }} as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where
            sg.academic_year is not null
            and sg.survey_id != 'historic_alchemer_Manager_survey'
    ),

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
        from {{ ref("int_surveys__survey_submissions") }} as ms
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and ms.academic_year = rt.academic_year
            and ms.term_code = rt.code
            and rt.type = 'SURVEY'
        where ms.survey_id = 'historic_alchemer_Manager_survey'
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
            {{ ref("int_surveys__survey_submissions") }} as ss
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
     * Collapse to admin grain. The upstream is submission-grained, so many
     * submissions roll up to one administration across all 3 arms. This is a
     * grain projection, not a dedupe of survey responses — that one moved to
     * int_surveys__survey_submissions.
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
