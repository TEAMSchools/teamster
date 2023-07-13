select ra.form_id, ra.response_id, ra.question_id, ta.value,
from {{ ref("stg_google_forms__responses_answers") }} as ra
cross join unnest(ra.text_answers.answers) as ta
