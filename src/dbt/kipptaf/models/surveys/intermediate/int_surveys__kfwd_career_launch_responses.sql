/* KIPP Forward Career Launch Survey */
select
    ri.response_date_submitted,
    ri.respondent_salesforce_id,

    'Alchemer survey' as survey_title,

    sr.question_short_name,
    sr.response_string_value,

    cast(ri.survey_id as string) as survey_id,
    cast(ri.response_id as string) as response_id,
    lower(ri.respondent_user_principal_name) as respondent_user_principal_name,
from {{ source("surveys", "int_surveys__response_identifiers") }} as ri
inner join
    {{ source("alchemer", "base_alchemer__survey_results") }} as sr
    on ri.survey_id = sr.survey_id
    and ri.response_id = sr.response_id
where ri.survey_id = 6734664

union all

/* KIPP Forward Career Launch Survey - OLD */
select
    safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,

    -- Google Forms responses are matched by email only
    null as respondent_salesforce_id,

    'Google Form v1' as survey_title,

    fr.item_abbreviation as question_short_name,
    fr.text_value as response_string_value,

    cast(fr.form_id as string) as survey_id,
    cast(fr.response_id as string) as response_id,
    lower(fr.respondent_email) as respondent_user_principal_name,
from {{ ref("int_google_forms__form_responses") }} as fr
where fr.form_id = '1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho'

union all

/* KIPP Forward Career Launch Survey */
select
    safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,

    -- Google Forms responses are matched by email only
    null as respondent_salesforce_id,

    'Google Form v2' as survey_title,

    fr.item_abbreviation as question_short_name,
    fr.text_value as response_string_value,

    cast(fr.form_id as string) as survey_id,
    cast(fr.response_id as string) as response_id,
    lower(fr.respondent_email) as respondent_user_principal_name,
from {{ ref("int_google_forms__form_responses") }} as fr
where fr.form_id = '1c4SLP61YIVnUUvRl_IUdFuLXdtI1Vsq9OE3Jrz3HR0U'
