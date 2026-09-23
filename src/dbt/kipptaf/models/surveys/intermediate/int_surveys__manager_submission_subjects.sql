with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    subject_source as (
        select survey_id, subject_df_employee_number, effective_survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }}
        where effective_survey_response_id is not null
    ),

    /*
     * int_surveys__manager_survey_details is question-grain and carries one
     * subject per submission, repeated across that submission's question rows.
     * effective_survey_response_id is the live response id on the Google Forms
     * arm and the deterministic fallback on the historic Alchemer arm, so one
     * partition covers both. Grain projection: subject_df_employee_number is
     * constant within the partition, so the order_by never breaks a real tie.
     */
    subjects as (
        {{
            dbt_utils.deduplicate(
                relation="subject_source",
                partition_by="survey_id, effective_survey_response_id",
                order_by="subject_df_employee_number",
            )
        }}
    )

select
    survey_id,

    effective_survey_response_id as survey_response_id,
    subject_df_employee_number as subject_employee_number,
from subjects
