with
    cc as (
        select
            * except (
                ab_course_cmp_ext_crd,
                ab_course_cmp_fun_flg,
                ab_course_cmp_met_cd,
                ab_course_cmp_sta_cd,
                ab_course_eva_pro_cd,
                asmtscores,
                attendance,
                attendance_type_code,
                currentabsences,
                currenttardies,
                custom,
                dateenrolled,
                dateleft,
                dcid,
                executionid,
                expression,
                finalgrades,
                firstattdate,
                id,
                ip_address,
                lastattmod,
                lastgradeupdate,
                `log`,
                origsectionid,
                period_obsolete,
                psguid,
                schoolid,
                sectionid,
                studentid,
                studentsectenrl_guid,
                studyear,
                teachercomment,
                teacherid,
                teacherprivatenote,
                termid,
                transaction_date,
                unused2,
                unused3,
                whomodifiedid,
                whomodifiedtype
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
        from {{ source("powerschool_dlt", "cc") }}
    ),

    abs_calcs as (
        select *, abs(termid) as abs_termid, abs(sectionid) as abs_sectionid, from cc
    ),

    yearid_calc as (
        select *, cast(left(cast(abs_termid as string), 2) as int) as yearid,
        from abs_calcs
    )

select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
from yearid_calc
