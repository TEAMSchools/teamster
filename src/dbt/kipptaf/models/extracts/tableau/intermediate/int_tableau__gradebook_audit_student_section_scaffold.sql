{{- config(materialized="table") -}}

with
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
    s.nj_student_tier,

    ce.cc_sectionid as sectionid,
    ce.cc_course_number as course_number,
    ce.cc_dateenrolled as date_enrolled,
    ce.sections_dcid,
    ce.sections_section_number as section_number,
    ce.sections_external_expression as external_expression,
    ce.sections_termid as termid,
    ce.courses_credittype as credit_type,
    ce.courses_course_name as course_name,
    ce.courses_excludefromgpa as exclude_from_gpa,
    ce.teachernumber as teacher_number,
    ce.teacher_lastfirst as teacher_name,
    ce.is_ap_course,

    sec.tableau_username,
    sec.quarter,
    sec.semester,
    sec.quarter_start_date,
    sec.quarter_end_date,
    sec.is_current_term,
    sec.is_quarter_end_date_range,
    sec.assignment_category_name,
    sec.assignment_category_code,
    sec.assignment_category_term,
    sec.expectation,
    sec.notes,
    sec.week_start_date,
    sec.week_end_date,
    sec.week_start_monday,
    sec.week_end_sunday,
    sec.school_week_start_date_lead,
    sec.week_number_academic_year,
    sec.week_number_quarter,

    qg.term_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
    qg.term_grade_points as quarter_course_grade_points_that_matters,
    qg.citizenship as quarter_citizenship,
    qg.comment_value as quarter_comment_value,

    cg.percent_grade as category_quarter_percent_grade,
    cg.category_quarter_average_all_courses,

    if(
        s.grade_level <= 8, ce.sections_section_number, ce.sections_external_expression
    ) as section_or_period,
from {{ ref("int_extracts__student_enrollments_subjects") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on s.studentid = ce.cc_studentid
    and s.yearid = ce.terms_yearid
    and s.powerschool_credittype = ce.courses_credittype
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
    and not ce.is_dropped_section
left join
    {{ ref("int_tableau__gradebook_audit_section_scaffold") }} as sec
    on ce.cc_sectionid = sec.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
left join
    {{ ref("base_powerschool__final_grades") }} as qg
    on ce.cc_studentid = qg.studentid
    and ce.cc_sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
    and sec.quarter = qg.storecode
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
    and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
left join
    category_grades as cg
    on ce.cc_studentid = cg.studentid
    and ce.cc_sectionid = cg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="cg") }}
    and sec.assignment_category_term = cg.storecode
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="cg") }}
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.enroll_status = 0
    and not s.is_out_of_district
