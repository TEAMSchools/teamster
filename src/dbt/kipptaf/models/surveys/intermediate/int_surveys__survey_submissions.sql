with
    /*
     * int_surveys__survey_responses is question-grain. Projected columns do not
     * vary across the questions of one submission, so this collapse is a grain
     * projection and the order_by is a stable tiebreaker, not a business rule.
     */
    live_submissions as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_surveys__survey_responses"),
                partition_by="survey_id, survey_response_id",
                order_by="survey_question_id",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    archive_source as (
        select
            survey_id,
            survey_title,
            respondent_email,
            date_submitted,
            campaign_academic_year,
            campaign_reporting_term,
            respondent_df_employee_number,
            effective_survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }}
        where
            survey_id = 'historic_alchemer_Manager_survey'
            and campaign_academic_year is not null
    ),

    /*
     * int_surveys__manager_survey_details is question-grain too, so the archive
     * arrives at 18 rows per submission. Same grain projection as above; every
     * column selected is constant within the partition.
     */
    archive_submissions as (
        {{
            dbt_utils.deduplicate(
                relation="archive_source",
                partition_by="survey_id, effective_survey_response_id",
                order_by="respondent_df_employee_number",
            )
        }}
    ),

    /*
     * Both arms are normalized onto survey_response_id here so the key is
     * hashed once below rather than once per arm. That single call site is what
     * makes this model the one home for survey_submission_key.
     */
    all_submissions as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            date_submitted,
            academic_year,
            term_code,
        from live_submissions

        union all

        select
            survey_id,

            effective_survey_response_id as survey_response_id,

            survey_title,
            respondent_email,

            respondent_df_employee_number as respondent_employee_number,

            date_submitted,

            campaign_academic_year as academic_year,
            campaign_reporting_term as term_code,
        from archive_submissions
    )

select
    survey_id,
    survey_response_id,
    survey_title,
    respondent_email,
    respondent_employee_number,
    date_submitted,
    academic_year,
    term_code,

    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,
from all_submissions
