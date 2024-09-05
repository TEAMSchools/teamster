select *, from {{ source("amplify", "src_amplify__dibels_progress_export") }}
