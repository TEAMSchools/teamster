with
    items as (
        select
            f.form_id,

            i.itemid as item_id,
            i.title as item_title,
            i.description as item_description,
            i.questionitem as question_item,
            i.imageitem as image_item,
            i.videoitem as video_item,

            /* repeated records */
            i.questiongroupitem as question_group_item,
        from {{ ref("stg_google_forms__form") }} as f
        cross join unnest(f.items) as i
    ),

    image_items as (
        select
            form_id,
            item_id,
            item_title,
            item_description,

            image_item.image.alttext as image_alt_text,
            image_item.image.contenturi as image_content_uri,
            image_item.image.properties.alignment as image_alignment,
            image_item.image.properties.width as image_width,
            image_item.image.sourceuri as image_source_uri,
        from items
        where image_item is not null
    ),

    video_items as (
        select
            form_id,
            item_id,
            item_title,
            item_description,

            video_item.caption as video_caption,

            video_item.video.properties.alignment as video_alignment,
            video_item.video.properties.width as video_width,
            video_item.video.youtubeuri as video_youtube_uri,
        from items
        where video_item is not null
    ),

    question_item_kinds as (
        select
            form_id,
            item_id,
            item_title,
            item_description,

            question_item.image.alttext as image_alt_text,
            question_item.image.contenturi as image_content_uri,
            question_item.image.properties.alignment as image_alignment,
            question_item.image.properties.width as image_width,
            question_item.image.sourceuri as image_source_uri,

            question_item.question,

            'Question' as item_kind,

            null as question_group_grid_shuffle_questions,
            null as question_group_grid_columns_type,
        from items
        where question_item is not null

        union all

        select
            i.form_id,
            i.item_id,
            i.item_title,
            i.item_description,

            i.question_group_item.image.alttext as image_alt_text,
            i.question_group_item.image.contenturi as image_content_uri,
            i.question_group_item.image.properties.alignment as image_alignment,
            i.question_group_item.image.properties.width as image_width,
            i.question_group_item.image.sourceuri as image_source_uri,

            question,

            'Question Group' as item_kind,

            i.question_group_item.grid.shufflequestions
            as question_group_grid_shuffle_questions,
            i.question_group_item.grid.columns.type as question_group_grid_columns_type,
        from items as i
        cross join unnest(i.question_group_item.questions) as question
        where i.question_group_item is not null
    ),

    questions as (
        select
            form_id,
            item_id,
            item_title,
            item_description,
            image_alt_text,
            image_content_uri,
            image_alignment,
            image_width,
            image_source_uri,
            question_group_grid_shuffle_questions,
            question_group_grid_columns_type,
            item_kind,

            question.questionid as question_id,
            question.required as question_required,

            question.grading.pointvalue as question_point_value,
            question.grading.generalfeedback.text as question_general_feedback_text,
            question.grading.whenright.text as question_when_right_text,
            question.grading.whenwrong.text as question_when_wrong_text,

            question.datequestion.includetime as question_include_time,
            question.datequestion.includeyear as question_include_year,

            question.fileuploadquestion.folderid as question_folder_id,
            question.fileuploadquestion.maxfiles as question_max_files,
            question.fileuploadquestion.maxfilesize as question_max_file_size,
            question.fileuploadquestion.types as question_types,

            question.rowquestion.title as question_title,

            question.scalequestion.high as question_high,
            question.scalequestion.highlabel as question_high_label,
            question.scalequestion.low as question_low,
            question.scalequestion.lowlabel as question_low_label,

            question.textquestion.paragraph as question_paragraph,

            question.timequestion.duration as question_duration,

            question.choicequestion.shuffle as question_choice_shuffle,
            question.choicequestion.type as question_choice_type,

            case
                when question.datequestion is not null
                then 'Date'
                when question.fileuploadquestion is not null
                then 'File Upload'
                when question.rowquestion is not null
                then 'Row'
                when question.scalequestion is not null
                then 'Scale'
                when question.textquestion is not null
                then 'Text'
                when question.timequestion is not null
                then 'Time'
                when question.choicequestion is not null
                then 'Choice'
            end as question_kind,
        from question_item_kinds
    ),

    form_items as (
        select
            form_id,
            item_id,
            item_title,
            item_description,

            image_alt_text,
            image_content_uri,
            image_alignment,
            image_width,
            image_source_uri,

            null as video_caption,
            null as video_alignment,
            null as video_width,
            null as video_youtube_uri,
            null as question_group_grid_shuffle_questions,
            null as question_group_grid_columns_type,
            null as question_id,
            null as question_required,
            null as question_kind,
            null as question_point_value,
            null as question_general_feedback_text,
            null as question_when_right_text,
            null as question_when_wrong_text,
            null as question_include_time,
            null as question_include_year,
            null as question_folder_id,
            null as question_max_files,
            null as question_max_file_size,
            null as question_types,
            null as question_title,
            null as question_high,
            null as question_high_label,
            null as question_low,
            null as question_low_label,
            null as question_paragraph,
            null as question_duration,
            null as question_choice_shuffle,
            null as question_choice_type,

            'Image' as item_kind,
        from image_items

        union all

        select
            form_id,
            item_id,
            item_title,
            item_description,

            null as image_alt_text,
            null as image_content_uri,
            null as image_alignment,
            null as image_width,
            null as image_source_uri,

            video_caption,
            video_alignment,
            video_width,
            video_youtube_uri,

            null as question_group_grid_shuffle_questions,
            null as question_group_grid_columns_type,
            null as question_id,
            null as question_required,
            null as question_kind,
            null as question_point_value,
            null as question_general_feedback_text,
            null as question_when_right_text,
            null as question_when_wrong_text,
            null as question_include_time,
            null as question_include_year,
            null as question_folder_id,
            null as question_max_files,
            null as question_max_file_size,
            null as question_types,
            null as question_title,
            null as question_high,
            null as question_high_label,
            null as question_low,
            null as question_low_label,
            null as question_paragraph,
            null as question_duration,
            null as question_choice_shuffle,
            null as question_choice_type,

            'Video' as item_kind,
        from video_items

        union all

        select
            form_id,
            item_id,
            item_title,
            item_description,
            image_alt_text,
            image_content_uri,
            image_alignment,
            image_width,
            image_source_uri,

            null as video_caption,
            null as video_alignment,
            null as video_width,
            null as video_youtube_uri,

            question_group_grid_shuffle_questions,
            question_group_grid_columns_type,
            question_id,
            question_required,
            question_kind,
            question_point_value,
            question_general_feedback_text,
            question_when_right_text,
            question_when_wrong_text,
            question_include_time,
            question_include_year,
            question_folder_id,
            question_max_files,
            question_max_file_size,
            question_types,
            question_title,
            question_high,
            question_high_label,
            question_low,
            question_low_label,
            question_paragraph,
            question_duration,
            question_choice_shuffle,
            question_choice_type,
            item_kind,
        from questions
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

    fi.item_id,
    fi.item_title,
    fi.item_description,
    fi.image_alt_text,
    fi.image_content_uri,
    fi.image_alignment,
    fi.image_width,
    fi.image_source_uri,
    fi.video_caption,
    fi.video_alignment,
    fi.video_width,
    fi.video_youtube_uri,
    fi.question_group_grid_shuffle_questions,
    fi.question_group_grid_columns_type,
    fi.question_id,
    fi.question_required,
    fi.question_kind,
    fi.question_point_value,
    fi.question_general_feedback_text,
    fi.question_when_right_text,
    fi.question_when_wrong_text,
    fi.question_include_time,
    fi.question_include_year,
    fi.question_folder_id,
    fi.question_max_files,
    fi.question_max_file_size,
    fi.question_types,
    fi.question_title,
    fi.question_high,
    fi.question_high_label,
    fi.question_low,
    fi.question_low_label,
    fi.question_paragraph,
    fi.question_duration,
    fi.question_choice_shuffle,
    fi.question_choice_type,
    fi.item_kind,

    fie.abbreviation as item_abbreviation,
    fie.url_id as item_url_id,
from {{ ref("stg_google_forms__form") }} as f
inner join form_items as fi on f.form_id = fi.form_id
left join
    {{ ref("stg_google_sheets__google_forms__form_items_extension") }} as fie
    on fi.form_id = fie.form_id
    and fi.item_id = fie.item_id
