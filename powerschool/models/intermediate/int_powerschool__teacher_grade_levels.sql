with
    section_teacher as (
        select
            sec.id as sectionid,
            sec.section_number,
            sec.section_type,
            sec.course_number,

            t.teachernumber,
        from {{ ref("stg_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__sectionteacher") }} as st on sec.id = st.sectionid
        inner join
            {{ ref("stg_powerschool__roledef") }} as rd
            on st.roleid = rd.id
            and rd.name in ('Lead Teacher', 'Co-teacher')
        inner join {{ ref("int_powerschool__teachers") }} as t on st.teacherid = t.id
        where sec.section_type != 'SC' or sec.section_type is null
    ),

    grade_level_counts as (
        select
            st.teachernumber,

            enr.cc_yearid,
            enr.cc_academic_year,

            co.grade_level,

            count(distinct enr.cc_sectionid) as section_count_distinct,
            count(enr.cc_studentid) as student_count,
        from section_teacher as st
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on st.sectionid = enr.cc_abs_sectionid
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on enr.cc_studentid = co.studentid
            and enr.cc_dateenrolled between co.entrydate and co.exitdate
        group by st.teachernumber, enr.cc_yearid, enr.cc_academic_year, co.grade_level
    ),

    grade_level_counts_window as (
        select
            teachernumber,
            cc_yearid,
            cc_academic_year,
            grade_level,
            section_count_distinct,
            student_count,

            sum(student_count) over (
                partition by teachernumber, cc_academic_year
            ) as student_total_all_grades,
        from grade_level_counts
    ),

    percentages as (
        select
            teachernumber,
            cc_yearid,
            cc_academic_year,
            grade_level,
            section_count_distinct,
            student_count,
            student_total_all_grades,
            student_count / student_total_all_grades as grade_level_ratio,
        from grade_level_counts_window
    )

select
    teachernumber,
    cc_yearid as yearid,
    cc_academic_year as academic_year,
    grade_level,
    section_count_distinct,
    student_count,
    student_total_all_grades,
    grade_level_ratio,

    row_number() over (
        partition by teachernumber, cc_academic_year order by grade_level_ratio desc
    ) as grade_level_rank,
from percentages
