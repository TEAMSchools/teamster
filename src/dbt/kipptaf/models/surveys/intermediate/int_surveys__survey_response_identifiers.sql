{{ config(enabled=False) }}

{%- set identifier_shortnames = [
    "respondent_df_employee_number",
    "respondent_userprincipalname",
    "respondent_adp_associate_id",
    "subject_df_employee_number",
    "employee_number",
    "email",
    "employee_preferred_name",
    "salesforce_id",
    "is_manager",
] -%}

with
    identifier_responses as (
        select
            sq.survey_id,
            sq.shortname,

            srd.survey_response_id,
            srd.string_value as answer,

            sr.status as response_status,
            sr.contact_id as response_contact_id,
            sr.date_started as response_date_started,
            sr.date_submitted as response_date_submitted,
            sr.response_time,

            sc.fiscal_year as campaign_fiscal_year,
            sc.name as campaign_name,
            regexp_extract(sc.name, r'\d+s+(\w+)') as campaign_reporting_term,
        from {{ ref("stg_alchemer__survey_question") }} as sq
        inner join
            {{ ref("stg_alchemer__survey_response__survey_data") }} as srd
            on sq.survey_id = srd.survey_id
            and sq.id = srd.question_id
            and srd.string_value is not null
        inner join
            {{ ref("stg_alchemer__survey_response") }} as sr
            on srd.survey_id = sr.survey_id
            and srd.survey_response_id = sr.id
            and sr.status = 'Complete'
        left join
            {{ ref("stg_alchemer__survey_campaign") }} as sc
            on sr.survey_id = sc.survey_id
            and sr.date_started between sc.link_open_date and sc.link_close_date
            and sc.status != 'Deleted'
        where sq.shortname in unnest({{ identifier_shortnames }})
    ),

    identifier_responses_pivot as (
        select
            survey_id,
            survey_response_id,
            response_status,
            response_contact_id,
            response_date_started,
            response_date_submitted,
            response_time,
            campaign_fiscal_year,
            campaign_name,
            campaign_reporting_term,
            salesforce_id as respondent_salesforce_id,
            safe_cast(respondent_adp_worker_id as string) as respondent_associate_id,
            safe_cast(
                lower(ifnull(respondent_userprincipalname, email)) as string
            ) as respondent_user_principal_name,

            if
            (
                safe_cast(respondent_df_employee_number as int) is not null,
                safe_cast(respondent_df_employee_number as int),
                safe_cast(
                    regexp_extract(
                        ifnull(respondent_df_employee_number, employee_preferred_name),
                        r'\[(\d+)\]'
                    ) as int
                )
            ) as respondent_employee_number,

            if
            (
                safe_cast(subject_df_employee_number as int) is not null,
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
            end as is_manager,
        from
            identifier_responses pivot (
                max(answer) for shortname
                in ('{{ identifier_shortnames | join("', '") }}')
            )
    ),

    identifier_responses_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="identifier_responses_pivot",
                partition_by="survey_id, respondent_employee_number, subject_employee_number, campaign_fiscal_year, campaign_name",
                order_by="response_date_submitted desc",
            )
        }}
    ),

    response_clean as (
        select
            rp.survey_response_id,
            rp.survey_id,
            rp.date_started,
            rp.subject_preferred_name,
            rp.is_manager,
            rp.salesforce_id,
            rp.respondent_user_principal_name as nonstaff_email,

            ab.subject_preferred_name_duplicate,

            coalesce(
                rp.subject_employee_number, ab.subject_employee_number
            ) as subject_employee_number,

            coalesce(
                rp.respondent_employee_number,
                upn.employee_number,
                adp.employee_number,
                mail.employee_number,
                ab.employee_number
            ) as respondent_employee_number,
        from identifier_responses_deduplicate as rp
        left join
            {{ ref("base_people__staff_roster") }} as upn
            on rp.respondent_user_principal_name = upn.user_principal_name
        left join
            {{ ref("base_people__staff_roster") }} as adp
            on rp.respondent_associate_id = adp.adp_worker_id_legacy
        left join
            {{ ref("base_people__staff_roster") }} as mail
            on rp.respondent_user_principal_name = mail.mail
        left join
            {{ source("alchemer", "src_alchemer__response_id_override") }} as ab
            on rp.survey_id = ab.survey_id
            and rp.survey_response_id = ab.survey_response_id
    )

