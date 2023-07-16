select
    co.student_number as `01 Student Id`,
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
    co.schoolid as `08 Site Id`,
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
    concat(co.academic_year, '-', (co.academic_year + 1)) as `14 Academic Year`,
    null as `15 Session Type Id`
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("base_powerschool__course_enrollments") }} as enr
    on co.student_number = enr.student_number
    and co.academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
    and not enr.is_enrolled_section
where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
