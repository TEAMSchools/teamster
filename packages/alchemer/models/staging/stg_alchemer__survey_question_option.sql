{{ config(schema="alchemer") }}

select
    sq.survey_id,
    sq.id as survey_question_id,

    sqo.id as option_id,
    sqo.value,
    sqo.properties.disabled,
from {{ ref("stg_alchemer__survey_question") }} as sq
cross join unnest(sq.`options`) as sqo
where array_length(sq.`options`) > 0
