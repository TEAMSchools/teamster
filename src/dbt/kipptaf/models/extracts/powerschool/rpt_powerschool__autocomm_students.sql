with
    grad_path as (
        select _dbt_source_relation, student_number, discipline, final_grad_path_code,
        from {{ ref("int_students__graduation_path_codes") }}
    ),

    grad_path_pivot as (
        select
            _dbt_source_relation,
            student_number,
            s_nj_stu_x__graduation_pathway_math,
            s_nj_stu_x__graduation_pathway_ela,
        from
            grad_path pivot (
                max(final_grad_path_code) for discipline in (
                    'Math' as `s_nj_stu_x__graduation_pathway_math`,
                    'ELA' as `s_nj_stu_x__graduation_pathway_ela`
                )
            )
    ),

    ps_fafsa_status as (
        select _dbt_source_relation, studentsdcid, fafsa as ps_fafsa_status,
        from {{ ref("stg_powerschool__s_stu_x") }}
    )

select
    se.student_number,
    se.student_web_id,
    se.advisory_name as team,
    se.lunch_status as eligibility_name,
    se.lunch_balance as total_balance,
    se.advisor_lastfirst as home_room,
    se.student_email_google as u_studentsuserfields__studentemail,

    g.s_nj_stu_x__graduation_pathway_math,
    g.s_nj_stu_x__graduation_pathway_ela,

    se.student_web_id || '.fam' as web_id,
    se.academic_year + (13 - se.grade_level) as graduation_year,

    format_date('%m/%d/%Y', de.district_entry_date) as district_entry_date,
    format_date('%m/%d/%Y', de.district_entry_date) as school_entry_date,

    regexp_extract(se._dbt_source_relation, r'(kipp\w+)_') as code_location,

    case
        when pfs.ps_fafsa_status = 'N'
        then pfs.ps_fafsa_status
        when f.overgrad_fafsa_opt_out = 'Yes'
        then 'E'
        when f.overall_has_fafsa
        then 'C'
    end as s_stu_x__fafsa,

    if(se.enroll_status = 0, 1, 0) as student_allowwebaccess,
    if(se.enroll_status = 0, 1, 0) as allowwebaccess,
    if(se.is_retained_year, 1, 0) as retained_tf,

    if(
        s.student_web_password is not null, null, se.student_web_password
    ) as student_web_password,

    if(
        s.student_web_password is not null, null, se.student_web_password
    ) as web_password,

    case
        when se.grade_level in (0, 5, 9)
        then 'A'
        when se.grade_level in (1, 6, 10)
        then 'B'
        when se.grade_level in (2, 7, 11)
        then 'C'
        when se.grade_level in (3, 8, 12)
        then 'D'
        when se.grade_level = 4
        then 'E'
    end as track,

from {{ ref("base_powerschool__student_enrollments") }} as se
left join
    {{ ref("stg_powerschool__students") }} as s
    on se.student_number = s.student_number
    and {{ union_dataset_join_clause(left_alias="se", right_alias="s") }}
left join
    {{ ref("int_powerschool__district_entry_date") }} as de
    on se.studentid = de.studentid
    and {{ union_dataset_join_clause(left_alias="se", right_alias="de") }}
    and de.rn_entry = 1
left join
    grad_path_pivot as g
    on se.student_number = g.student_number
    and {{ union_dataset_join_clause(left_alias="se", right_alias="g") }}
left join
    {{ ref("int_extracts__student_enrollments") }} as f
    on se.academic_year = f.academic_year
    and se.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="se", right_alias="f") }}
left join
    ps_fafsa_status as pfs
    on se.students_dcid = pfs.studentsdcid
    and {{ union_dataset_join_clause(left_alias="se", right_alias="pfs") }}
where
    se.academic_year = {{ var("current_academic_year") }}
    and se.rn_year = 1
    and se.grade_level != 99
