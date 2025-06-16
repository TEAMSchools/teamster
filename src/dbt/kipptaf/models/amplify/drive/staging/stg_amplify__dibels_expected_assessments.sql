select *, from {{ source("amplify", "src_amplify__dibels_expected_assessments") }}
