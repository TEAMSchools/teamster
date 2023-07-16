select
    enr.student_number as `01 Student Id`,
    null as `02 Ssid`,
    null as `03 Last Name`,
    null as `04 First Name`,
    null as `05 Middle Name`,
    null as `06 Birth Date`,
    concat(
        case
            when enr.`Db_Name` = 'kippnewark'
            then 'NWK'
            when enr.`Db_Name` = 'kippcamden'
            then 'CMD'
            when enr.`Db_Name` = 'kippmiami'
            then 'MIA'
        end,
        enr.sectionid
    ) as `07 Section Id`,
    enr.schoolid as `08 Site Id`,
    enr.course_number as `09 Course Id`,
    enr.teachernumber as `10 User Id`,
    enr.dateenrolled as `11 Entry Date`,
    enr.dateleft as `12 Leave Date`,
    case
        when co.grade_level in (-2, -1)
        then 15
        when co.grade_level = 99
        then 14
        else co.grade_level + 1
    end as `13 Grade Level Id`,
    concat(enr.academic_year, '-', (enr.academic_year + 1)) as `14 Academic Year`,
    null as `15 Session Type Id`
from {{ ref("base_powerschool__course_enrollments") }} as enr
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on enr.student_number = co.student_number
    and enr.academic_year = co.academic_year
    and enr.`Db_Name` = co.`Db_Name`
    and co.rn_year = 1
where enr.course_enroll_status = 0 and enr.section_enroll_status = 0
