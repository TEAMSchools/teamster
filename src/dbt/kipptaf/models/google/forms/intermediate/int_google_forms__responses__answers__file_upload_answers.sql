select
    ra.form_id,
    ra.response_id,
    ra.question_id,

    fua.fileid as `file_id`,
    fua.filename as `file_name`,
    fua.mimetype as `mime_type`,
from {{ ref("stg_google_forms__responses__answers") }} as ra
cross join unnest(ra.file_upload_answers.answers) as fua