select
    rc.survey_response_id,
    rc.survey_id,
    rc.response_status,
    rc.response_contact_id,
    rc.response_date_started,
    rc.response_date_submitted,
    rc.response_time,
    rc.campaign_name,
    rc.campaign_fiscal_year,
    rc.campaign_reporting_term,
    rc.subject_employee_number,
    rc.respondent_employee_number,
    rc.respondent_salesforce_id,

    resp.preferred_name_lastfirst as respondent_preferred_name,
    resp.worker_id as respondent_adp_worker_id,
    resp.mail as respondent_mail,
    resp.sam_account_name as respondent_sam_account_name,

    reh.business_unit_home_name as respondent_legal_entity_name,
    reh.home_work_location_name as respondent_primary_site,
    reh.department_home_name as respondent_department_name,
    reh.job_title as respondent_primary_job,
    reh.assignment_status as respondent_assignment_status,
    reh.report_to_employee_number as respondent_manager_df_employee_number,

    rsch.powerschool_school_id as respondent_primary_site_schoolid,
    rsch.grade_band as respondent_primary_site_grade_band,

    rmgr.preferred_name_lastfirst as respondent_manager_name,
    rmgr.mail as respondent_manager_mail,
    rmgr.user_principal_name as respondent_manager_user_principal_name,
    rmgr.sam_account_name as respondent_manager_sam_account_name,

    subj.preferred_name_lastfirst as subject_preferred_name,
    subj.worker_id as subject_adp_worker_id,
    subj.user_principal_name as subject_user_principal_name,
    subj.mail as subject_mail,
    subj.sam_account_name as subject_sam_account_name,

    seh.business_unit_home_name as subject_legal_entity_name,
    seh.home_work_location_name as subject_primary_site,
    seh.department_home_name as subject_department_name,
    seh.job_title as subject_primary_job,
    seh.report_to_employee_number as subject_manager_df_employee_number,

    ssch.powerschool_school_id as subject_powerschool_school_id,
    ssch.grade_band as subject_primary_site_grade_band,

    smgr.preferred_name_lastfirst as subject_manager_name,
    smgr.mail as subject_manager_mail,
    smgr.user_principal_name as subject_manager_user_principal_name,
    smgr.sam_account_name as subject_manager_sam_account_name,

    ifnull(
        rc.is_manager,
        if(rc.respondent_employee_number = seh.report_to_employee_number, true, false)
    ) as is_manager,

    ifnull(
        resp.user_principal_name, rc.nonstaff_email
    ) as respondent_user_principal_name,
from identifier_responses_deduplicate as rc
left join
    {{ ref("base_people__staff_roster") }} as resp
    on rc.respondent_employee_number = resp.employee_number
left join
    people.employment_history_static as reh
    on resp.position_id = reh.position_id
    and sc.link_close_date between reh.effective_start_date and reh.effective_end_date
left join
    {{ ref("base_people__staff_roster") }} as rmgr
    on reh.report_to_employee_number = rmgr.employee_number
left join
    people.school_crosswalk as rsch on reh.home_work_location_name = rsch.site_name
left join
    {{ ref("base_people__staff_roster") }} as subj
    on rc.subject_employee_number = subj.employee_number
left join
    people.employment_history_static as seh
    on subj.position_id = seh.position_id
    and sc.link_close_date between seh.effective_start_date and seh.effective_end_date
left join
    {{ ref("base_people__staff_roster") }} as smgr
    on seh.report_to_employee_number = smgr.employee_number
left join
    people.school_crosswalk as ssch on seh.home_work_location_name = ssch.site_name
