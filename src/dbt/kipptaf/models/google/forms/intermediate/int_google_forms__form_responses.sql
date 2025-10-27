with
    answers as (
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
    ),

    text_answers as (
        select
            ra.form_id,
            ra.response_id,
            ra.question_id,

            ta.value,

            if(ta.value is null, true, false) as is_null_value,
        from answers as ra
        cross join unnest(ra.text_answers.answers) as ta
    ),

    file_upload_answers as (
        select
            ra.form_id,
            ra.response_id,
            ra.question_id,

            fua.fileid as file_id,
            fua.filename as file_name,
            fua.mimetype as mime_type,
        from answers as ra
        cross join unnest(ra.file_upload_answers.answers) as fua
    )

select
    f.form_id,
    f.revision_id,
    f.responder_uri,
    f.linked_sheet_id,
    f.info_title,
    f.info_document_title,
    f.info_description,
    f.settings_quiz_settings_is_quiz,
    f.item_id,
    f.item_title,
    f.item_description,
    f.image_alt_text,
    f.image_content_uri,
    f.image_alignment,
    f.image_width,
    f.image_source_uri,
    f.video_caption,
    f.video_alignment,
    f.video_width,
    f.video_youtube_uri,
    f.question_group_grid_shuffle_questions,
    f.question_group_grid_columns_type,
    f.question_id,
    f.question_required,
    f.question_kind,
    f.question_point_value,
    f.question_general_feedback_text,
    f.question_when_right_text,
    f.question_when_wrong_text,
    f.question_include_time,
    f.question_include_year,
    f.question_folder_id,
    f.question_max_files,
    f.question_max_file_size,
    f.question_types,
    f.question_title,
    f.question_high,
    f.question_high_label,
    f.question_low,
    f.question_low_label,
    f.question_paragraph,
    f.question_duration,
    f.question_choice_shuffle,
    f.question_choice_type,
    f.item_kind,
    f.item_abbreviation,
    f.item_url_id,

    r.response_id,
    r.respondent_email,
    r.total_score,
    r.answers,
    r.create_time,
    r.create_timestamp,
    r.last_submitted_time,
    r.last_submitted_timestamp,
    r.last_submitted_date_local,
    r.rn_form_respondent_submitted_desc,

    rata.value as text_value,
    rata.is_null_value as text_is_null_value,

    rafu.file_id as file_upload_file_id,
    rafu.file_name as file_upload_file_name,
    rafu.mime_type as file_upload_mime_type,

    safe_cast(
        regexp_extract(
            max(if(f.item_abbreviation = 'respondent_name', rata.value, null)) over (
                partition by r.response_id, r.respondent_email
            ),
            r'(\d{6})'
        ) as int
    ) as employee_number,
from {{ ref("int_google_forms__form__items") }} as f
left join {{ ref("stg_google_forms__responses") }} as r on f.form_id = r.form_id
left join
    text_answers as rata
    on f.form_id = rata.form_id
    and f.question_id = rata.question_id
    and r.response_id = rata.response_id
left join
    file_upload_answers as rafu
    on f.form_id = rafu.form_id
    and f.question_id = rafu.question_id
    and r.response_id = rafu.response_id
