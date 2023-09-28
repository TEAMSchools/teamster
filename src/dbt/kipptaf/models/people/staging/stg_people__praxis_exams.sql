with
    praxis_submissions as (
        select
            last_submitted_time,
            respondent_email,
            respondent_name,
            employee_number,
            cert_status,
            cert_steps_taken,
            cert_barriers,
            updates_open_ended,
            praxis_document_link as praxis_document_link,
        from {{ ref("int_surveys__staff_information_survey_pivot") }}
        where praxis_document_link is not null
    )
select
    last_submitted_time as date_submitted,
    respondent_email,
    respondent_name,
    employee_number,
    cert_status,
    cert_steps_taken,
    cert_barriers,
    updates_open_ended,
    concat(
        'https://drive.google.com/file/d/', praxis_document_link
    ) as cert_document_link,
    row_number() over (
        partition by employee_number order by last_submitted_time desc
    ) as rn_praxis_doc
from praxis_submissions
