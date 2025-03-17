select *, from {{ source("reporting", "src_reporting__graduation_path_combos") }}
