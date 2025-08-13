with
    student_roster as (
        select
            _dbt_source_relation,
            studentid,
            student_number,
            student_name as lastfirst,
            enroll_status,
            yearid,
            academic_year,
            region,
            school_level,
            reporting_schoolid as schoolid,
            school as school_abbreviation,
            grade_level,
            advisory_name as team,
            advisor_lastfirst as advisor_name,
            spedlep as iep_status,
            cohort,
            gender,
            year_in_school,
            is_tutoring as tutoring_nj,
            is_counseling_services as is_counselingservices,
            is_student_athlete as is_studentathlete,
            unweighted_ada as ada,
            hos,
        from {{ ref("int_extracts__student_enrollments") }}
        where rn_year = 1
    ),

    section_teacher as (
        select
            enr._dbt_source_relation,
            enr.cc_studentid as studentid,
            enr.cc_sectionid as sectionid,
            enr.cc_yearid as yearid,
            enr.cc_course_number as course_number,
            enr.sections_section_number as section_number,
            enr.sections_external_expression as external_expression,
            enr.sections_termid as termid,
            enr.courses_credittype as credittype,
            enr.courses_course_name as course_name,
            enr.teacher_lastfirst as teacher_name,

            f.nj_student_tier,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on enr.cc_studentid = f.studentid
            and enr.cc_academic_year = f.academic_year
            and enr.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="f") }}
            and f.rn_year = 1
        where enr.rn_course_number_year = 1 and not enr.is_dropped_section
    )

