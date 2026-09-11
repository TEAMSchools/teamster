with
    /*
     * int_surveys__survey_responses is question-grain at 4.1M rows, 32.6
     * questions per submission. That clears both bars in the ranked-column gate
     * (.claude/rules/dbt-sql.md): over ~1M input rows, and over 1 slot hour a
     * week in the models that read it. dbt_utils.deduplicate would pack the
     * whole ~25-column row into array_agg; enumerating the 8 columns the union
     * actually needs keeps the shuffle to those.
     *
     * Ascending survey_question_id reproduces what dbt_utils.deduplicate picked
     * here before, so the swap moves no rows.
     *
     * The pick is not quite arbitrary. Of 126,808 submissions, survey_title,
     * respondent_email, respondent_employee_number, date_submitted and
     * term_code are all constant within the partition, but academic_year is
     * NOT: 68 submissions carry more than one, because the upstream resolves it
     * by joining a submission timestamp into the reporting-terms windows. For
     * those 68 the order key decides which year wins, which then decides which
     * administration the marts attach the submission to. Keep the order key
     * stable until that upstream ambiguity is resolved. TODO: #3918 follow-up.
     */
    live_ranked as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            date_submitted,
            academic_year,
            term_code,

            row_number() over (
                partition by survey_id, survey_response_id order by survey_question_id
            ) as rn,
        from {{ ref("int_surveys__survey_responses") }}
    ),

    live_submissions as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            date_submitted,
            academic_year,
            term_code,
        from live_ranked
        where rn = 1
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
