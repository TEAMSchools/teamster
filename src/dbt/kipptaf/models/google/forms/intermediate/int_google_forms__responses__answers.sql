select
    r.form_id,
    r.response_id,

    a.value.questionid as question_id,
    a.value.grade.score as grade__score,
    a.value.grade.correct as grade__correct,
    a.value.grade.feedback.text as grade__feedback__text,
    a.value.textanswers as text_answers,
    a.value.fileuploadanswers as file_upload_answers,
from {{ ref("stg_google_forms__responses") }} as r
cross join unnest(r.answers) as a
