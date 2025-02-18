select
    repo_grade_level_id,
    repository_id,
    grade_level_id,
    grade_level_id - 1 as grade_level,
from {{ source("illuminate", "repository_grade_levels") }}
where not _fivetran_deleted
