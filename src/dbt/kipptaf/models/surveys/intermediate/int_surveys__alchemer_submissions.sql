with
    gdir_alias_map as (
        select gd.primary_email, addr.address as known_address,
        from {{ ref("stg_google_directory__users") }} as gd, unnest(gd.emails) as addr
        union distinct
        select gd.primary_email, alias,
        from {{ ref("stg_google_directory__users") }} as gd, unnest(gd.aliases) as alias
        union distinct
        select gd.primary_email, gd.primary_email as known_address,
        from {{ ref("stg_google_directory__users") }} as gd
    ),

    alchemer_responses as (
        select
            sr.survey_id,
            sr.session_id,
            sr.date_started,
            sr.date_submitted,

            sr.id as response_id,

            s.title as survey_title,
            s.link_default as survey_link_default,

            date(sr.date_submitted) as date_submitted_date,
        from {{ source("alchemer", "stg_alchemer__survey_response") }} as sr
        inner join
            {{ source("alchemer", "stg_alchemer__survey") }} as s on sr.survey_id = s.id
    ),

    alchemer_identifiers as (
        select
            survey_id,
            response_id,
            respondent_mail,

            lower(
                regexp_extract(respondent_mail, r'^([^@]+)')
            ) as respondent_local_part,
        from {{ source("surveys", "int_surveys__response_identifiers") }}
    )

/*
 * Inner join to reporting terms: an Alchemer response outside every SURVEY
 * window is not a submission, as it was before the response-grain rewrite.
 */
select
    sr.survey_title,
    sr.date_started,
    sr.date_submitted,

    ri.respondent_mail as respondent_email,

    rt.name as term_name,

    cast(sr.survey_id as string) as survey_id,
    cast(sr.response_id as string) as survey_response_id,

    1 as round_rn,

    coalesce(sc.fiscal_year - 1, rt.academic_year) as academic_year,
    coalesce(regexp_extract(sc.name, r'\s(.*)'), rt.code) as term_code,

    coalesce(
        srh.employee_number, srh_alias.employee_number
    ) as respondent_employee_number,
    coalesce(srh.formatted_name, srh_alias.formatted_name) as respondent_preferred_name,
    coalesce(
        srh.sam_account_name, srh_alias.sam_account_name
    ) as respondent_samaccountname,
    coalesce(
        srh.user_principal_name, srh_alias.user_principal_name
    ) as respondent_userprincipalname,

    concat(
        sr.survey_link_default, '?snc=', sr.session_id, '&sg_navigate=start'
    ) as survey_response_link,
from alchemer_responses as sr
left join
    {{ source("alchemer", "stg_alchemer__survey_campaign") }} as sc
    on sr.survey_id = sc.survey_id
    and sr.date_started between sc.link_open_date and sc.link_close_date
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sr.survey_title = rt.name
    and sr.date_submitted_date between rt.start_date and rt.end_date
    and rt.type = 'SURVEY'
left join
    alchemer_identifiers as ri
    on sr.survey_id = ri.survey_id
    and sr.response_id = ri.response_id
left join
    {{ ref("int_people__staff_roster_history") }} as srh
    on (
        ri.respondent_local_part = srh.sam_account_name
        or ri.respondent_mail = srh.google_email
    )
    and sr.date_submitted
    between srh.effective_date_start_timestamp and srh.effective_date_end_timestamp
    and srh.primary_indicator
left join
    gdir_alias_map as gam
    on srh.employee_number is null
    and ri.respondent_mail = gam.known_address
left join
    {{ ref("int_people__staff_roster_history") }} as srh_alias
    on gam.primary_email = srh_alias.google_email
    and sr.date_submitted
    between srh_alias.effective_date_start_timestamp
    and srh_alias.effective_date_end_timestamp
    and srh_alias.primary_indicator
