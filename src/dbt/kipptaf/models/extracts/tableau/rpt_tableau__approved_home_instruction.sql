select
    school,
    student_number,
    student_name as student,
    academic_year,
    dob,
    is_504,
    spedlep as iep_status,
    lep_status,
    grade_level,
    region,
    home_instruction_enter_date as enter_date,
    home_instruction_exit_date as exit_date,
    home_instruction_sp_comment as sp_comment,

    if(
        home_instruction_exit_date < current_date('{{ var("local_timezone") }}'),
        'Expired',
        'Current'
    ) as hi_status,
from {{ ref("int_extracts__student_enrollments") }}
where academic_year >= {{ var("current_academic_year") - 1 }} and rn_year = 1
