-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    students_student_number as `01 Student ID`,

    null as `02 SSID`,
    null as `03 Last Name`,
    null as `04 First Name`,
    null as `05 Middle Name`,
    null as `06 Birth Date`,

    concat(
        regexp_extract(_dbt_source_relation, r'(kipp\w+)_'), cc_sectionid
    ) as `07 Section ID`,

    cc_schoolid as `08 Site ID`,
    cc_course_number as `09 Course ID`,
    teachernumber as `10 User ID`,
    cc_dateenrolled as `11 Entry Date`,
    cc_dateleft as `12 Leave Date`,

    case
        when students_grade_level in (-2, -1)
        then 15
        when students_grade_level = 99
        then 14
        else students_grade_level + 1
    end as `13 Grade Level ID`,

    concat(cc_academic_year, '-', cc_academic_year + 1) as `14 Academic Year`,

    null as `15 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("base_powerschool__course_enrollments") }}
where
    cc_academic_year = {{ current_school_year(var("local_timezone")) }}
    and not is_dropped_section
