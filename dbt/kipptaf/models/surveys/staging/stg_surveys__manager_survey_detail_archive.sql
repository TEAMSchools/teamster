select
    * except (
        date_submitted,
        campaign_academic_year,
        respondent_df_employee_number,
        subject_df_employee_number,
        answer_value
    ),

    safe_cast(date_submitted as timestamp) as date_submitted,
    safe_cast(campaign_academic_year as integer) as campaign_academic_year,
    safe_cast(
        respondent_df_employee_number as integer
    ) as respondent_df_employee_number,
    safe_cast(subject_df_employee_number as integer) as subject_df_employee_number,
    safe_cast(answer_value as numeric) as answer_value,
from {{ source("surveys", "src_surveys__manager_survey_detail_archive") }}
