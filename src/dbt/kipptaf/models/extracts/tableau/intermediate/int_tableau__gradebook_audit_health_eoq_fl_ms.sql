{{- config(materialized="table") -}}

with
    quarter_grades as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            course_number,
            sectionid,
            termid,
            storecode,
            term_percent_grade_adjusted as quarter_course_percent_grade_that_matters,
            term_grade_points as quarter_course_grade_points_that_matters,
            citizenship as quarter_citizenship,
            comment_value as quarter_comment_value,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
            and regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippmiami'
            and schoolid = 30200803
    ),

    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,

            concat('Q', storecode_order) as term,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,
        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid = {{ var("current_academic_year") - 1990 }}
            and not is_dropped_section
            and storecode_type in ('W', 'F', 'S')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
            and regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippmiami'
            and schoolid = 30200803
    )

-- student + course + category: w_grade_inflation and qt_effort_grade_missing
select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
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
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.cal_quarter_end_date,
    s.is_current_quarter,
    s.is_quarter_end_date_range,

    s.sectionid,
    s.sections_dcid,
    s.section_number,
    s.external_expression,
    s.date_enrolled,
    s.credit_type,
    s.course_number,
    s.course_name,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.tutoring_nj,
    s.nj_student_tier,
    s.is_ap_course,
    s.tableau_username,

    qg.quarter_course_percent_grade_that_matters,
    qg.quarter_course_grade_points_that_matters,
    qg.quarter_citizenship,
    qg.quarter_comment_value,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_quarter_average_all_courses,

    if(
        c.category_name_code = 'W'
        and abs(
            round(c.category_quarter_average_all_courses, 2)
            - round(c.category_quarter_percent_grade, 2)
        )
        >= 30,
        true,
        false
    ) as w_grade_inflation,

    if(
        c.category_name_code = 'W'
        and c.category_quarter_percent_grade is null
        and s.is_quarter_end_date_range,
        true,
        false
    ) as qt_effort_grade_missing,

    false as qt_percent_grade_greater_100,

    false as qt_student_is_ada_80_plus_gpa_less_2,

    false as qt_grade_70_comment_missing,

    false as qt_g1_g8_conduct_code_missing,

    false as qt_g1_g8_conduct_code_incorrect,

from {{ ref("int_tableau__gradebook_audit_roster") }} as s
left join
    quarter_grades as qg
    on s.studentid = qg.studentid
    and s.quarter = qg.storecode
    and s.sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qg") }}
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.quarter = c.term
    and s.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
where s.region = 'Miami' and s.school_level = 'MS' and c.category_name_code = 'W'

union all

-- student + course: qt_percent_grade_greater_100,
-- qt_student_is_ada_80_plus_gpa_less_2, qt_grade_70_comment_missing,
-- qt_g1_g8_conduct_code_missing,,qt_g1_g8_conduct_code_incorrect
select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
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
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.cal_quarter_end_date,
    s.is_current_quarter,
    s.is_quarter_end_date_range,

    s.sectionid,
    s.sections_dcid,
    s.section_number,
    s.external_expression,
    s.date_enrolled,
    s.credit_type,
    s.course_number,
    s.course_name,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.tutoring_nj,
    s.nj_student_tier,
    s.is_ap_course,
    s.tableau_username,

    qg.quarter_course_percent_grade_that_matters,
    qg.quarter_course_grade_points_that_matters,
    qg.quarter_citizenship,
    qg.quarter_comment_value,

    '' as category_name_code,
    '' as category_quarter_code,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    false as w_grade_inflation,
    false as qt_effort_grade_missing,

    if(
        qg.quarter_course_percent_grade_that_matters > 100, true, false
    ) as qt_percent_grade_greater_100,

    if(
        s.ada_above_or_at_80 and qg.quarter_course_grade_points_that_matters < 2.0,
        true,
        false
    ) as qt_student_is_ada_80_plus_gpa_less_2,

    if(
        s.is_quarter_end_date_range
        and qg.quarter_course_percent_grade_that_matters < 70
        and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_grade_70_comment_missing,

    if(
        s.is_quarter_end_date_range
        and s.course_name != 'HR'
        and qg.quarter_citizenship is null,
        true,
        false
    ) as qt_g1_g8_conduct_code_missing,

    if(
        s.is_quarter_end_date_range
        and s.course_name != 'HR'
        and qg.quarter_citizenship is not null
        and qg.quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
        true,
        false
    ) as qt_g1_g8_conduct_code_incorrect,

from {{ ref("int_tableau__gradebook_audit_roster") }} as s
left join
    quarter_grades as qg
    on s.studentid = qg.studentid
    and s.quarter = qg.storecode
    and s.sectionid = qg.sectionid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qg") }}
where s.region = 'Miami' and s.school_level = 'MS'
