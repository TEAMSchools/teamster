select
    studentcount as student_count,
    studentwithguardiancount as student_with_guardian_count,
from {{ source("deanslist", "src_deanslist__dff_stats") }}
