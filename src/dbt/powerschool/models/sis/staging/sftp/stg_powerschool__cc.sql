select
    * except (
        currentabsences,
        currenttardies,
        dateenrolled,
        dateleft,
        dcid,
        id,
        schoolid,
        sectionid,
        studentid,
        studyear,
        teacherid,
        termid
    ),

    cast(currentabsences as int) as currentabsences,
    cast(currenttardies as int) as currenttardies,
    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(sectionid as int) as sectionid,
    cast(studentid as int) as studentid,
    cast(studyear as int) as studyear,
    cast(teacherid as int) as teacherid,
    cast(termid as int) as termid,

    cast(dateenrolled as date) as dateenrolled,
    cast(dateleft as date) as dateleft,

{# 
| yearid                |                 | INT64         | missing in definition |
| abs_sectionid         |                 | INT64         | missing in definition |
| abs_termid            |                 | INT64         | missing in definition |
| academic_year         |                 | INT64         | missing in definition |
| fiscal_year           |                 | INT64         | missing in definition |
| ab_course_cmp_ext_crd | STRING          |               | missing in contract   |
| ab_course_cmp_fun_flg | STRING          |               | missing in contract   |
| ab_course_cmp_met_cd  | STRING          |               | missing in contract   |
| ab_course_cmp_sta_cd  | STRING          |               | missing in contract   |
| ab_course_eva_pro_cd  | STRING          |               | missing in contract   |
| asmtscores            | STRING          |               | missing in contract   |
| attendance            | STRING          |               | missing in contract   |
| attendance_type_code  | STRING          |               | missing in contract   |
| expression            | STRING          |               | missing in contract   |
| finalgrades           | STRING          |               | missing in contract   |
| firstattdate          | STRING          |               | missing in contract   |
| ip_address            | STRING          |               | missing in contract   |
| lastattmod            | STRING          |               | missing in contract   |
| lastgradeupdate       | STRING          |               | missing in contract   |
| log                   | STRING          |               | missing in contract   |
| origsectionid         | STRING          |               | missing in contract   |
| period_obsolete       | STRING          |               | missing in contract   |
| psguid                | STRING          |               | missing in contract   |
| studentsectenrl_guid  | STRING          |               | missing in contract   |
| teachercomment        | STRING          |               | missing in contract   |
| teacherprivatenote    | STRING          |               | missing in contract   |
| transaction_date      | STRING          |               | missing in contract   |
| unused2               | STRING          |               | missing in contract   |
| unused3               | STRING          |               | missing in contract   |
| whomodifiedid         | STRING          |               | missing in contract   |
| whomodifiedtype       | STRING          |               | missing in contract   |
#}
from {{ source("powerschool_sftp", "src_powerschool__cc") }}
