{{ config(enabled=False) }}
with
    section_teacher as (
        select
            scaff.studentid,
            scaff.yearid,
            scaff.course_number,
            scaff.sectionid,
            scaff.db_name,
            sec.credittype,
            sec.course_name,
            sec.section_number,
            sec.external_expression,
            sec.termid,
            sec.teacher_lastfirst as teacher_name
        from powerschool.course_section_scaffold as scaff
        left join
            powerschool.sections_identifiers as sec
            on (scaff.sectionid = sec.sectionid and scaff.db_name = sec.db_name)
        where scaff.is_curterm = 1
    ),

    final_grades as (
        select
            fg.studentid,
            fg.yearid,
            fg.db_name,
            fg.course_number,
            fg.sectionid,
            fg.storecode,
            fg.exclude_from_gpa,
            fg.potential_credit_hours,
            fg.term_grade_percent_adj,
            fg.term_grade_letter_adj,
            fg.term_grade_pts,
            fg.y1_grade_percent_adj,
            fg.y1_grade_letter,
            fg.y1_grade_pts,
            fg.need_60,
            fg.need_70,
            fg.need_80,
            fg.need_90,
            case
                when
                    (
                        cast(current_timestamp as date)
                        between fg.termbin_start_date and fg.termbin_end_date
                    )
                then 1
                else 0
            end as is_curterm,
            cou.credittype,
            cou.course_name
        from powerschool.final_grades_static as fg
        inner join
            powerschool.courses as cou
            on (fg.course_number = cou.course_number and fg.db_name = cou.db_name)
        where fg.termbin_start_date <= current_timestamp
    )

