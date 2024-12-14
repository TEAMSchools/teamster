select
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
    r.section_or_period,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

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
    f.cte_grouping,

from {{ ref("int_tableau__gradebook_audit_roster") }} as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
where r.school_level != 'ES' and f.cte_grouping = 'assignment_student'
