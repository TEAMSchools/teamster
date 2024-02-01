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
                    '{{ var("alchemer_survey_identifier_short_names") | join("', '") }}'  -- noqa: LT05
                )
            )
    ),

    response_clean as (
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
            {{ source("alchemer", "src_alchemer__response_id_override") }} as ab
            on rp.survey_id = ab.survey_id
            and rp.response_id = ab.survey_response_id
    )

select
    rc.survey_id,
    rc.response_id,
    rc.response_contact_id,
    rc.response_date_started,
    rc.response_date_submitted,
    rc.response_time,
    rc.campaign_name,
    rc.campaign_fiscal_year,
    rc.campaign_reporting_term,
    rc.campaign_link_close_date,
    rc.subject_employee_number,
    rc.respondent_employee_number,
    rc.respondent_salesforce_id,
    rc.rn_survey_response_campaign_desc,

    resp.preferred_name_lastfirst as respondent_preferred_name_lastfirst,
    resp.worker_id as respondent_adp_worker_id,
    resp.mail as respondent_mail,
    resp.sam_account_name as respondent_sam_account_name,

    reh.business_unit_home_name as respondent_business_unit,
    reh.home_work_location_name as respondent_work_location,
    reh.department_home_name as respondent_department,
    reh.job_title as respondent_job_title,
    reh.assignment_status as respondent_assignment_status,
    reh.report_to_employee_number as respondent_report_to_employee_number,
    reh.home_work_location_powerschool_school_id
    as respondent_work_location_powerschool_school_id,
    reh.home_work_location_grade_band as respondent_work_location_grade_band,
    reh.report_to_preferred_name_lastfirst
    as respondent_report_to_preferred_name_lastfirst,
    reh.report_to_mail as respondent_report_to_mail,
    reh.report_to_user_principal_name as respondent_report_to_user_principal_name,
    reh.report_to_sam_account_name as respondent_report_to_sam_account_name,

    subj.preferred_name_lastfirst as subject_preferred_name_lastfirst,
    subj.worker_id as subject_adp_worker_id,
    subj.user_principal_name as subject_user_principal_name,
    subj.mail as subject_mail,
    subj.sam_account_name as subject_sam_account_name,

    seh.business_unit_home_name as subject_business_unit,
    seh.home_work_location_name as subject_work_location,
    seh.department_home_name as subject_department,
    seh.job_title as subject_job_title,
    seh.report_to_employee_number as subject_report_to_employee_number,
    seh.home_work_location_powerschool_school_id
    as subject_work_location_powerschool_school_id,
    seh.home_work_location_grade_band as subject_work_location_grade_band,
    seh.report_to_preferred_name_lastfirst
    as subject_report_to_preferred_name_lastfirst,
    seh.report_to_mail as subject_report_to_mail,
    seh.report_to_user_principal_name as subject_report_to_user_principal_name,
    seh.report_to_sam_account_name as subject_report_to_sam_account_name,

    coalesce(
        rc.respondent_is_manager,
        if(rc.respondent_employee_number = seh.report_to_employee_number, true, false)
    ) as is_manager,

    coalesce(
        resp.user_principal_name, rc.respondent_user_principal_name
    ) as respondent_user_principal_name,
from response_clean as rc
left join
    {{ ref("base_people__staff_roster") }} as resp
    on rc.respondent_employee_number = resp.employee_number
left join
    {{ ref("base_people__staff_roster_history") }} as reh
    on resp.worker_id = reh.worker_id
    and rc.campaign_link_close_date
    between reh.work_assignment__fivetran_start and reh.work_assignment__fivetran_end
    and reh.primary_indicator
left join
    {{ ref("base_people__staff_roster") }} as subj
    on rc.subject_employee_number = subj.employee_number
left join
    {{ ref("base_people__staff_roster_history") }} as seh
    on subj.worker_id = seh.worker_id
    and rc.campaign_link_close_date
    between seh.work_assignment__fivetran_start and seh.work_assignment__fivetran_end
    and seh.primary_indicator