/* current year - term grades */
select
    co.student_number,
    co.lastfirst,
    co.reporting_schoolid as schoolid,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.enroll_status,
    co.academic_year,
    co.iep_status,
    co.cohort,
    co.region,
    co.gender,
    co.school_level,

    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,

    gr.course_number,
    gr.storecode as term_name,
    gr.storecode as finalgradename,
    gr.exclude_from_gpa as excludefromgpa,
    gr.potential_credit_hours as credit_hours,
    gr.term_grade_percent_adj as term_grade_percent_adjusted,
    gr.term_grade_letter_adj as term_grade_letter_adjusted,
    gr.term_grade_pts as term_gpa_points,
    gr.y1_grade_percent_adj as y1_grade_percent_adjusted,
    gr.y1_grade_letter,
    gr.y1_grade_pts as y1_gpa_points,
    gr.is_curterm,
    gr.credittype,
    gr.course_name,

    null as earnedcrhrs,

    case when pgf.citizenship != '' then pgf.citizenship end as citizenship,
    case when pgf.comment_value != '' then pgf.comment_value end as comment_value,

    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as period,
    st.external_expression,

    max(case when gr.is_curterm = 1 then gr.need_60 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_65,
    max(case when gr.is_curterm = 1 then gr.need_70 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_70,
    max(case when gr.is_curterm = 1 then gr.need_80 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_80,
    max(case when gr.is_curterm = 1 then gr.need_90 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_90,
from powerschool.cohort_identifiers_static as co
left join
    final_grades as gr
    on co.studentid = gr.studentid
    and co.yearid = gr.yearid
    and co.db_name = gr.db_name
left join
    powerschool.pgfinalgrades as pgf
    on gr.studentid = pgf.studentid
    and gr.sectionid = pgf.sectionid
    and gr.storecode = pgf.finalgradename
    and gr.db_name = pgf.db_name
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and co.db_name = st.db_name
    and gr.course_number = st.course_number
where
    co.rn_year = 1
    and co.grade_level != 99
    and co.academic_year = utilities.global_academic_year()

union all

/* current year - Y1 grades */
select
    co.student_number,
    co.lastfirst,
    co.reporting_schoolid as schoolid,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.enroll_status,
    co.academic_year,
    co.iep_status,
    co.cohort,
    co.region,
    co.gender,
    co.school_level,
    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,
    gr.course_number,
    'Y1' as term_name,
    'Y1' as finalgradename,
    gr.exclude_from_gpa as excludefromgpa,
    gr.potential_credit_hours as credit_hours,
    gr.y1_grade_percent_adj as term_grade_percent_adjusted,
    gr.y1_grade_letter as term_grade_letter_adjusted,
    gr.y1_grade_pts as term_gpa_points,
    gr.y1_grade_percent_adj as y1_grade_percent_adjusted,
    gr.y1_grade_letter,
    gr.y1_grade_pts as y1_gpa_points,
    gr.is_curterm,
    gr.credittype,
    gr.course_name,
    y1.earnedcrhrs,
    null as citizenship,
    null as comment_value,
    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as period,
    st.external_expression,
    max(case when gr.is_curterm = 1 then gr.need_60 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_65,
    max(case when gr.is_curterm = 1 then gr.need_70 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_70,
    max(case when gr.is_curterm = 1 then gr.need_80 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_80,
    max(case when gr.is_curterm = 1 then gr.need_90 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_90
from powerschool.cohort_identifiers_static as co
left join
    final_grades as gr
    on (
        co.studentid = gr.studentid
        and co.yearid = gr.yearid
        and co.db_name = gr.db_name
        and gr.is_curterm = 1
    )
left join
    powerschool.storedgrades as y1
    on co.studentid = y1.studentid
    and co.academic_year = y1.academic_year
    and co.db_name = y1.db_name
    and gr.course_number = y1.course_number
    and y1.storecode = 'Y1'
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and co.db_name = st.db_name
    and gr.course_number = st.course_number
where
    co.rn_year = 1
    and co.grade_level != 99
    and co.academic_year = utilities.global_academic_year()

union all

/* category grades - term */
select
    co.student_number,
    co.lastfirst,
    co.reporting_schoolid as schoolid,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.enroll_status,
    co.academic_year,
    co.iep_status,
    co.cohort,
    co.region,
    co.gender,
    co.school_level,
    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,
    cg.course_number,
    replace(cg.reporting_term, 'RT', 'Q') as term_name,
    cg.storecode_type as finalgradename,
    null as excludefromgpa,
    null as credit_hours,
    cg.category_pct as term_grade_percent_adjusted,
    null as term_grade_letter_adjusted,
    null as term_gpa_points,
    cg.category_pct_y1 as y1_grade_percent_adjusted,
    null as y1_grade_letter,
    null as y1_gpa_points,
    case
        when
            cast(current_timestamp as date)
            between cg.termbin_start_date and cg.termbin_end_date
        then 1
        else 0
    end as is_curterm,
    st.credittype,
    st.course_name,
    null as earnedcrhrs,
    null as citizenship,
    null as comment_value,
    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as period,
    st.external_expression,
    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90
from powerschool.cohort_identifiers_static as co
left join
    powerschool.category_grades_static as cg
    on (
        co.studentid = cg.studentid
        and co.yearid = cg.yearid
        and co.db_name = cg.db_name
        and cg.storecode_type != 'Q'
    )
left join
    section_teacher as st
    on (
        co.studentid = st.studentid
        and co.yearid = st.yearid
        and co.db_name = st.db_name
        and cg.course_number = st.course_number
    )
where
    co.rn_year = 1
    and co.grade_level != 99
    and co.academic_year = utilities.global_academic_year()

union all

/* category grades - year */
select
    co.student_number,
    co.lastfirst,
    co.reporting_schoolid as schoolid,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.enroll_status,
    co.academic_year,
    co.iep_status,
    co.cohort,
    co.region,
    co.gender,
    co.school_level,
    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,
    cy.course_number,
    'Y1' as term_name,
    concat(cy.storecode_type, 'Y1') as finalgradename,
    null as excludefromgpa,
    null as credit_hours,
    cy.category_pct_y1 as term_grade_percent_adjusted,
    null as term_grade_letter_adjusted,
    null as term_gpa_points,
    cy.category_pct_y1 as y1_grade_percent_adjusted,
    null as y1_grade_letter,
    null as y1_gpa_points,
    1 as is_curterm,
    st.credittype,
    st.course_name,
    null as earnedcrhrs,
    null as citizenship,
    null as comment_value,
    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as period,
    st.external_expression,
    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90
from powerschool.cohort_identifiers_static as co
left join
    powerschool.category_grades_static as cy
    on (
        co.studentid = cy.studentid
        and co.yearid = cy.yearid
        and co.db_name = cy.db_name
        and cy.storecode_type != 'Q'
        and (
            cast(current_timestamp as date)
            between cy.termbin_start_date and cy.termbin_end_date
        )
    )
left join
    section_teacher as st
    on (
        co.studentid = st.studentid
        and co.yearid = st.yearid
        and co.db_name = st.db_name
        and cy.course_number = st.course_number
    )
where
    co.rn_year = 1
    and co.grade_level != 99
    and co.academic_year = utilities.global_academic_year()

union all

/* historical grades */
select
    co.student_number,
    co.lastfirst,
    co.reporting_schoolid as schoolid,
    co.grade_level,
    co.team,
    co.advisor_name,
    co.enroll_status,
    co.academic_year,
    co.iep_status,
    co.cohort,
    co.region,
    co.gender,
    co.school_level,
    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,
    sg.course_number,
    'Y1' as term_name,
    'Y1' as finalgradename,
    sg.excludefromgpa,
    sg.potentialcrhrs as credit_hours,
    sg.percent as term_grade_percent_adjusted,
    sg.grade as term_grade_letter_adjusted,
    sg.gpa_points as term_gpa_points,
    sg.percent as y1_grade_percent_adjusted,
    sg.grade as y1_grade_letter,
    sg.gpa_points as y1_gpa_points,
    1 as is_curterm,
    sg.credit_type as credittype,
    sg.course_name,
    sg.earnedcrhrs,
    null as citizenship,
    null as comment_value,
    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as period,
    st.external_expression,
    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90
from powerschool.cohort_identifiers_static as co
left join
    powerschool.storedgrades as sg
    on (
        co.studentid = sg.studentid
        and co.academic_year = sg.academic_year
        and co.db_name = sg.db_name
        and sg.storecode = 'Y1'
        and sg.course_number is not null
    )
left join
    section_teacher as st
    on (
        co.studentid = st.studentid
        and co.yearid = st.yearid
        and co.db_name = st.db_name
        and sg.course_number = st.course_number
    )
where co.rn_year = 1 and co.academic_year != utilities.global_academic_year()

union all

/* transfer grades */
select
    coalesce(co.student_number, e1.student_number) as student_number,
    coalesce(co.lastfirst, e1.lastfirst) as lastfirst,
    coalesce(co.schoolid, e1.schoolid) as schoolid,
    coalesce(co.grade_level, e1.grade_level) as grade_level,
    coalesce(co.team, e1.team) as team,
    null as advisor_name,
    coalesce(co.enroll_status, e1.enroll_status) as enroll_status,
    tr.academic_year,
    coalesce(co.iep_status, e1.iep_status) as iep_status,
    coalesce(co.cohort, e1.cohort) as cohort,
    coalesce(co.region, e1.region) as region,
    coalesce(co.gender, e1.gender) as gender,
    coalesce(co.school_level, e1.school_level) as school_level,
    case when sp.studentid is not null then 1 end as is_counselingservices,
    case when sa.studentid is not null then 1 end as is_studentathlete,
    concat('TRANSFER', tr.termid, tr.db_name, tr.dcid) as course_number,
    'Y1' as term_name,
    'Y1' as finalgradename,
    tr.excludefromgpa,
    tr.potentialcrhrs as credit_hours,
    tr.percent as term_grade_percent_adjusted,
    tr.grade as term_grade_letter_adjusted,
    tr.gpa_points as term_gpa_points,
    tr.percent as y1_grade_percent_adjusted,
    tr.grade as y1_grade_letter,
    tr.gpa_points as y1_gpa_points,
    1 as is_curterm,
    'TRANSFER' as credittype,
    tr.course_name,
    tr.earnedcrhrs,
    null as citizenship,
    null as comment_value,
    tr.sectionid,
    tr.termid,
    'TRANSFER' as teacher_name,
    'TRANSFER' as section_number,
    null as period,
    null as external_expression,
    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90
from powerschool.storedgrades as tr
left join
    powerschool.cohort_identifiers_static as co
    on (
        tr.studentid = co.studentid
        and tr.schoolid = co.schoolid
        and tr.db_name = co.db_name
        and tr.academic_year = co.academic_year
        and co.rn_year = 1
    )
left join
    powerschool.cohort_identifiers_static as e1
    on (
        tr.studentid = e1.studentid
        and tr.schoolid = e1.schoolid
        and tr.db_name = e1.db_name
        and e1.year_in_school = 1
    )
where tr.storecode = 'Y1' and tr.course_number is null
