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

    /*
     * The terms join keys on the UTC date, which is what date() of the raw
     * string resolved to before this model read staging directly. The local
     * date differs on submissions near midnight; switching is a behavior
     * change for another issue.
     */
    gforms_responses as (
        select
            form_id,
            response_id,
            respondent_email,
            create_timestamp,
            last_submitted_timestamp,

            date(last_submitted_timestamp) as last_submitted_date,

            lower(
                regexp_extract(respondent_email, r'^([^@]+)')
            ) as respondent_local_part,
        from {{ ref("stg_google_forms__responses") }}
    ),

    live_gforms as (
        select
            r.form_id as survey_id,
            r.response_id as survey_response_id,
            r.respondent_email,
            r.create_timestamp as date_started,
            r.last_submitted_timestamp as date_submitted,

            f.info_title as survey_title,

            rt.academic_year,
            rt.code as term_code,
            rt.name as term_name,

            coalesce(
                srh.employee_number, srh_alias.employee_number
            ) as respondent_employee_number,
            coalesce(
                srh.formatted_name, srh_alias.formatted_name
            ) as respondent_preferred_name,
            coalesce(
                srh.sam_account_name, srh_alias.sam_account_name
            ) as respondent_samaccountname,
            coalesce(
                srh.user_principal_name, srh_alias.user_principal_name
            ) as respondent_userprincipalname,

            concat(
                'https://docs.google.com/forms/d/',
                r.form_id,
                '/edit#response=',
                r.response_id
            ) as survey_response_link,

            dense_rank() over (
                partition by r.respondent_email, rt.academic_year, rt.code, r.form_id
                order by r.last_submitted_timestamp desc
            ) as round_rn,
        from gforms_responses as r
        inner join {{ ref("stg_google_forms__form") }} as f on r.form_id = f.form_id
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on f.info_title = rt.name
            and r.last_submitted_date between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                r.respondent_local_part = srh.sam_account_name
                or r.respondent_email = srh.google_email
            )
            and r.last_submitted_timestamp
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join
            gdir_alias_map as gam
            on srh.employee_number is null
            and r.respondent_email = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and r.last_submitted_timestamp
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
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
    ),

    /*
     * Inner join to reporting terms: an Alchemer response outside every
     * SURVEY window is not a submission, as before this model read the
     * response-grain tables directly.
     */
    live_alchemer as (
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
            coalesce(
                srh.formatted_name, srh_alias.formatted_name
            ) as respondent_preferred_name,
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
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
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
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    archive_source as (
        select
            survey_id,
            survey_title,
            respondent_email,
            date_submitted,
            campaign_academic_year,
            campaign_reporting_term,
            respondent_df_employee_number,
            effective_survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }}
        where
            survey_id = 'historic_alchemer_Manager_survey'
            and campaign_academic_year is not null
    ),

    /*
     * int_surveys__manager_survey_details is question-grain, so the archive
     * arrives at 18 rows per submission. Every column selected is constant
     * within the partition.
     */
    archive_submissions as (
        {{
            dbt_utils.deduplicate(
                relation="archive_source",
                partition_by="survey_id, effective_survey_response_id",
                order_by="respondent_df_employee_number",
            )
        }}
    ),

    all_submissions as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            academic_year,
            term_code,
            term_name,
            survey_response_link,
            round_rn,
        from live_gforms

        union all

        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            academic_year,
            term_code,
            term_name,
            survey_response_link,
            round_rn,
        from live_alchemer

        union all

        select
            survey_id,

            effective_survey_response_id as survey_response_id,

            survey_title,
            respondent_email,

            respondent_df_employee_number as respondent_employee_number,

            cast(null as string) as respondent_preferred_name,
            cast(null as string) as respondent_samaccountname,
            cast(null as string) as respondent_userprincipalname,
            cast(null as timestamp) as date_started,

            date_submitted,

            campaign_academic_year as academic_year,
            campaign_reporting_term as term_code,

            cast(null as string) as term_name,
            cast(null as string) as survey_response_link,
            cast(null as int) as round_rn,
        from archive_submissions
    )

select
    survey_id,
    survey_response_id,
    survey_title,
    respondent_email,
    respondent_employee_number,
    respondent_preferred_name,
    respondent_samaccountname,
    respondent_userprincipalname,
    date_started,
    date_submitted,
    academic_year,
    term_code,
    term_name,
    survey_response_link,
    round_rn,

    coalesce(
        cast(respondent_employee_number as string), respondent_email
    ) as respondent_identifier,

    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,
from all_submissions
