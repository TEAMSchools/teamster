with
    pgfinalgrades_ranked as (
        select
            studentid,
            sectionid,
            finalgradename,
            `percent`,
            citizenship,

            row_number() over (
                partition by studentid, sectionid, finalgradename
                order by lastgradeupdate desc, dcid desc
            ) as rn_final_grade,
        from {{ ref("stg_powerschool__pgfinalgrades") }}
    ),

    enr_tb as (
        select
            enr.cc_dcid,
            enr.cc_sectionid,
            enr.cc_abs_sectionid as sectionid,
            enr.cc_studentid as studentid,
            enr.cc_schoolid as schoolid,
            enr.cc_course_number as course_number,
            enr.courses_credittype as credittype,
            enr.is_dropped_section,

            tb.yearid,
            tb.storecode,
            tb.storecode_type,
            tb.storecode_order,
            tb.date1 as termbin_start_date,
            tb.date2 as termbin_end_date,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on enr.cc_schoolid = tb.schoolid
            and enr.cc_abs_termid = tb.termid
        where not enr.is_dropped_course
    ),

    stored_grades_ranked as (
        /* same pick as int_powerschool__student_course_grades_spine */
        select
            et.cc_dcid,
            et.storecode,

            sg.`percent`,
            sg.behavior,

            row_number() over (
                partition by et.cc_dcid, et.storecode
                order by
                    coalesce(sg.excludefromgpa = 0, false) desc,
                    coalesce(sg.sectionid = et.cc_sectionid, false) desc,
                    sg.datestored desc nulls last,
                    sg.dcid desc
            ) as rn_stored_grade,
        from enr_tb as et
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on et.studentid = sg.studentid
            and et.course_number = sg.course_number
            and et.yearid = sg.yearid
            and et.storecode = sg.storecode
    ),

    enr_gr as (
        select
            et.cc_dcid,
            et.sectionid,
            et.studentid,
            et.schoolid,
            et.course_number,
            et.credittype,
            et.is_dropped_section,
            et.yearid,
            et.storecode,
            et.storecode_type,
            et.storecode_order,
            et.termbin_start_date,
            et.termbin_end_date,

            'RT' || et.storecode_order as reporting_term,
            'Q' || et.storecode_order as `quarter`,

            coalesce(sg.`percent`, pgf.`percent`) as percent_grade,
            coalesce(sg.behavior, pgf.citizenship) as citizenship_grade,

            case
                when
                    et.termbin_end_date < current_date('{{ var("local_timezone") }}')
                    and et.storecode_order = '4'
                then true
                when
                    current_date('{{ var("local_timezone") }}')
                    between et.termbin_start_date and et.termbin_end_date
                then true
                else false
            end as is_current,
        from enr_tb as et
        left join
            pgfinalgrades_ranked as pgf
            on et.studentid = pgf.studentid
            and et.cc_sectionid = pgf.sectionid
            and et.storecode = pgf.finalgradename
            and pgf.rn_final_grade = 1
        left join
            stored_grades_ranked as sg
            on et.cc_dcid = sg.cc_dcid
            and et.storecode = sg.storecode
            and sg.rn_stored_grade = 1
    ),

    ranked as (
        select
            *,

            row_number() over (
                partition by studentid, yearid, course_number, storecode
                order by is_dropped_section asc, percent_grade desc, cc_dcid desc
            ) as rn,
        from enr_gr
    ),

    deduplicate as (select * except (rn), from ranked where rn = 1)

select
    sectionid,
    studentid,
    schoolid,
    course_number,
    credittype,
    is_dropped_section,
    yearid,
    reporting_term,
    `quarter`,
    termbin_start_date,
    termbin_end_date,
    is_current,
    storecode,
    storecode_type,
    storecode_order,
    percent_grade,
    citizenship_grade,

    /* rounding to 6 places first stops float summation order from flipping an
       exact .5 between builds */
    round(
        round(
            avg(percent_grade) over (
                partition by studentid, yearid, course_number, storecode_type
                order by termbin_start_date asc
            ),
            6
        ),
        0
    ) as percent_grade_y1_running,
from deduplicate
