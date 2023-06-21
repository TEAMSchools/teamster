{{ config(schema="alchemer") }}

select
    sr.survey_id,
    sr.id as survey_response_id,

    sd.value.id as question_id,
    sd.value.answer.string_value,

    ans.*
from {{ ref("stg_alchemer__survey_response") }} as sr
cross join unnest(sr.survey_data.map_survey_data_record_value) as sd
cross join
    unnest(sd.value.answer.map_union_string_surveyresponse_answer_record_value) as ans
