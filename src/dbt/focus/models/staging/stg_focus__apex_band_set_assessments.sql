select id, band_set_id, assessment_id, created_at, updated_at,
from {{ source("focus", "apex_band_set_assessments") }}
