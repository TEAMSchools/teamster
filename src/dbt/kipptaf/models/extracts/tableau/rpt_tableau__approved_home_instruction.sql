select
    co.school as school,
    co.student_number,
    co.student_name as student,
    co.academic_year,
    co.dob,
    co.is_504,
    co.spedlep as iep_status,
    co.lep_status,
    co.grade_level,
    co.region,

    sp.enter_date,
    sp.exit_date,
    sp.sp_comment,

    if(
        sp.exit_date < current_date('{{ var("local_timezone") }}'), 'Expired', 'Current'
    ) as hi_status,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on co.studentid = sp.studentid
    and co.academic_year = sp.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
    and sp.specprog_name = 'Home Instruction'
    and sp.rn_student_program_year_desc = 1
where co.academic_year >= {{ var("current_academic_year") - 1 }} and co.rn_year = 1
