with
    full_roster as (select *, from {{ ref("int_people__staff_roster") }}),

    ops_pm_roster as (select *, from {{ ref("rpt_gsheets__operations_pm_roster") }}),

    schools as (
        select *, from {{ ref("stg_google_sheets__people__location_crosswalk") }}
    ),

    terms as (select *, from {{ ref("stg_google_sheets__reporting__terms") }}),

    form_responses as (
        select *,
        from {{ ref("int_google_forms__form_responses") }}
        where
            /* Operations Teammate PM Form */
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

            -- pivoting out employee_number, PM round selected
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
            ) over (partition by form_responses.response_id) as round_survey,
        from form_responses
    ),

    final as (
        select
            terms.academic_year,
            terms.type,
            terms.code,
            terms.name,

            ops_pm_roster.employee_number,
            ops_pm_roster.formatted_name,
            ops_pm_roster.job_title,
            ops_pm_roster.home_work_location_name,
            ops_pm_roster.home_work_location_abbreviation,
            ops_pm_roster.reports_to_formatted_name,

            responses_pivoted.form_id,
            responses_pivoted.survey_title,
            responses_pivoted.item_id,
            responses_pivoted.section_title,
            responses_pivoted.question_id,
            responses_pivoted.question_title,
            responses_pivoted.item_abbreviation,
            responses_pivoted.response_id,
            responses_pivoted.last_submitted_date_local,
            responses_pivoted.respondent_email,
            responses_pivoted.text_value,
            responses_pivoted.text_value_int,
            responses_pivoted.form_employee_number,
            responses_pivoted.round_survey,

            schools.abbreviation,
            schools.region,
            schools.grade_band,

            full_roster.formatted_name as respondent_name,
            full_roster.job_title as respondent_job_title,

            if(responses_pivoted.form_employee_number is null, 0, 1) as completion,
        from ops_pm_roster
        inner join terms on terms.type = 'OPS'
        left join
            responses_pivoted
            on ops_pm_roster.employee_number = responses_pivoted.form_employee_number
            and responses_pivoted.last_submitted_date_local
            between terms.start_date and terms.end_date
        left join schools on ops_pm_roster.home_work_location_name = schools.name
        left join
            full_roster on responses_pivoted.respondent_email = full_roster.google_email
    )

select *,
from final
