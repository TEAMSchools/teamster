select
    survey_id,
    survey_title,
    survey_response_id,
    respondent_email,
    campaign_academic_year,
    campaign_name,
    campaign_reporting_term,
    respondent_employee_number,
    subject_employee_number,
    approval_level,
    date_started,
    date_submitted,
    rn_level_approval,
    rn_approval,
    respondent_preferred_name,
    respondent_samaccountname,
    respondent_userprincipalname,
    subject_preferred_name,
    subject_samaccountname,
    subject_userprincipalname,
    dept_and_job,
    final_confirmation,
    next_year_seat,
    renewal_decision,
    salary,
    salary_confirmation,
    salary_modification_explanation,
    salary_rule,
    add_comp_amt_1,
    add_comp_amt_2,
    add_comp_amt_3,
    add_comp_amt_4,
    add_comp_amt_5,
    add_comp_name_1,
    add_comp_name_2,
    add_comp_name_3,
    add_comp_name_4,
    add_comp_name_5,
    concated_add_comp,
    valid_approval,
from {{ ref("int_surveys__renewal_responses_feed") }}
