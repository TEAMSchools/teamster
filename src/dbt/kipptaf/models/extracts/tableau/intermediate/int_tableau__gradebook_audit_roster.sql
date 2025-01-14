{{- config(materialized="table") -}}

with
    course_enrollments as (
        select
            m._dbt_source_relation,
            m.cc_studentid as studentid,
            m.cc_yearid as yearid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.cc_dateenrolled as date_enrolled,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.sections_termid as termid,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,
            m.is_ap_course,

            r.sam_account_name as tableau_username,

            f.nj_student_tier,

            concat(m.cc_schoolid, m.cc_course_number) as schoolid_course_number,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("base_people__staff_roster") }} as r
            on m.teachernumber = r.powerschool_teacher_number
        left join
            {{ ref("int_extracts__student_filters") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
        where
            not m.is_dropped_section
            and m.cc_course_number not in (
                'LOG20',  -- Early Dismissal
                'LOG300',  -- Study Hall
                'SEM22101G1',  -- Student Government
                'SEM22106G1',  -- Advisory
                'SEM22106S1',  -- Not in SY24-25 yet
                /* Lunch */
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG22999XL',
                'LOG9'
            )
    ),

    terms as (
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,

            tb.storecode as `quarter`,
            tb.date1 as quarter_start_date,
            tb.date2 as quarter_end_date,
            tb.is_current_term as is_current_quarter,
            tb.is_quarter_end_date_range,
            tb.semester,
        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.schoolid = tb.schoolid
            and t.id = tb.termid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and tb.date1 <= current_date('{{ var("local_timezone") }}')
        where t.yearid = {{ var("current_academic_year") - 1990 }} and t.isyearrec = 1
    ),

    category_grades as (
        select
            _dbt_source_relation,
            studentid,
            sectionid,
            storecode,
            percent_grade,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, studentid, yearid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,
        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid = {{ var("current_academic_year") - 1990 }}
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.yearid,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.region_school_level,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_self_contained,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.is_tutoring,
    s.ada,
    s.ada_above_or_at_80,

    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,
    ce.nj_student_tier,
    ce.is_ap_course,
    ce.tableau_username,
    ce.schoolid_course_number,

    t.quarter,
    t.semester,
    t.quarter_start_date,
    t.quarter_end_date,
    t.is_current_quarter,
    t.is_quarter_end_date_range,

    ge.week_number,
    ge.assignment_category_name,
    ge.assignment_category_code,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    w.week_start_date,
    w.week_end_date,
    w.week_start_monday,
    w.week_end_sunday,
    w.school_week_start_date_lead,
    w.week_number_academic_year,
    w.week_number_quarter,

    qg.term_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
    qg.term_grade_points as quarter_course_grade_points_that_matters,
    qg.citizenship as quarter_citizenship,
    qg.comment_value as quarter_comment_value,

    cg.percent_grade as category_quarter_percent_grade,
    cg.category_quarter_average_all_courses,

    concat(
        ce.course_number, ge.assignment_category_code
    ) as course_number_assignment_category_code,

    if(
        s.grade_level <= 8, ce.section_number, ce.external_expression
    ) as section_or_period,
from {{ ref("int_tableau__student_enrollments") }} as s
inner join
    course_enrollments as ce
    on s.studentid = ce.studentid
    and s.yearid = ce.yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
inner join
    terms as t
    on s.yearid = t.yearid
    and s.schoolid = t.schoolid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
left join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on s.region = ge.region
    and s.school_level = ge.school_level
    and s.academic_year = ge.academic_year
    and t.quarter = ge.quarter
left join
    {{ ref("int_powerschool__calendar_week") }} as w
    on s.academic_year = w.academic_year
    and s.school_level = w.school_level
    and s.schoolid = w.schoolid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="w") }}
    and ge.quarter = w.quarter
    and ge.week_number = w.week_number_quarter
left join
    {{ ref("base_powerschool__final_grades") }} as qg
    on s.studentid = qg.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qg") }}
    and ce.sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
    and t.quarter = qg.storecode
    and {{ union_dataset_join_clause(left_alias="t", right_alias="qg") }}
    and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
left join
    category_grades as cg
    on s.studentid = cg.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="cg") }}
    and ce.sectionid = cg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="cg") }}
    and ge.assignment_category_term = cg.storecode
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.enroll_status = 0
    and not s.is_out_of_district
