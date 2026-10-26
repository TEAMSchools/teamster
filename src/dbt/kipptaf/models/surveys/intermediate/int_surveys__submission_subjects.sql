with
    subject_answers as (
        select
            form_id,
            response_id,

            max(
                if(
                    item_abbreviation in ('subject_employee_number', 'employee_name'),
                    regexp_extract(text_value, r'\((\d{6})\)'),
                    null
                )
            ) as subject_employee_number_answer,
            max(
                if(
                    -- Miami-only form, so every family answer is a Miami student
                    info_title = 'KIPP Miami Re-Commitment Form'
                    ' & Family School Community Diagnostic'
                    and item_abbreviation = 'family_respondent_number'
                    and regexp_contains(text_value, r'^\d{5,6}$'),
                    -- Miami's PowerSchool-to-Focus student number prefix
                    concat('8400', text_value),
                    null
                )
            ) as respondent_student_number_answer,
        from {{ ref("int_google_forms__form_responses") }}
        where
            item_abbreviation
            in ('subject_employee_number', 'employee_name', 'family_respondent_number')
        group by form_id, response_id
    )

select
    form_id as survey_id,
    response_id as survey_response_id,

    safe_cast(subject_employee_number_answer as int64) as subject_employee_number,
    safe_cast(respondent_student_number_answer as int64) as respondent_student_number,
from subject_answers
