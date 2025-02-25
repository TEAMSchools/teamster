select *, from {{ source("amplify", "src_amplify__dibels_measures") }}
