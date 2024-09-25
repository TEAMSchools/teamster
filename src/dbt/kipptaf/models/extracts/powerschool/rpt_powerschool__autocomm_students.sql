with
    grad_path as (
        select _dbt_source_relation, student_number, discipline, final_grad_path,
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
                max(final_grad_path) for discipline in (
                    'Math' as `s_nj_stu_x__graduation_pathway_math`,
                    'ELA' as `s_nj_stu_x__graduation_pathway_ela`
                )
            )
    )

-- trunk-ignore(sqlfluff/ST06)
select
    se.student_number,
    se.student_web_id,

    if(
        s.student_web_password is not null, null, se.student_web_password
    ) as student_web_password,

    se.advisory_name as team,
    se.lunch_status as eligibility_name,
    se.lunch_balance as total_balance,
    se.advisor_lastfirst as home_room,

    if(
        s.student_web_password is not null, null, se.student_web_password
    ) as web_password,

    g.s_nj_stu_x__graduation_pathway_math,
    g.s_nj_stu_x__graduation_pathway_ela,

    format_date('%m/%d/%Y', de.district_entry_date) as district_entry_date,
    format_date('%m/%d/%Y', de.district_entry_date) as school_entry_date,

    se.student_web_id || '.fam' as web_id,
    se.academic_year + (13 - se.grade_level) as graduation_year,

    if(se.enroll_status = 0, 1, 0) as student_allowwebaccess,
    if(se.enroll_status = 0, 1, 0) as allowwebaccess,
    if(se.is_retained_year, 1, 0) as retained_tf,

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

    regexp_extract(se._dbt_source_relation, r'(kipp\w+)_') as code_location,
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
where
    se.academic_year = {{ var("current_academic_year") }}
    and se.rn_year = 1
    and se.grade_level != 99
