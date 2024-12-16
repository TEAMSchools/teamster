with
    roster_assignment_student as (
        select distinct
            r._dbt_source_relation,
            r.academic_year,
            r.academic_year_display,
            r.region,
            r.school_level,
            r.region_school_level,
            r.schoolid,
            r.school,

            r.studentid,
            r.student_number,
            r.student_name,
            r.grade_level,
            r.salesforce_id,
            r.ktc_cohort,
            r.enroll_status,
            r.cohort,
            r.gender,
            r.ethnicity,
            r.advisory,
            r.hos,
            r.year_in_school,
            r.year_in_network,
            r.rn_undergrad,
            r.is_out_of_district,
            r.is_pathways,
            r.is_retained_year,
            r.is_retained_ever,
            r.lunch_status,
            r.gifted_and_talented,
            r.iep_status,
            r.lep_status,
            r.is_504,
            r.is_counseling_services,
            r.is_student_athlete,
            r.tutoring_nj,
            r.nj_student_tier,
            r.ada,
            r.ada_above_or_at_80,
            r.date_enrolled,

            r.`quarter`,
            r.semester,
            r.week_number,
            r.quarter_start_date,
            r.quarter_end_date,
            r.cal_quarter_end_date,
            r.is_current_quarter,
            r.is_quarter_end_date_range,
            r.audit_due_date,

            r.assignment_category_name,
            r.assignment_category_code,
            r.assignment_category_term,
            r.expectation,
            r.notes,

            r.section_or_period,
            r.sectionid,
            r.sections_dcid,
            r.section_number,
            r.external_expression,
            r.credit_type,
            r.course_number,
            r.course_name,
            r.exclude_from_gpa,
            r.is_ap_course,

            r.teacher_number,
            r.teacher_name,
            r.tableau_username,

            r.category_quarter_percent_grade,
            r.category_quarter_average_all_courses,

            r.quarter_course_percent_grade_that_matters,
            r.quarter_course_grade_points_that_matters,
            r.quarter_citizenship,
            r.quarter_comment_value,

            f.audit_category,
            f.audit_flag_name,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as r
        left join
            {{ ref("stg_reporting__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and f.cte_grouping = 'assignment_student'
        where r.school_level != 'ES'
    )*/
select
    t.assignment_category_code,
    t.teacher_assign_id,
    t.teacher_assign_name,
    t.teacher_assign_due_date,
    t.teacher_assign_score_type,
    t.teacher_assign_max_score,
    t.n_students,
    t.n_late,
    t.n_exempt,
    t.n_missing,
    t.n_expected,
    t.n_expected_scored,
    t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

    a.student_number,
    a.raw_score,
    a.score_entered,
    a.assign_final_score_percent,
    a.is_exempt,
    a.is_late,
    a.is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from {{ ref("int_powerschool__teacher_assignment_audit_base") }} as t
inner join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on t.quarter = a.quarter
    and t.week_number_quarter = a.week_number
    and t.schoolid = a.schoolid
    and t.sectionid = a.sectionid
    and t.assignment_category_code = a.assignment_category_code
    and t.teacher_assign_id = a.teacher_assign_id
    and a.cte_grouping = 'assignment_student'
where t.school_level != 'ES'
