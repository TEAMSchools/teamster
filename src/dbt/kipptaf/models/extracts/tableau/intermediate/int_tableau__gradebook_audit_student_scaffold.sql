with
    category_grades as (
        select
            _dbt_source_relation,
            studentid,
            sectionid,
            storecode,
            percent_grade as category_quarter_percent_grade,

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
    s.`ada`,
    s.ada_above_or_at_80,

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

    sec.teacher_tableau_username,
    sec.school_leader,
    sec.school_leader_tableau_username,
    sec.region_school_level,
    sec.quarter,
    sec.semester,
    sec.quarter_start_date,
    sec.quarter_end_date,
    sec.is_current_term,
    sec.is_quarter_end_date_range,
    sec.week_start_date,
    sec.week_end_date,
    sec.week_start_monday,
    sec.week_end_sunday,
    sec.school_week_start_date_lead,
    sec.week_number_academic_year,
    sec.week_number_quarter,
    sec.section_or_period,

    qg.term_percent_grade_adjusted as quarter_course_percent_grade,
    qg.term_grade_points as quarter_course_grade_points,
    qg.citizenship as quarter_citizenship,
    qg.comment_value as quarter_comment_value,

    'student_section_week_scaffold' as scaffold_name,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on s.studentid = ce.cc_studentid
    and s.yearid = ce.terms_yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
    and not ce.is_dropped_section
inner join
    {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
    on ce.cc_sectionid = sec.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
    and sec.scaffold_name = 'teacher_section_week_scaffold'
left join
    {{ ref("base_powerschool__final_grades") }} as qg
    on ce.cc_studentid = qg.studentid
    and ce.cc_sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
    and sec.quarter = qg.storecode
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
    and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.enroll_status = 0
    and not s.is_out_of_district

union all

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
    s.`ada`,
    s.ada_above_or_at_80,

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

    sec.teacher_tableau_username,
    sec.school_leader,
    sec.school_leader_tableau_username,
    sec.region_school_level,
    sec.quarter,
    sec.semester,
    sec.quarter_start_date,
    sec.quarter_end_date,
    sec.is_current_term,
    sec.is_quarter_end_date_range,
    sec.week_start_date,
    sec.week_end_date,
    sec.week_start_monday,
    sec.week_end_sunday,
    sec.school_week_start_date_lead,
    sec.week_number_academic_year,
    sec.week_number_quarter,
    sec.section_or_period,

    qg.term_percent_grade_adjusted as quarter_course_percent_grade,
    qg.term_grade_points as quarter_course_grade_points,
    qg.citizenship as quarter_citizenship,
    qg.comment_value as quarter_comment_value,

    'student_section_week_category_scaffold' as scaffold_name,

    ge.assignment_category_name,
    ge.assignment_category_code,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    cg.category_quarter_percent_grade,
    cg.category_quarter_average_all_courses,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on s.studentid = ce.cc_studentid
    and s.yearid = ce.terms_yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
    and not ce.is_dropped_section
inner join
    {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
    on ce.cc_sectionid = sec.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
    and sec.scaffold_name = 'teacher_section_week_category_scaffold'
inner join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on sec.region = ge.region
    and sec.school_level = ge.school_level
    and sec.academic_year = ge.academic_year
    and sec.quarter = ge.quarter
    and sec.week_number_quarter = ge.week_number
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
    on s.studentid = cg.studentid
    and ce.cc_sectionid = cg.sectionid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="cg") }}
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="cg") }}
    and ge.assignment_category_term = cg.storecode
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.enroll_status = 0
    and not s.is_out_of_district
