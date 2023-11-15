select
    sda.respondent_legal_entity_name,
    sda.respondent_primary_site,
    sda.campaign_reporting_term,
    sda.question_shortname,
    sda.answer,
    safe_cast(sda.date_submitted as timestamp) as date_submitted,
    safe_cast(sda.campaign_academic_year as integer) as campaign_academic_year,
    safe_cast(
        sda.respondent_df_employee_number as integer
    ) as respondent_df_employee_number,
    safe_cast(sda.answer_value as numeric) as answer_value,
from
    {{
        source(
            "surveys", "src_surveys__cmo_engagement_regional_survey_detail_archive"
        )
    }} as sda
