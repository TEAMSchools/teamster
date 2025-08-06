with
    student_enrollments as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            yearid,
            academic_year,
            schoolid,
            spedlep,
            is_504,
            lep_status,
            ada,
        from {{ ref("int_extracts__student_enrollments") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    designation as (
        select
            co.student_number,
            co.academic_year,

            if(co.spedlep != 'No IEP', 'IEP', null) as is_iep,
            if(co.is_504, '504', null) as is_504,
            if(co.lep_status, 'LEP', null) as is_lep,
            if(co.ada <= 0.9, 'Chronic Absence', null) as is_chronic_absentee,

            if(gpa.gpa_term >= 2.0, 'Quarter GPA 2.0+', null) as is_quarter_gpa_2plus,
            if(gpa.gpa_term >= 2.5, 'Quarter GPA 2.5+', null) as is_quarter_gpa_25plus,
            if(gpa.gpa_term >= 3.0, 'Quarter GPA 3.0+', null) as is_quarter_gpa_3plus,
            if(gpa.gpa_term >= 3.5, 'Quarter GPA 3.5+', null) as is_quarter_gpa_35plus,

            if(
                ps.n_failing is null or ps.n_failing = 0 and co.grade_level >= 5,
                'Failing 0 Classes',
                null
            ) as is_failing_0_classes_y1,
        from student_enrollments as co
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on co.academic_year = rt.academic_year
            and co.schoolid = rt.school_id
            and rt.type = 'RT'
            and rt.is_current
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpa
            on co.studentid = gpa.studentid
            and co.yearid = gpa.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
            and rt.name = gpa.term_name
            and {{ union_dataset_join_clause(left_alias="rt", right_alias="gpa") }}
        left join
            {{ ref("int_powerschool__final_grades_rollup") }} as ps
            on co.studentid = ps.studentid
            and co.academic_year = ps.academic_year
            and {{ union_dataset_join_clause(left_alias="co", right_alias="ps") }}
            and rt.name = ps.storecode
            and {{ union_dataset_join_clause(left_alias="rt", right_alias="ps") }}
    )

select co.student_number, co.academic_year, sp.specprog_name as designation_name,
from student_enrollments as co
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
    and sp.exit_date >= current_date('{{ var("local_timezone") }}')

union all

select student_number, academic_year, values_column as designation_name,
from
    designation unpivot (
        values_column for name_column in (
            is_504,
            is_chronic_absentee,
            is_iep,
            is_lep,
            is_quarter_gpa_2plus,
            is_quarter_gpa_25plus,
            is_quarter_gpa_35plus,
            is_quarter_gpa_3plus,
            is_failing_0_classes_y1
        )
    )
