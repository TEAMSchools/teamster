-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    concat(
        regexp_extract(_dbt_source_relation, r'(kipp\w+)_'), sections_id
    ) as `01 Section ID`,

    terms_schoolid as `02 Site ID`,
    terms_name as `03 Term Name`,

    sections_course_number as `04 Course ID`,

    teachernumber as `05 User ID`,

    if(
        terms_schoolid = 73253, sections_expression, sections_section_number
    ) as `06 Period`,

    concat(terms_academic_year, '-', terms_academic_year + 1) as `07 Academic Year`,

    null as `08 Room Number`,
    null as `09 Session Type ID`,
    null as `10 Local Term ID`,
    null as `11 Quarter Num`,

    terms_firstday as `12 User Start Date`,
    terms_lastday as `13 User End Date`,

    1 as `14 Primary Teacher`,
    null as `15 Teacher Competency Level`,
    null as `16 Is Attendance Enabled`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("base_powerschool__sections") }}
where terms_academic_year = {{ current_school_year(var("local_timezone")) }}
