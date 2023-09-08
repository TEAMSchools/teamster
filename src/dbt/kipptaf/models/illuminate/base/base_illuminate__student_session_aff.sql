select
    ssa.stu_sess_id,
    ssa.student_id,
    ssa.session_id,
    ssa.grade_level_id,
    ssa.attendance_program_id,
    ssa.tuition_payer_code_id,
    ssa.entry_date,
    ssa.leave_date,
    ssa.entry_code_id,
    ssa.exit_code_id,
    ssa.track_number,
    ssa.fte_override,
    ssa.is_primary_ada,
    ssa.created_at,

    s.academic_year,
    s.site_id,

    row_number() over (
        partition by ssa.student_id, s.academic_year
        order by ssa.entry_date desc, ssa.leave_date desc
    ) as rn_student_session_desc,
from {{ source("illuminate", "student_session_aff") }} as ssa
inner join
    {{ source("illuminate", "sessions") }} as s
    on ssa.session_id = s.session_id
    and not s._fivetran_deleted
where not ssa._fivetran_deleted
