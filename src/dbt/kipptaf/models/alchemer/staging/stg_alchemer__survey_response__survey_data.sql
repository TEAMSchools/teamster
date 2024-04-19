select
    sr.survey_id,
    sr.id as survey_response_id,

    sd.value.id as question_id,
    sd.value.answer.string_value,

    null as option_value,
    null as rank_value,
from {{ ref("stg_alchemer__survey_response") }} as sr
cross join unnest(sr.survey_data.map_union_answer_null_value) as sd
where sd.value.answer.string_value is not null

union all

select
    sr.survey_id,
    sr.id as survey_response_id,

    sd.value.id as question_id,

    null as string_value,

    ans.value.`option` as option_value,
    ans.value.rank as rank_value,
from {{ ref("stg_alchemer__survey_response") }} as sr
cross join unnest(sr.survey_data.map_union_answer_null_value) as sd
cross join unnest(sd.value.answer.map_union_optionanswer_null_value) as ans
