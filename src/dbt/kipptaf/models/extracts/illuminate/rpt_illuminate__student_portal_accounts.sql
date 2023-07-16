select
    s.student_number as `01 Student Id`,
    sl.username as `02 Username`,
    sl.google_email as `03 Email`,
    1 as `04 Enable Portal`,
    saa.password as `05 Temporary Password`
from {{ ref("stg_powerschool__students") }} as s
inner join
    {{ ref("stg_people__student_logins") }} as sl
    on s.student_number = sl.student_number
where s.enroll_status = 0
