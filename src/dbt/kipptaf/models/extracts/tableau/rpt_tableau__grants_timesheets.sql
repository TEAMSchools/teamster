with
    sub as (
        -- trunk-ignore(sqlfluff/ST06): contract column order is mandated
        select
            sr.survey_id,
            sr.survey_title,
            sr.response_id,
            sr.response_string_value,
            sr.question_id,

            ri.respondent_employee_number,
            ri.respondent_preferred_name_lastfirst,

            lc.location_clean_name,
            lc.campus_name,

            case
                sr2.home_business_unit_name
                when 'TEAM'
                then 'TEAM Academy Charter School'
                when 'KCNA'
                then 'KIPP Cooper Norcross Academy'
                when 'MIA'
                then 'KIPP Miami'
                when 'KNJ'
                then 'KIPP TEAM and Family Schools Inc.'
                else sr2.home_business_unit_name
            end as home_business_unit_name,
            sr2.home_department_name,
            sr2.job_function,
            sr2.job_title,

            sr2.mail,
            sr2.user_principal_name,
            sr2.sam_account_name,

            sr2.reports_to_mail,
            sr2.reports_to_sam_account_name,

            concat(
                sr.survey_link_default,
                '?snc=',
                sr.response_session_id,
                '&sg_navigate=start'
            ) as edit_link,
        from {{ source("alchemer", "base_alchemer__survey_results") }} as sr
        left join
            {{ source("surveys", "int_surveys__response_identifiers") }} as ri
            on sr.survey_id = ri.survey_id
            and sr.response_id = ri.response_id
        left join
            {{ ref("int_people__staff_roster") }} as sr2
            on ri.respondent_employee_number = sr2.employee_number
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sr2.home_work_location_name = lc.location_name
        where
            sr.survey_title = 'Federally Funded Staff Semi-Annual Certification'
            and sr.question_id in (20, 94, 72)
    )

select
    survey_id,
    survey_title,
    response_id as survey_response_id,
    edit_link,
    respondent_employee_number as respondent_df_employee_number,
    respondent_preferred_name_lastfirst as respondent_preferred_name,

    location_clean_name,
    campus_name,
    home_business_unit_name,
    home_department_name,
    job_function,
    job_title,
    mail,
    user_principal_name,
    sam_account_name,
    reports_to_mail,
    reports_to_sam_account_name,

    /* pivot cols */
    approver_email,
    parse_date('%m/%d/%Y', teammate_signature) as teammate_signature,
    parse_date('%m/%d/%Y', approver_signature) as approver_signature,
from
    sub pivot (
        max(response_string_value) for question_id
        in (20 as teammate_signature, 94 as approver_signature, 72 as approver_email)
    )
