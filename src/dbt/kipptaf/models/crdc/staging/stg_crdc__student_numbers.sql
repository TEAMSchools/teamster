select *, from {{ source("crdc", "src_crdc__student_numbers") }}
