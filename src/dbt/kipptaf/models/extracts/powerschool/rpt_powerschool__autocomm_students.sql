select
    se.student_number,
    se.student_web_id,
    se.student_web_password,
    if(se.enroll_status = 0, 1, 0) as student_allowwebaccess,
    se.student_web_id || '.fam' as web_id,
    se.student_web_password as web_password,
    if(se.enroll_status = 0, 1, 0) as allowwebaccess,
    se.advisory_name as team,
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
    se.lunch_status as eligibility_name,
    se.lunch_balance as total_balance,
    se.advisor_lastfirst as home_room,
    se.academic_year + (13 - se.grade_level) as graduation_year,
    regexp_extract(se._dbt_source_relation, r'(kipp\w+)_\w+') as code_location,

    format_date('%m/%d/%Y', de.district_entry_date) as district_entry_date,
    format_date('%m/%d/%Y', de.district_entry_date) as school_entry_date,
from {{ ref("base_powerschool__student_enrollments") }} as se
left join
    {{ ref("int_powerschool__district_entry_date") }} as de
    on se.studentid = de.studentid
    and {{ union_dataset_join_clause(left_alias="se", right_alias="de") }}
    and de.rn_entry = 1
where
    se.academic_year = {{ var("current_academic_year") }}
    and se.rn_year = 1
    and se.grade_level != 99
