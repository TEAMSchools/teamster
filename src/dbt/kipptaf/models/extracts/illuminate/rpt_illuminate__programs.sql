/* Gifted & Talented */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Import Student ID`,

    null as `02 State Student ID`,

    last_name as `03 Student Last Name`,
    first_name as `04 Student First Name`,

    null as `05 Student Middle Name`,

    dob as `06 Birth Date`,

    127 as `07 Program ID`,
    null as `08 Eligibility Start Date`,
    null as `09 Eligibility End Date`,

    entrydate as `10 Program Start Date`,
    exitdate as `11 Program End Date`,

    concat(academic_year, '-', (academic_year + 1)) as `12 Academic Year`,

    null as `13 Program Eligibility Code`,
    null as `14 Program Exit Code`,
    null as `15 Site ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("base_powerschool__student_enrollments") }}
where
    academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
    and gifted_and_talented = 'Y'
    and grade_level != 99

union all

/* ELL */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Import Student ID`,

    null as `02 State Student ID`,

    last_name as `03 Student Last Name`,
    first_name as `04 Student First Name`,

    null as `05 Student Middle Name`,

    dob as `06 Birth Date`,

    120 as `07 Program ID`,
    null as `08 Eligibility Start Date`,
    null as `09 Eligibility End Date`,

    entrydate as `10 Program Start Date`,
    exitdate as `11 Program End Date`,

    concat(academic_year, '-', (academic_year + 1)) as `12 Academic Year`,

    null as `13 Program Eligibility Code`,
    null as `14 Program Exit Code`,
    null as `15 Site ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("base_powerschool__student_enrollments") }}
where
    academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
    and lep_status
    and grade_level != 99
