select
    fr.form_id,
    fr.info_title,
    fr.info_document_title,
    fr.item_id,
    fr.item_title,
    fr.question_id,
    fr.question_title,
    fr.item_abbreviation,
    fr.response_id,
    fr.last_submitted_date_local,
    fr.respondent_email,
    fr.text_value,
    safe_cast(fr.text_value as decimal) as answer_value,
    max(case when fr.item_title = 'School Name:' then fr.text_value end) over (
        partition by fr.response_id
    ) as school_name,
from {{ ref("int_google_forms__form_responses") }} as fr
left join
    {{ ref("int_people__staff_roster") }} as sr on fr.respondent_email = sr.google_email
where
    fr.form_id = '1lYa4PDXK9_SfTx72BfJKgbA8F7NUS0ifYRo0pTp6ynQ'
    and fr.text_value is not null
