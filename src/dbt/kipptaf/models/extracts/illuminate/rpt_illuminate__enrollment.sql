select
    student_number as `01 Student Id`,
    state_studentnumber as `02 Ssid`,
    last_name as `03 Last Name`,
    first_name as `04 First Name`,
    null as `05 Middle Name`,
    dob as `06 Birth Date`,
    schoolid as `07 Site Id`,
    entrydate as `08 Entry Date`,
    exitdate as `09 Leave Date`,
    case
        when grade_level in (-2, -1)
        then 15
        when grade_level = 99
        then 14
        else grade_level + 1
    end as `10 Grade Level Id`,
    concat(academic_year, '-', (academic_year + 1)) as `11 Academic Year`,
    1 as `12 Is Primary Ada`,
    null as `13 Attendance Program Id`,
    null as `14 Exit Code Id`,
    null as `15 Session Type Id`,
    null as `16 Enrollment Entry Code`
from {{ ref("base_powerschool__student_enrollments") }}
where academic_year = {{ var("current_academic_year") }} and grade_level != 99
