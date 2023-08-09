with certifications_long AS (
    SELECT last_submitted_time,
          employee_number,
          respondent_email,
          respondent_name,
          'NJ' AS cert_state,
          nj_cert_endorsement_1 AS cert_endoresement,
          nj_cert_type_1 AS cert_type,
          nj_cert_issue_date_1 AS cert_issue_date,
          NULL AS cert_expiration_date,
          nj_cert_document_link_1 AS cert_document,
          1 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE nj_cert_endorsement_1 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "NJ" AS cert_state,
          nj_cert_endorsement_2 AS cert_endoresement,
          nj_cert_type_2 AS cert_type,
          nj_cert_issue_date_2 AS cert_issue_date,
          NULL AS cert_expiration_date,
          nj_cert_document_link_2 AS cert_document,
          2 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE nj_cert_endorsement_2 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "NJ" AS cert_state,
          nj_cert_endorsement_3 AS cert_endoresement,
          nj_cert_type_3 AS cert_type,
          nj_cert_issue_date_3 AS cert_issue_date,
          NULL AS cert_expiration_date,
          nj_cert_document_link_3 AS cert_document,
          3 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE nj_cert_endorsement_3 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "NJ" AS cert_state,
          nj_cert_endorsement_4 AS cert_endoresement,
          nj_cert_type_4 AS cert_type,
          nj_cert_issue_date_4 AS cert_issue_date,
          NULL AS cert_expiration_date,
          nj_cert_document_link_4 AS cert_document,
          4 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE nj_cert_endorsement_4 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "NJ" AS cert_state,
          nj_cert_endorsement_5 AS cert_endoresement,
          nj_cert_type_5 AS cert_type,
          nj_cert_issue_date_5 AS cert_issue_date,
          NULL AS cert_expiration_date,
          nj_cert_document_link_5 AS cert_document,
          5 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE nj_cert_endorsement_5 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "FL" AS cert_state,
          fl_cert_endorsement_1 AS cert_endoresement,
          NULL AS cert_type,
          NULL AS cert_issue_date,
          fl_cert_expiration_1 AS cert_expiration_date,
          nj_cert_document_link_1 AS cert_document,
          1 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE fl_cert_endorsement_1 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "FL" AS cert_state,
          fl_cert_endorsement_2 AS cert_endoresement,
          NULL AS cert_type,
          NULL AS cert_issue_date,
          fl_cert_expiration_2 AS cert_expiration_date,
          nj_cert_document_link_2 AS cert_document,
          2 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE fl_cert_endorsement_2 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "FL" AS cert_state,
          fl_cert_endorsement_3 AS cert_endoresement,
          NULL AS cert_type,
          NULL AS cert_issue_date,
          fl_cert_expiration_3 AS cert_expiration_date,
          nj_cert_document_link_3 AS cert_document,
          3 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE fl_cert_endorsement_3 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "FL" AS cert_state,
          fl_cert_endorsement_4 AS cert_endoresement,
          NULL AS cert_type,
          NULL AS cert_issue_date,
          fl_cert_expiration_4 AS cert_expiration_date,
          nj_cert_document_link_4 AS cert_document,
          4 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE fl_cert_endorsement_4 IS NOT NULL

    UNION DISTINCT

    SELECT last_submitted_time,
          respondent_email,
          respondent_name,
          employee_number,
          "FL" AS cert_state,
          fl_cert_endorsement_5 AS cert_endoresement,
          NULL AS cert_type,
          NULL AS cert_issue_date,
          fl_cert_expiration_5 AS cert_expiration_date,
          nj_cert_document_link_5 AS cert_document,
          5 AS cert_submission_number
    FROM {{ ref('int_surveys__staff_information_survey_pivot') }}
    WHERE fl_cert_endorsement_5 IS NOT NULL
    )
 
SELECT last_submitted_time AS date_submitted,
       respondent_email,
       respondent_name,
       employee_number,
       cert_state,
       cert_endoresement,
       cert_type,
       cert_issue_date,
       cert_expiration_date,
       concat('https://drive.google.com/file/d/',cert_document) as cert_document_link,
       ROW_NUMBER() OVER(PARTITION BY employee_number ORDER BY last_submitted_time ASC, cert_submission_number ASC) AS cert_number
from certifications_long
       