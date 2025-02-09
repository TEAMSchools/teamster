{{- config(enabled=false) -}}

with
    identifier_responses as (
        select
            survey_id,
            question_short_name,
            response_id,
            response_string_value,
            response_contact_id,
            response_date_started,
            response_date_submitted,
            response_time,
            campaign_fiscal_year,
            campaign_name,
            campaign_link_close_date,
            regexp_extract(campaign_name, r'\d+s+(\w+)') as campaign_reporting_term,
        from {{ ref("base_alchemer__survey_results") }}
        where
            response_status = 'Complete'
            and is_identifier_question
            and response_string_value is not null
    ),

    identifier_responses_pivot as (
        select
            survey_id,
            response_id,
            response_contact_id,
            response_date_started,
            response_date_submitted,
            response_time,
            campaign_fiscal_year,
            campaign_name,
            campaign_reporting_term,
            campaign_link_close_date,

            {# pivot cols #}
            salesforce_id as respondent_salesforce_id,
            safe_cast(
                respondent_adp_associate_id as string
            ) as respondent_adp_worker_id,
            safe_cast(
                lower(coalesce(respondent_userprincipalname, email)) as string
            ) as respondent_user_principal_name,

            coalesce(
                safe_cast(respondent_employee_number as int),
                safe_cast(respondent_df_employee_number as int),
                safe_cast(
                    regexp_extract(
                        coalesce(
                            respondent_df_employee_number, employee_preferred_name
                        ),
                        r'\[(\d+)\]'
                    ) as int
                )
            ) as respondent_employee_number,

            coalesce(
                safe_cast(subject_df_employee_number as int),
                safe_cast(
                    regexp_extract(
                        coalesce(subject_df_employee_number, employee_preferred_name),
                        r'\[(\d+)\]'
                    ) as int
                )
            ) as subject_employee_number,

            if(
                regexp_extract(subject_df_employee_number, r'\[(\d+)\]') is null,
                subject_df_employee_number,
                null
            ) as subject_preferred_name,

            case
                is_manager
                when 'Yes - I am their manager.'
                then true
                when 'No - I am their peer.'
                then false
                else safe_cast(safe_cast(is_manager as int) as boolean)
            end as respondent_is_manager,
        from
            identifier_responses pivot (
                max(response_string_value) for question_short_name in (
                    -- trunk-ignore(sqlfluff/LT05)
                    '{{ var("alchemer_survey_identifier_short_names") | join("', '") }}'
                )
            )
    )

select
    rp.survey_id,
    rp.response_id,
    rp.response_contact_id,
    rp.response_date_started,
    rp.response_date_submitted,
    rp.response_time,
    rp.campaign_fiscal_year,
    rp.campaign_name,
    rp.campaign_reporting_term,
    rp.campaign_link_close_date,
    rp.respondent_salesforce_id,
    rp.respondent_is_manager,
    rp.respondent_user_principal_name,

    coalesce(
        rp.subject_employee_number, ab.subject_employee_number
    ) as subject_employee_number,

    coalesce(
        rp.respondent_employee_number, ab.respondent_employee_number
    ) as respondent_employee_number,

    row_number() over (
        partition by
            rp.survey_id,
            rp.respondent_employee_number,
            rp.subject_employee_number,
            rp.campaign_fiscal_year,
            rp.campaign_name
        order by rp.response_date_submitted desc
    ) as rn_survey_response_campaign_desc,
from identifier_responses_pivot as rp
left join
    {{ ref("stg_alchemer__response_id_override") }} as ab
    on rp.survey_id = ab.survey_id
    and rp.response_id = ab.survey_response_id
