select *, from {{ source("amplify", "src_amplify__mclass__sftp__pm_student_summary") }}
