{# TODO: rewrite as multi-column unpivot #}
with
    certifications_long as (
        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'NJ' as cert_state,
            nj_cert_endorsement_1 as cert_endoresement,
            nj_cert_type_1 as cert_type,
            nj_cert_issue_date_1 as cert_issue_date,
            null as cert_expiration_date,
            nj_cert_document_link_1 as cert_document_link,
            1 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where nj_cert_endorsement_1 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'NJ' as cert_state,
            nj_cert_endorsement_2 as cert_endoresement,
            nj_cert_type_2 as cert_type,
            nj_cert_issue_date_2 as cert_issue_date,
            null as cert_expiration_date,
            nj_cert_document_link_2 as cert_document_link,
            2 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where nj_cert_endorsement_2 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'NJ' as cert_state,
            nj_cert_endorsement_3 as cert_endoresement,
            nj_cert_type_3 as cert_type,
            nj_cert_issue_date_3 as cert_issue_date,
            null as cert_expiration_date,
            nj_cert_document_link_3 as cert_document_link,
            3 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where nj_cert_endorsement_3 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'NJ' as cert_state,
            nj_cert_endorsement_4 as cert_endoresement,
            nj_cert_type_4 as cert_type,
            nj_cert_issue_date_4 as cert_issue_date,
            null as cert_expiration_date,
            nj_cert_document_link_4 as cert_document_link,
            4 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where nj_cert_endorsement_4 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'NJ' as cert_state,
            nj_cert_endorsement_5 as cert_endoresement,
            nj_cert_type_5 as cert_type,
            nj_cert_issue_date_5 as cert_issue_date,
            null as cert_expiration_date,
            nj_cert_document_link_5 as cert_document_link,
            5 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where nj_cert_endorsement_5 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'FL' as cert_state,
            fl_cert_endorsement_1 as cert_endoresement,
            null as cert_type,
            null as cert_issue_date,
            fl_cert_expiration_1 as cert_expiration_date,
            nj_cert_document_link_1 as cert_document_link,
            1 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where fl_cert_endorsement_1 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'FL' as cert_state,
            fl_cert_endorsement_2 as cert_endoresement,
            null as cert_type,
            null as cert_issue_date,
            fl_cert_expiration_2 as cert_expiration_date,
            nj_cert_document_link_2 as cert_document_link,
            2 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where fl_cert_endorsement_2 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'FL' as cert_state,
            fl_cert_endorsement_3 as cert_endoresement,
            null as cert_type,
            null as cert_issue_date,
            fl_cert_expiration_3 as cert_expiration_date,
            nj_cert_document_link_3 as cert_document_link,
            3 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where fl_cert_endorsement_3 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'FL' as cert_state,
            fl_cert_endorsement_4 as cert_endoresement,
            null as cert_type,
            null as cert_issue_date,
            fl_cert_expiration_4 as cert_expiration_date,
            nj_cert_document_link_4 as cert_document_link,
            4 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where fl_cert_endorsement_4 is not null

        union all

        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            'FL' as cert_state,
            fl_cert_endorsement_5 as cert_endoresement,
            null as cert_type,
            null as cert_issue_date,
            fl_cert_expiration_5 as cert_expiration_date,
            nj_cert_document_link_5 as cert_document_link,
            5 as cert_submission_number,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where fl_cert_endorsement_5 is not null
    )

select
    last_submitted_time as date_submitted,
    respondent_email,
    respondent_name,
    employee_number,
    cert_state,
    cert_endoresement,
    cert_type,
    cert_issue_date,
    cert_expiration_date,
    concat(
        'https://drive.google.com/file/d/', cert_document_link
    ) as cert_document_link,
    row_number() over (
        partition by employee_number
        order by last_submitted_time asc, cert_submission_number asc
    ) as cert_number,
from certifications_long
