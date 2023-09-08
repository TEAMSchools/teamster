with
    designation as (
        select
            co.student_number,
            co.academic_year,
            if(co.spedlep != 'No IEP', 'IEP', null) as is_iep,
            if(co.is_504, '504', null) as is_504,
            if(co.lep_status, 'LEP', null) as is_lep,

            if(gpa.gpa_term >= 3.0, 'Quarter GPA 3.0+', null) as is_quarter_gpa_3plus,
            if(gpa.gpa_term >= 3.5, 'Quarter GPA 3.5+', null) as is_quarter_gpa_35plus,

            if(att.ada < 0.9, 'Chronic Absence', null) as is_chronic_absentee,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpa
            on co.studentid = gpa.studentid
            and co.yearid = gpa.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
            and gpa.is_current
        left join
            {{ ref("int_powerschool__ada") }} as att
            on co.studentid = att.studentid
            and co.yearid = att.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
        where co.rn_year = 1 and co.academic_year = {{ var("current_academic_year") }}
    )

select co.student_number, co.academic_year, sp.specprog_name as designation_name,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on co.studentid = sp.studentid
    and co.academic_year = sp.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
    and sp.specprog_name in (
        'Counseling Services',
        'Home Instruction',
        'Out of District',
        'Self-Contained Special Education',
        'Student Athlete',
        'Tutoring'
    )
    and sp.exit_date >= current_date('America/New_York')
where co.rn_year = 1 and co.academic_year = {{ var("current_academic_year") }}

union all

select student_number, academic_year, values_column as designation_name,
from
    designation unpivot (
        values_column for name_column in (
            is_504,
            is_chronic_absentee,
            is_iep,
            is_lep,
            is_quarter_gpa_35plus,
            is_quarter_gpa_3plus
        )
    )
