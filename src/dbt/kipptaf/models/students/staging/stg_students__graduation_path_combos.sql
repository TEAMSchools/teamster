select *, from {{ source("students", "src_students__graduation_path_combos") }}
