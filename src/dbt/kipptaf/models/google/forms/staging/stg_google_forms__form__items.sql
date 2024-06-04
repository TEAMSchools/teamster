with
    items as (
        select
            f.formid as form_id,

            i.itemid as item_id,
            i.title as item_title,
            i.description as item_description,

            i.questionitem as question_item,
            i.questiongroupitem as question_group_item,
            i.imageitem as image_item,
            i.videoitem as video_item,
        {#
            i.pagebreakitem as page_break_item,
            i.textitem as text_item,
        #}
        from {{ source("google_forms", "src_google_forms__form") }} as f
        cross join unnest(f.items) as i
    ),

    image_items as (
        select
            form_id,
            item_id,
            item_title,
            item_description,

            'Image' as item_kind,

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

            'Video' as item_kind,

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

            null as question_group_grid_shuffle_questions,
            null as question_group_grid_columns_type,

            question_item.question,

            'Question' as item_kind,
        from items
        where question_item is not null

        union all

        select
            form_id,
            item_id,
            item_title,
            item_description,

            question_group_item.image.alttext as image_alt_text,
            question_group_item.image.contenturi as image_content_uri,
            question_group_item.image.properties.alignment as image_alignment,
            question_group_item.image.properties.width as image_width,
            question_group_item.image.sourceuri as image_source_uri,

            question_group_item.grid.shufflequestions
            as question_group_grid_shuffle_questions,
            question_group_item.grid.columns.type as question_group_grid_columns_type,

            question,

            'Question Group' as item_kind,
        {#
            gco.isother as is_other,
            gco.value as value,

            gco.image.alttext as alt_text,
            gco.image.contenturi as content_uri,
            gco.image.properties.alignment as alignment,
            gco.image.properties.width as width,
            gco.image.sourceuri as source_uri,

            null as go_to_section_kind,
            gco.gotoaction as go_to_action,
            gco.gotosectionid as go_to_section_id,
        #}
        from items
        cross join unnest(question_group_item.questions) as question
        where question_group_item is not null
    {#
        cross join unnest(question_group_item.grid.columns.options) as gco
    #}
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

        {#
            cqo.gotoaction as option_go_to_action,
            cqo.gotosectionid as option_go_to_section_id,
            cqo.isother as option_is_other,
            cqo.value as option_value,

            cqo.image.alttext as image_alt_text,
            cqo.image.contenturi as image_content_uri,
            cqo.image.properties.alignment as image_alignment,
            cqo.image.properties.width as image_width,
            cqo.image.sourceuri as image_source_uri,
        #}
        {#
            gcaa.value as value,

            gwrm.link.displaytext as display_text,
            gwrm.link.uri as uri,
            gwrm.video.displaytext as display_text,
            gwrm.video.youtubeuri as youtube_uri,

            gwwm.link.displaytext as display_text,
            gwwm.link.uri as uri,
            gwwm.video.displaytext as display_text,
            gwwm.video.youtubeuri as youtube_uri,

            ggfm.link.displaytext as display_text,
            ggfm.link.uri as uri,
            ggfm.video.displaytext as display_text,
            ggfm.video.youtubeuri as youtube_uri,
        #}
        from question_item_kinds
    {#
        cross join unnest(i.questionitem.question.choicequestion.options) as cqo
    #}
    {#
        cross join unnest(i.questionitem.question.grading.whenright.material) as gwrm
        cross join unnest(i.questionitem.question.grading.whenwrong.material) as gwwm
        cross join
            unnest(i.questionitem.question.grading.generalfeedback.material) as ggfm
        cross join
            unnest(i.questionitem.question.grading.correctanswers.answers) as gcaa
    #}
    )

select
    form_id,
    item_id,
    item_title,
    item_description,
    item_kind,

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
from image_items

union all

select
    form_id,
    item_id,
    item_title,
    item_description,
    item_kind,

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
from video_items

union all

select
    form_id,
    item_id,
    item_title,
    item_description,
    item_kind,

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
from questions
