select
    co.school_abbreviation as school,
    co.student_number,
    co.lastfirst as student,
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

    case
        when sp.exit_date < current_date('{{ var("local_timezone") }}')
        then 'Expired'
        else 'Current'
    end as hi_status,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on co.studentid = sp.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
    and co.academic_year = sp.academic_year
    and sp.specprog_name = 'Home Instruction'
where co.academic_year >= {{ var("current_academic_year") }} - 1 and co.rn_year = 1
