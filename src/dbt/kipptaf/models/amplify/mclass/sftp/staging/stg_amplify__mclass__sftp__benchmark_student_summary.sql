select *,
from {{ source("amplify", "src_amplify__mclass__sftp__benchmark_student_summary") }}
