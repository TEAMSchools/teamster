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

    enriched as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.question_id as survey_question_id,
            fr.text_value as answer,
            fr.item_title as question_title,
            fr.item_abbreviation as question_shortname,
            fr.respondent_email,

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

            safe_cast(fr.text_value as numeric) as answer_value,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

            concat(
                'https://docs.google.com/forms/d/',
                fr.form_id,
                '/edit#response=',
                fr.response_id
            ) as survey_response_link,

            if(safe_cast(fr.text_value as int) is null, 1, 0) as is_open_ended,

            dense_rank() over (
                partition by fr.respondent_email, rt.academic_year, rt.code, fr.form_id
                order by fr.last_submitted_time desc
            ) as round_rn,
        from {{ ref("int_google_forms__form_responses") }} as fr
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on fr.info_title = rt.name
            and date(fr.last_submitted_time) between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                lower(regexp_extract(fr.respondent_email, r'^([^@]+)'))
                = srh.sam_account_name
                or fr.respondent_email = srh.google_email
            )
            and timestamp(fr.last_submitted_time)
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join
            gdir_alias_map as gam
            on srh.employee_number is null
            and fr.respondent_email = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and timestamp(fr.last_submitted_time)
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator

        union all

        select
            safe_cast(sr.survey_id as string) as survey_id,

            sr.survey_title,

            safe_cast(sr.response_id as string) as survey_response_id,

            safe_cast(sr.question_id as string) as survey_question_id,

            sr.response_value as answer,
            sr.question_title_english as question_title,
            sr.question_short_name as question_shortname,

            ri.respondent_mail as respondent_email,

            coalesce(sr.campaign_fiscal_year - 1, rt.academic_year) as academic_year,

            coalesce(regexp_extract(sr.campaign_name, r'\s(.*)'), rt.code) as term_code,

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

            safe_cast(sr.response_value as numeric) as answer_value,

            sr.response_date_started as date_started,
            sr.response_date_submitted as date_submitted,

            concat(
                sr.survey_link_default,
                '?snc=',
                sr.response_session_id,
                '&sg_navigate=start'
            ) as survey_response_link,

            if(safe_cast(sr.response_value as int) is null, 1, 0) as is_open_ended,

            1 as round_rn,
        from {{ source("alchemer", "base_alchemer__survey_results") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.name
            and sr.response_date_submitted_date between rt.start_date and rt.end_date
        left join
            {{ source("surveys", "int_surveys__response_identifiers") }} as ri
            on sr.survey_id = ri.survey_id
            and sr.response_id = ri.response_id
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                lower(regexp_extract(ri.respondent_mail, r'^([^@]+)'))
                = srh.sam_account_name
                or ri.respondent_mail = srh.google_email
            )
            and sr.response_date_submitted
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
            and sr.response_date_submitted
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
    )

select
    e.*,
    coalesce(
        cast(e.respondent_employee_number as string), e.respondent_email
    ) as respondent_identifier,
from enriched as e
