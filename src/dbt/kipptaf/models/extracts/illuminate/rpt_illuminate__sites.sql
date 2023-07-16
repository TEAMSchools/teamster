select
    school_number as `01 Site Id`,
    name as `02 Site Name`,
    school_number as `03 State Site Id`,
    case
        when low_grade in (-2, -1)
        then 15
        when low_grade = 99
        then 14
        else low_grade + 1
    end as `04 Start Grade Level Id`,
    case
        when high_grade in (-2, -1)
        then 15
        when high_grade = 99
        then 14
        else high_grade + 1
    end as `05 End Grade Level Id`,
    case
        when high_grade = 8
        then 1
        when high_grade = 12
        then 2
        when high_grade = 0
        then 4
        when high_grade = 4
        then 9
        else 7
    end as `06 School Type Id`,
    null as `07 Address 1`,
    null as `08 Address 2`,
    schoolcity as `09 City`,
    schoolstate as `10 State`,
    schoolzip as `11 Zip Code`,
    null as `12 Local Site Code`,
    null as `13 Annual Hours Of Instruction`,
    null as `14 Annual Number Of Weeks Of Instruction`,
    null as `15 Parent Site Id`
from {{ ref("stg_powerschool__schools") }}
where state_excludefromreporting = 0
