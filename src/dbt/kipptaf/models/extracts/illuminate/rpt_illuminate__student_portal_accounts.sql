select
    s.student_number as `01 Student Id`,
    saa.student_web_id as `02 Username`,
    saa.student_web_id + '@teamstudents.org' as `03 Email`,
    1 as `04 Enable Portal`,
    saa.student_web_password as `05 Temporary Password`
from {{ ref("stg_powerschool__students") }} as s
inner join
    {{ ref("stg_people__student_logins") }} as saa
    on s.student_number = saa.student_number
where s.enroll_status = 0
