select
    f.formid as form_id,

    i.itemid as item_id,
    i.title,
    i.description,

    i.questionitem.question.questionid as question_item__question__question_id,
    i.questionitem.question.required as question_item__question__required,
    i.questionitem.question.grading.pointvalue
    as question_item__question__grading__point_value,
    i.questionitem.question.grading.whenright.text
    as questionitem__question__grading__whenright__text,
    i.questionitem.question.grading.whenwrong.text
    as questionitem__question__grading__whenwrong__text,
    i.questionitem.question.grading.generalfeedback.text
    as questionitem__question__grading__generalfeedback__text,
    i.questionitem.question.choicequestion.shuffle
    as question_item__question__choice_question__shuffle,
    i.questionitem.question.choicequestion.`type`
    as question_item__question__choice_question__type,
    i.questionitem.question.textquestion.paragraph
    as question_item__question__text_question__paragraph,
    i.questionitem.question.scalequestion.low
    as question_item__question__scale_question__low,
    i.questionitem.question.scalequestion.high
    as question_item__question__scale_question__high,
    i.questionitem.question.scalequestion.lowlabel
    as question_item__question__scale_question__low_label,
    i.questionitem.question.scalequestion.highlabel
    as question_item__question__scale_question__high_label,
    i.questionitem.question.datequestion.includetime
    as question_item__question__date_question__include_time,
    i.questionitem.question.datequestion.includeyear
    as question_item__question__date_question__include_year,
    i.questionitem.question.timequestion.duration
    as question_item__question__time_question__duration,
    i.questionitem.question.fileuploadquestion.folderid
    as question_item__question__file_upload_question__folder_id,
    i.questionitem.question.fileuploadquestion.maxfiles
    as question_item__question__file_upload_question__max_files,
    i.questionitem.question.fileuploadquestion.maxfilesize
    as question_item__question__file_upload_question__max_file_size,
    i.questionitem.question.rowquestion.title
    as question_item__question__row_question__title,

    i.questionitem.image.contenturi as question_item__image__content_uri,
    i.questionitem.image.alttext as question_item__image__alt_text,
    i.questionitem.image.sourceuri as question_item__image__source_uri,
    i.questionitem.image.properties.width as question_item__image__properties__width,
    i.questionitem.image.properties.alignment
    as question_item__image__properties__alignment,

    i.questiongroupitem.image.contenturi as question_group_item__image__content_uri,
    i.questiongroupitem.image.alttext as question_group_item__image__alt_text,
    i.questiongroupitem.image.sourceuri as question_group_item__image__source_uri,
    i.questiongroupitem.image.properties.width
    as question_group_item__image__properties__width,
    i.questiongroupitem.image.properties.alignment
    as question_group_item__image__properties__alignment,

    i.questiongroupitem.grid.shufflequestions
    as question_group_item__grid__shuffle_questions,
    i.questiongroupitem.grid.columns.shuffle
    as question_group_item__grid__columns__shuffle,
    i.questiongroupitem.grid.columns.`type` as question_group_item__grid__columns__type,

    i.pagebreakitem.string_field_for_empty_message
    as page_break_item__string_field_for_empty_message,

    i.textitem.string_field_for_empty_message
    as text_item__string_field_for_empty_message,

    i.imageitem.image.contenturi as image_item__image__content_uri,
    i.imageitem.image.alttext as image_item__image__alt_text,
    i.imageitem.image.sourceuri as image_item__image__source_uri,
    i.imageitem.image.properties.width as image_item__image__properties__width,
    i.imageitem.image.properties.alignment as image_item__image__properties__alignment,

    i.videoitem.caption as video_item__caption,
    i.videoitem.video.youtubeuri as video_item__video__youtube_uri,
    i.videoitem.video.properties.width as video_item__video__properties__width,
    i.videoitem.video.properties.alignment as video_item__video__properties__alignment,

{# i.questionItem.question.grading.correctAnswers.answers	REPEATED #}
{# i.questionItem.question.grading.whenRight.material	REPEATED #}
{# i.questionItem.question.grading.whenWrong.material	REPEATED #}
{# i.questionItem.question.grading.generalFeedback.material	REPEATED #}
{# i.questionItem.question.choiceQuestion.options	REPEATED #}
{# i.questionItem.question.fileUploadQuestion.types	REPEATED	STRING #}
{# i.questionGroupItem.grid.columns.options	REPEATED #}
{# i.questionGroupItem.questions	REPEATED #}
{# i.questionGroupItem.questions.grading.correctAnswers.answers	REPEATED #}
{# i.questionGroupItem.questions.grading.whenRight.material	REPEATED #}
{# i.questionGroupItem.questions.grading.whenWrong.material	REPEATED #}
{# i.questionGroupItem.questions.grading.generalFeedback.material #}
{# i.questionGroupItem.questions.choiceQuestion.options	REPEATED #}
{# i.questionGroupItem.questions.fileUploadQuestion.types	REPEATED	STRING #}
from {{ source("google_forms", "src_google_forms__form") }} as f
cross join unnest(f.items) as i
