select
    -- noqa: disable=RF05
    s.student_number as `01 Student ID`,

    null as `02 SSID`,
    null as `03 Last Name`,
    null as `04 First Name`,
    null as `05 Middle Name`,
    null as `06 Birth Date`,

    concat(
        regexp_extract(s._dbt_source_relation, r'(kipp\w+)_'), enr.cc_sectionid
    ) as `07 Section ID`,

    s.schoolid as `08 Site ID`,

    enr.cc_course_number as `09 Course ID`,
    enr.teachernumber as `10 User ID`,
    enr.cc_dateenrolled as `11 Entry Date`,
    enr.cc_dateleft as `12 Leave Date`,

    case
        when s.grade_level in (-2, -1)
        then 15
        when s.grade_level = 99
        then 14
        else s.grade_level + 1
    end as `13 Grade Level ID`,
    concat(s.academic_year, '-', (s.academic_year + 1)) as `14 Academic Year`,

    null as `15 Session Type ID`,
from {{ ref("base_powerschool__student_enrollments") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as enr
    on s.studentid = enr.cc_studentid
    and s.academic_year = enr.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="s", right_alias="enr") }}
    and not enr.is_dropped_section
where s.academic_year = {{ var("current_academic_year") }} and s.rn_year = 1
