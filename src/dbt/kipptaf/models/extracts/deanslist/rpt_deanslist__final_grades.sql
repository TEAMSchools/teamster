with
    enr as (
        select
            enr._dbt_source_relation,
            enr.cc_studentid,
            enr.cc_yearid,
            enr.cc_academic_year,
            enr.cc_sectionid,
            enr.cc_course_number,
            enr.cc_dateenrolled,
            enr.courses_course_name,
            enr.courses_credit_hours,
            enr.sections_dcid,
            enr.sections_section_number,
            enr.students_student_number,
            enr.teacher_lastfirst,
            ifnull(enr.cc_currentabsences, 0) as currentabsences,
            ifnull(enr.cc_currenttardies, 0) as currenttardies,
            abs(enr.sections_excludefromgpa - 1) as include_grades_display,

            rt.name as term_name,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on enr.cc_schoolid = rt.school_id
            and enr.cc_academic_year = rt.academic_year
            and rt.type = 'RT'
        where
            enr.cc_academic_year = {{ var("current_academic_year") }}
            and not enr.is_dropped_course
    ),

    enr_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="enr",
                partition_by="cc_studentid, cc_academic_year, cc_course_number, term_name",
                order_by="cc_dateenrolled desc",
            )
        }}
    )

select
    enr.students_student_number as student_number,
    enr.cc_academic_year as academic_year,
    enr.cc_course_number as course_number,
    enr.cc_sectionid as sectionid,
    enr.sections_dcid as sections_dcid,
    enr.sections_section_number as section_number,
    enr.teacher_lastfirst as teacher_name,
    enr.courses_course_name as course_name,
    enr.courses_credit_hours as credit_hours,
    enr.term_name as term,
    enr.include_grades_display,
    enr.currentabsences,
    enr.currenttardies,

    max(fg.term_percent_grade_adjusted_rt1) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q1_pct`,
    max(fg.term_letter_grade_adjusted_rt1) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q1_letter`,
    max(fg.term_percent_grade_adjusted_rt2) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q2_pct`,
    max(fg.term_letter_grade_adjusted_rt2) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q2_letter`,
    max(fg.term_percent_grade_adjusted_rt3) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q3_pct`,
    max(fg.term_letter_grade_adjusted_rt3) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q3_letter`,
    max(fg.term_percent_grade_adjusted_rt4) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q4_pct`,
    max(fg.term_letter_grade_adjusted_rt4) over (
        partition by enr.cc_studentid, enr.cc_yearid, enr.cc_course_number
        order by enr.term_name asc
    ) as `Q4_letter`,

    coalesce(sgy1.percent, fg.y1_percent_grade_adjusted) as y1_pct,
    coalesce(sgy1.grade, fg.y1_letter_grade) as y1_letter,

    cat.f_cur as f_term,
    cat.s_cur as s_term,
    cat.w_cur as w_term,
    cat.w_rt1,
    cat.w_rt2,
    cat.w_rt3,
    cat.w_rt4,

    coalesce(kctz.ctz_cur, cat.ctz_cur) as ctz_cur,
    coalesce(kctz.ctz_rt1, cat.ctz_rt1) as ctz_rt1,
    coalesce(kctz.ctz_rt2, cat.ctz_rt2) as ctz_rt2,
    coalesce(kctz.ctz_rt3, cat.ctz_rt3) as ctz_rt3,
    coalesce(kctz.ctz_rt4, cat.ctz_rt4) as ctz_rt4,

    comm.comment_value,

    coalesce(
        lead(fg.need_60, 1) over (
            partition by fg.studentid, fg.course_number order by fg.storecode
        ),
        fg.need_60
    ) as need_60,

    null as e1_pct,
    null as e2_pct,
from enr_deduplicate as enr
left join
    {{ ref("int_powerschool__final_grades_pivot") }} as fg
    on enr.cc_studentid = fg.studentid
    and enr.cc_yearid = fg.yearid
    and enr.cc_course_number = fg.course_number
    and enr.term_name = fg.storecode
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="fg") }}
left join
    {{ ref("int_powerschool__category_grades_pivot") }} as cat
    on enr.cc_studentid = cat.studentid
    and enr.cc_course_number = cat.course_number
    and enr.term_name = cat.reporting_term
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="cat") }}
left join
    {{ ref("int_powerschool__category_grades_pivot") }} as kctz
    on fg.studentid = kctz.studentid
    and fg.storecode = kctz.reporting_term
    and {{ union_dataset_join_clause(left_alias="fg", right_alias="kctz") }}
    and kctz.course_number = 'HR'
    and left(enr.sections_section_number, 1) = '0'
left join
    {{ ref("stg_powerschool__pgfinalgrades") }} as comm
    on enr.cc_studentid = comm.studentid
    and enr.cc_sectionid = comm.sectionid
    and enr.term_name = comm.finalgradename
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="comm") }}
left join
    {{ ref("stg_powerschool__storedgrades") }} as sgy1
    on enr.cc_studentid = sgy1.studentid
    and enr.cc_academic_year = sgy1.academic_year
    and enr.cc_course_number = sgy1.course_number
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="sgy1") }}
    and enr.term_name = 'Q4'
    and sgy1.storecode = 'Y1'
where enr.cc_academic_year = {{ var("current_academic_year") }}
