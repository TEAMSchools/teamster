with
    live_gforms as (
        select
            r.form_id as survey_id,
            r.response_id as survey_response_id,
            r.respondent_email,
            r.create_timestamp as date_started,
            r.last_submitted_timestamp as date_submitted,
            r.response_link as survey_response_link,

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

            dense_rank() over (
                partition by r.respondent_email, rt.academic_year, rt.code, r.form_id
                order by r.last_submitted_timestamp desc
            ) as round_rn,
        from {{ ref("stg_google_forms__responses") }} as r
        inner join {{ ref("stg_google_forms__form") }} as f on r.form_id = f.form_id
        /*
         * One row per submission relies on same-name SURVEY windows never
         * overlapping. Nothing collapses here any more, so an overlap fails
         * the survey_submission_key unique test; the mutually_exclusive_ranges
         * test on the terms model catches it at the sheet. #5276, #3918
         */
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
            {{ ref("int_google_directory__users__addresses") }} as gda
            on srh.employee_number is null
            and r.respondent_email = gda.address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gda.primary_email = srh_alias.google_email
            and r.last_submitted_timestamp
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
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
    respondent_identifier,
    survey_submission_key,
from {{ ref("int_surveys__alchemer_submissions") }}
