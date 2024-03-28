select
    formid as form_id,
    revisionid as revision_id,
    responderuri as responder_uri,
    linkedsheetid as linked_sheet_id,
    info.title as info_title,
    info.documenttitle as info_document_title,
    info.description as info_description,
    settings.quizsettings.isquiz as settings_quiz_settings_is_quiz,
from {{ source("google_forms", "src_google_forms__form") }}