/* current year - term grades */
select
    co.student_number,
    co.lastfirst,
    co.schoolid,
    co.school_abbreviation,
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
    co.is_counselingservices,
    co.is_studentathlete,
    co.tutoring_nj,
    co.hos,
    co.ada,

    gr.course_number,
    gr.storecode as term_name,
    gr.storecode as finalgradename,
    gr.exclude_from_gpa as excludefromgpa,
    gr.potential_credit_hours as credit_hours,
    gr.term_percent_grade_adjusted as term_grade_percent_adjusted,
    gr.term_letter_grade_adjusted as term_grade_letter_adjusted,
    gr.term_grade_points as term_gpa_points,
    gr.y1_percent_grade_adjusted as y1_grade_percent_adjusted,
    gr.y1_letter_grade as y1_grade_letter,
    gr.y1_grade_points as y1_gpa_points,

    if(gr.termbin_is_current, 1, 0) as is_curterm,

    gr.credittype,
    gr.course_name,

    null as earnedcrhrs,

    nullif(pgf.citizenship, '') as citizenship,
    nullif(pgf.comment_value, '') as comment_value,

    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as `period`,
    st.external_expression,
    st.nj_student_tier,

    max(case when gr.termbin_is_current then gr.need_60 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_65,
    max(case when gr.termbin_is_current then gr.need_70 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_70,
    max(case when gr.termbin_is_current then gr.need_80 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_80,
    max(case when gr.termbin_is_current then gr.need_90 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_90,

from student_roster as co
left join
    {{ ref("base_powerschool__final_grades") }} as gr
    on co.studentid = gr.studentid
    and co.yearid = gr.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gr") }}
    and gr.termbin_start_date <= current_date('{{ var("local_timezone") }}')
left join
    {{ ref("stg_powerschool__pgfinalgrades") }} as pgf
    on gr.studentid = pgf.studentid
    and gr.sectionid = pgf.sectionid
    and gr.storecode = pgf.finalgradename
    and {{ union_dataset_join_clause(left_alias="gr", right_alias="pgf") }}
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
    and gr.course_number = st.course_number
where co.academic_year = {{ var("current_academic_year") }}

union all

/* current year - Y1 grades */
select
    co.student_number,
    co.lastfirst,
    co.schoolid,
    co.school_abbreviation,
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
    co.is_counselingservices,
    co.is_studentathlete,
    co.tutoring_nj,
    co.hos,
    co.ada,

    gr.course_number,

    'Y1' as term_name,
    'Y1' as finalgradename,

    gr.exclude_from_gpa as excludefromgpa,
    gr.potential_credit_hours as credit_hours,
    gr.y1_percent_grade_adjusted as term_grade_percent_adjusted,
    gr.y1_letter_grade as term_grade_letter_adjusted,
    gr.y1_grade_points as term_gpa_points,
    gr.y1_percent_grade_adjusted as y1_grade_percent_adjusted,
    gr.y1_letter_grade as y1_grade_letter,
    gr.y1_grade_points as y1_gpa_points,
    if(gr.termbin_is_current, 1, 0) as is_curterm,
    gr.credittype,
    gr.course_name,

    y1.earnedcrhrs,

    cast(null as string) as citizenship,
    cast(null as string) as comment_value,

    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as `period`,
    st.external_expression,
    st.nj_student_tier,

    max(case when gr.termbin_is_current then gr.need_60 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_65,
    max(case when gr.termbin_is_current then gr.need_70 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_70,
    max(case when gr.termbin_is_current then gr.need_80 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_80,
    max(case when gr.termbin_is_current then gr.need_90 end) over (
        partition by co.student_number, co.academic_year, gr.course_number
    ) as need_90,

from student_roster as co
left join
    {{ ref("base_powerschool__final_grades") }} as gr
    on co.studentid = gr.studentid
    and co.yearid = gr.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gr") }}
    and gr.termbin_is_current
    and gr.termbin_start_date <= current_date('{{ var("local_timezone") }}')
left join
    {{ ref("stg_powerschool__storedgrades") }} as y1
    on co.studentid = y1.studentid
    and co.academic_year = y1.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="y1") }}
    and gr.course_number = y1.course_number
    and y1.storecode = 'Y1'
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
    and gr.course_number = st.course_number
where co.academic_year = {{ var("current_academic_year") }}

union all

/* category grades - term */
select
    co.student_number,
    co.lastfirst,
    co.schoolid,
    co.school_abbreviation,
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
    co.is_counselingservices,
    co.is_studentathlete,
    co.tutoring_nj,
    co.hos,
    co.ada,

    cg.course_number,
    cg.storecode as term_name,
    cg.storecode_type as finalgradename,

    null as excludefromgpa,
    null as credit_hours,

    cg.percent_grade as term_grade_percent_adjusted,

    null as term_grade_letter_adjusted,
    null as term_gpa_points,

    cg.percent_grade_y1_running as y1_grade_percent_adjusted,

    null as y1_grade_letter,
    null as y1_gpa_points,

    if(
        current_date('{{ var("local_timezone") }}')
        between cg.termbin_start_date and cg.termbin_end_date,
        1,
        0
    ) as is_curterm,

    st.credittype,
    st.course_name,

    null as earnedcrhrs,
    null as citizenship,
    null as comment_value,

    st.sectionid,
    st.termid,
    st.teacher_name,
    st.section_number,
    st.section_number as `period`,
    st.external_expression,
    st.nj_student_tier,

    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90,

from student_roster as co
left join
    {{ ref("int_powerschool__category_grades") }} as cg
    on co.studentid = cg.studentid
    and co.yearid = cg.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cg") }}
    and cg.storecode_type != 'Q'
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
    and cg.course_number = st.course_number
where co.academic_year = {{ var("current_academic_year") }}

union all

/* category grades - year */
select
    co.student_number,
    co.lastfirst,
    co.schoolid,
    co.school_abbreviation,
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
    co.is_counselingservices,
    co.is_studentathlete,
    co.tutoring_nj,
    co.hos,
    co.ada,

    cy.course_number,

    'Y1' as term_name,

    concat(cy.storecode_type, 'Y1') as finalgradename,

    null as excludefromgpa,
    null as credit_hours,

    cy.percent_grade_y1_running as term_grade_percent_adjusted,

    null as term_grade_letter_adjusted,
    null as term_gpa_points,

    cy.percent_grade_y1_running as y1_grade_percent_adjusted,

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
    st.section_number as `period`,
    st.external_expression,
    st.nj_student_tier,

    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90,

from student_roster as co
left join
    {{ ref("int_powerschool__category_grades") }} as cy
    on co.studentid = cy.studentid
    and co.yearid = cy.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cy") }}
    and cy.storecode_type != 'Q'
    and current_date('{{ var("local_timezone") }}')
    between cy.termbin_start_date and cy.termbin_end_date
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
    and cy.course_number = st.course_number
where co.academic_year = {{ var("current_academic_year") }}

union all

/* historical grades */
select
    co.student_number,
    co.lastfirst,
    co.schoolid,
    co.school_abbreviation,
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
    co.is_counselingservices,
    co.is_studentathlete,
    co.tutoring_nj,
    co.hos,
    co.ada,

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
    st.section_number as `period`,
    st.external_expression,
    st.nj_student_tier,

    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90,
from student_roster as co
left join
    {{ ref("stg_powerschool__storedgrades") }} as sg
    on co.studentid = sg.studentid
    and co.academic_year = sg.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sg") }}
    and sg.storecode = 'Y1'
    and sg.course_number is not null
left join
    section_teacher as st
    on co.studentid = st.studentid
    and co.yearid = st.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="st") }}
    and sg.course_number = st.course_number
where co.academic_year < {{ var("current_academic_year") }}

union all

/* transfer grades */
select
    coalesce(co.student_number, e1.student_number) as student_number,
    coalesce(co.lastfirst, e1.lastfirst) as lastfirst,
    coalesce(co.schoolid, e1.schoolid) as schoolid,
    coalesce(co.school_abbreviation, e1.school_abbreviation) as school_abbreviation,
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
    coalesce(co.is_counselingservices, 0) as is_counselingservices,
    coalesce(co.is_studentathlete, 0) as is_studentathlete,

    null as tutoring_nj,

    coalesce(co.hos, e1.hos) as hos,
    coalesce(co.ada, e1.ada) as ada,

    concat(
        'T', upper(regexp_extract(tr._dbt_source_relation, r'(kipp\w+)_')), tr.dcid
    ) as course_number,

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
    null as `period`,
    null as external_expression,
    null as nj_student_tier,
    null as need_65,
    null as need_70,
    null as need_80,
    null as need_90,
from {{ ref("stg_powerschool__storedgrades") }} as tr
left join
    student_roster as co
    on tr.studentid = co.studentid
    and tr.schoolid = co.schoolid
    and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
    and tr.academic_year = co.academic_year
left join
    student_roster as e1
    on tr.studentid = e1.studentid
    and tr.schoolid = e1.schoolid
    and {{ union_dataset_join_clause(left_alias="tr", right_alias="e1") }}
    and e1.year_in_school = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on co.studentid = sp.studentid
    and current_date('{{ var("local_timezone") }}')
    between sp.enter_date and sp.exit_date
    and sp.specprog_name = 'Counseling Services'
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
left join
    {{ ref("int_powerschool__spenrollments") }} as sa
    on co.studentid = sa.studentid
    and current_date('{{ var("local_timezone") }}')
    between sa.enter_date and sa.exit_date
    and sa.specprog_name = 'Student Athlete'
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sa") }}
where tr.storecode = 'Y1' and tr.course_number is null
