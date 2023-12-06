with
    sub as (
        select
            sr.survey_id,
            sr.survey_title,
            sr.response_id,
            sr.response_string_value,
            sr.question_id,

            ri.respondent_employee_number,
            ri.respondent_user_principal_name,
            ri.respondent_business_unit,
            ri.respondent_preferred_name_lastfirst,
            ri.respondent_work_location,
            ri.respondent_job_title,

            concat(
                sr.survey_link_default,
                '?snc=',
                sr.response_session_id,
                '&sg_navigate=start'
            ) as edit_link,
        from {{ ref("base_alchemer__survey_results") }} as sr
        left join
            {{ ref("int_surveys__response_identifiers") }} as ri
            on sr.survey_id = ri.survey_id
            and sr.response_id = ri.response_id
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
    respondent_user_principal_name as respondent_userprincipalname,
    respondent_business_unit as respondent_legal_entity_name,
    respondent_preferred_name_lastfirst as respondent_preferred_name,
    respondent_work_location as respondent_primary_site,
    respondent_job_title as respondent_primary_job,

    /* pivot cols */
    teammate_signature,
    approver_signature,
    approver_email,
from
    sub pivot (
        max(response_string_value) for question_id
        in (20 as teammate_signature, 94 as approver_signature, 72 as approver_email)
    )
