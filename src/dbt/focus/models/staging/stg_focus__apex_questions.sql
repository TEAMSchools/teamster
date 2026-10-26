select
    id,
    passage_id,
    rubric_id,
    syear,
    type,
    status,
    auto_grade,
    shuffle_answers,
    dok,
    bloom_taxonomy,
    uuid,
    vendor_id,
    import_legacy_id,
    import_source,
    created_at,
    updated_at,
from {{ source("focus", "apex_questions") }}
where deleted is not true
