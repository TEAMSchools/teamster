select
    stu_sess_id,
    student_id,
    session_id,
    grade_level_id,
    attendance_program_id,
    tuition_payer_code_id,
    entry_date,
    leave_date,
    entry_code_id,
    exit_code_id,
    track_number,
    fte_override,
    is_primary_ada,
    created_at,
    row_number() over (
        partition by student_id, session_id order by entry_date desc
    ) as rn_student_session_desc,
    row_number() over (
        partition by student_id, session_id, grade_level_id order by entry_date desc
    ) as rn_student_session_grade_desc,
from {{ source("illuminate", "student_session_aff") }}
where not _fivetran_deleted
