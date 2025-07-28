with

    full_roster as (select *, from {{ ref("int_people__staff_roster") }}),

    ops_pm_roster as (select *, from {{ ref("rpt_gsheets__operations_pm_roster") }}),

    schools as (select *, from {{ ref("stg_people__location_crosswalk") }}),

    form_responses as (
        select *
        from {{ ref("int_google_forms__form_responses") }}
        -- filtering for Operations EKG Form
        where
            form_id = '1oPcgOeaNS7DNaG2wa9JnfkWfxfxp7eOuj3XnXJoe-vE'
            and text_value is not null
    ),

    responses_pivoted as (
        select
            form_id,
            info_document_title as survey_title,
            item_id,
            item_title as section_title,
            question_id,
            question_title,
            item_abbreviation,
            response_id,
            last_submitted_date_local,
            respondent_email,
            text_value,
            if(
                regexp_contains(text_value, r'^-?\d+$'),
                safe_cast(text_value as int),
                null
            ) as text_value_int,

            -- pivoting out employee_number, walkthrough round and school selection
            -- items
            max(
                case
                    when form_responses.item_id = '53d2a0dc'
                    then
                        safe_cast(
                            regexp_extract(
                                form_responses.text_value, r'\[(\d{6})\]$'
                            ) as int
                        )
                end
            ) over (partition by form_responses.response_id) as form_employee_number,
            max(
                case
                    when form_responses.item_id = '1511dc24'
                    then form_responses.text_value
                end
            ) over (partition by form_responses.response_id) as walkthrough_round,
            max(
                case
                    when form_responses.item_id = '3a4fdfe4'
                    then form_responses.text_value
                end
            ) over (partition by form_responses.response_id) as form_school,
        from form_responses

    ),

    final as (
        select
            ops_pm_roster.*,
            responses_pivoted.*,
            schools.abbreviation,
            schools.region,
            schools.grade_band,
            full_roster.formatted_name as respondent_name,
            full_roster.job_title as respondent_job_title,
            if(responses_pivoted.form_employee_number is null, 0, 1) as completion,
        from ops_pm_roster
        left join
            responses_pivoted
            on ops_pm_roster.employee_number = responses_pivoted.form_employee_number
        left join schools on ops_pm_roster.home_work_location_name = schools.name
        left join
            full_roster on full_roster.google_email = responses_pivoted.respondent_email

    )

select *,
from final
