with
    category_grades as (
        select
            _dbt_source_relation,
            yearid,
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
            -- change 1991 to 1990 when ready
            yearid = {{ var("current_academic_year") - 1991 }}
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    ),

    quarter_course_grades as (
        select
            _dbt_source_relation,
            academic_year,
            yearid,
            studentid,
            sectionid,
            storecode,
            termbin_start_date,
            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_grade_points as quarter_course_grade_points,
            citizenship as quarter_conduct,
            comment_value as quarter_comment_value,

            'current_year' as grades_type,

        from {{ ref("base_powerschool__final_grades") }}

        union all

        select
            _dbt_source_relation,
            academic_year,
            yearid,
            studentid,
            sectionid,
            storecode,
            null as termbin_start_date,
            `percent` as quarter_course_percent_grade,
            gpa_points as quarter_course_grade_points,
            behavior as quarter_conduct,
            comment_value as quarter_comment_value,

            'last_year' as grades_type,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }}
            and storecode_type = 'Q'
            and not is_transfer_grade
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
    sec.is_current_week,
    sec.section_or_period,

    qg.quarter_course_percent_grade,
    qg.quarter_course_grade_points,
    qg.quarter_conduct,
    qg.quarter_comment_value,

    'student_scaffold' as scaffold_name,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    -- gpa and ada tag
    if(
        s.school_level != 'ES'
        and s.ada_above_or_at_80
        and qg.quarter_course_grade_points < 2.0,
        true,
        false
    ) as qt_student_is_ada_80_plus_gpa_less_2,

    -- quarter course grade above 100
    if(
        qg.quarter_course_percent_grade > 100, true, false
    ) as qt_percent_grade_greater_100,

    -- course comments
    if(
        s.school_level != 'ES'
        and sec.is_quarter_end_date_range
        and qg.quarter_course_percent_grade < 70
        and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_grade_70_comment_missing,

    if(
        sec.region_school_level = 'MiamiES'
        and sec.is_quarter_end_date_range
        and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_comment_missing,

    if(
        sec.region_school_level in ('CamdenES', 'NewarkES')
        and sec.is_quarter_end_date_range
        and ce.courses_credittype in ('HR', 'MATH', 'ENG', 'RHET')
        and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_es_comment_missing,

    -- conduct codes
    if(
        s.region = 'Miami'
        and s.grade_level != 0
        and sec.is_quarter_end_date_range
        and ce.courses_course_name != 'HR'
        and qg.quarter_conduct is null,
        true,
        false
    ) as qt_g1_g8_conduct_code_missing,

    if(
        s.region = 'Miami'
        and s.grade_level != 0
        and sec.is_quarter_end_date_range
        and ce.courses_course_name != 'HR'
        and qg.quarter_conduct not in ('A', 'B', 'C', 'D', 'E', 'F'),
        true,
        false
    ) as qt_g1_g8_conduct_code_incorrect,

    if(
        sec.region_school_level = 'MiamiES'
        and s.grade_level = 0
        and sec.is_quarter_end_date_range
        and ce.courses_course_name = 'HR'
        and qg.quarter_conduct is null,
        true,
        false
    ) as qt_kg_conduct_code_missing,

    if(
        sec.region_school_level = 'MiamiES'
        and s.grade_level = 0
        and sec.is_quarter_end_date_range
        and ce.courses_course_name = 'HR'
        and qg.quarter_conduct not in ('E', 'G', 'S', 'M'),
        true,
        false
    ) as qt_kg_conduct_code_incorrect,

    if(
        sec.region_school_level = 'MiamiES'
        and s.grade_level = 0
        and sec.is_quarter_end_date_range
        and ce.courses_course_name != 'HR'
        and qg.quarter_conduct is not null,
        true,
        false
    ) as qt_kg_conduct_code_not_hr,

    null as w_grade_inflation,
    null as qt_effort_grade_missing,
    null as qt_formative_grade_missing,
    null as qt_summative_grade_missing,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on s.studentid = ce.cc_studentid
    and s.yearid = ce.terms_yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
    and not ce.is_dropped_section
inner join
    {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
    on ce.terms_yearid = sec.yearid
    and ce.cc_sectionid = sec.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
    and sec.scaffold_name = 'teacher_scaffold'
left join
    quarter_course_grades as qg
    on ce.terms_yearid = qg.yearid
    and ce.cc_studentid = qg.studentid
    and ce.cc_sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
    and sec.quarter = qg.storecode
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
    -- and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
    and qg.grades_type = 'last_year'
where
    s.academic_year = {{ var("current_academic_year") - 1 }}
    and s.rn_year = 1
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
    sec.is_current_week,
    sec.section_or_period,

    qg.quarter_course_percent_grade,
    qg.quarter_course_grade_points,
    qg.quarter_conduct,
    qg.quarter_comment_value,

    'student_category_scaffold' as scaffold_name,

    ge.assignment_category_name,
    ge.assignment_category_code,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    cg.category_quarter_percent_grade,
    cg.category_quarter_average_all_courses,

    null as qt_student_is_ada_80_plus_gpa_less_2,
    null as qt_percent_grade_greater_100,
    null as qt_grade_70_comment_missing,
    null as qt_comment_missing,
    null as qt_es_comment_missing,
    null as qt_g1_g8_conduct_code_missing,
    null as qt_g1_g8_conduct_code_incorrect,
    null as qt_kg_conduct_code_missing,
    null as qt_kg_conduct_code_incorrect,
    null as qt_kg_conduct_code_not_hr,

    if(
        ge.assignment_category_code = 'W'
        and s.school_level != 'ES'
        and abs(
            round(cg.category_quarter_average_all_courses, 2)
            - round(cg.category_quarter_percent_grade, 2)
        )
        >= 30,
        true,
        false
    ) as w_grade_inflation,

    if(
        s.region = 'Miami'
        and ge.assignment_category_code = 'W'
        and cg.category_quarter_percent_grade is null
        and sec.is_quarter_end_date_range,
        true,
        false
    ) as qt_effort_grade_missing,

    if(
        s.region_school_level = 'MiamiES'
        and ge.assignment_category_code = 'F'
        and cg.category_quarter_percent_grade is null
        and sec.is_quarter_end_date_range,
        true,
        false
    ) as qt_formative_grade_missing,

    if(
        s.region_school_level = 'MiamiES'
        and sec.credit_type not in ('ENG', 'MATH')
        and ge.assignment_category_code = 'S'
        and cg.category_quarter_percent_grade is null
        and sec.is_quarter_end_date_range,
        true,
        false
    ) as qt_summative_grade_missing,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on s.studentid = ce.cc_studentid
    and s.yearid = ce.terms_yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
    and not ce.is_dropped_section
inner join
    {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as sec
    on ce.terms_yearid = sec.yearid
    and ce.cc_sectionid = sec.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="sec") }}
    and sec.scaffold_name = 'teacher_category_scaffold'
inner join
    {{ ref("stg_google_sheets__gradebook_expectations_assignments") }} as ge
    on sec.region = ge.region
    and sec.school_level = ge.school_level
    and sec.academic_year = ge.academic_year
    and sec.quarter = ge.quarter
    and sec.week_number_quarter = ge.week_number
    and sec.assignment_category_code = ge.assignment_category_code
left join
    quarter_course_grades as qg
    on ce.terms_yearid = qg.yearid
    and ce.cc_studentid = qg.studentid
    and ce.cc_sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
    and sec.quarter = qg.storecode
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="qg") }}
    -- and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
    and qg.grades_type = 'last_year'
left join
    category_grades as cg
    on ce.terms_yearid = cg.yearid
    and ce.cc_studentid = cg.studentid
    and ce.cc_sectionid = cg.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="cg") }}
    and ge.assignment_category_term = cg.storecode
where
    s.academic_year = {{ var("current_academic_year") - 1 }}
    and s.rn_year = 1
    and s.enroll_status = 0
    and not s.is_out_of_district
