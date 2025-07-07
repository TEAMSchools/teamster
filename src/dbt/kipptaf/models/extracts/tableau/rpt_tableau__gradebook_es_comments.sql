with
    teacher_aggs as (
        select
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,
            `quarter`,
            semester,
            week_number_quarter as audit_qt_week_number,
            quarter_start_date,
            quarter_end_date,
            is_current_term as is_current_quarter,
            is_quarter_end_date_range,
            week_start_monday as audit_start_date,
            week_end_sunday as audit_end_date,
            school_week_start_date_lead as audit_due_date,
            assignment_category_name,
            assignment_category_code,
            assignment_category_term,
            expectation,
            notes,
            section_or_period,
            sectionid,
            sections_dcid,
            section_number,
            external_expression,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,
            is_ap_course,
            teacher_number,
            teacher_name,
            teacher_tableau_username,
            school_leader,
            school_leader_tableau_username,
            assignmentid as teacher_assign_id,
            assignment_name as teacher_assign_name,
            duedate as teacher_assign_due_date,
            scoretype as teacher_assign_score_type,
            totalpointvalue as teacher_assign_max_score,
            n_students,
            n_late,
            n_exempt,
            n_missing,
            n_null,
            n_is_null_missing,
            n_is_null_not_missing,
            n_expected,
            n_expected_scored,
            total_expected_scored_section_quarter_week_category,
            total_expected_section_quarter_week_category,
            percent_graded_for_quarter_week_class,
            sum_totalpointvalue_section_quarter_category,
            teacher_running_total_assign_by_cat,
            teacher_avg_score_for_assign_per_class_section_and_assign_id,
            audit_category,
            cte_grouping,
            code_type,
            audit_flag_name,

            max(audit_flag_value) as audit_flag_value,
        from {{ ref("int_tableau__gradebook_audit_flags") }}
        where audit_category = 'Comments'
        group by all
    ),

    valid_flags as (
        select
            academic_year,
            region,
            schoolid,
            `quarter`,
            week_number_quarter as audit_qt_week_number,
            assignment_category_term,
            sectionid,
            teacher_number,
            assignmentid as teacher_assign_id,
            studentid,
            student_number,
            student_name,
            grade_level,
            salesforce_id,
            ktc_cohort,
            enroll_status,
            cohort,
            gender,
            ethnicity,
            advisory,
            year_in_school,
            year_in_network,
            rn_undergrad,
            is_out_of_district,
            is_retained_year,
            is_retained_ever,
            lunch_status,
            gifted_and_talented,
            iep_status,
            lep_status,
            is_504,
            is_counseling_services,
            is_student_athlete,
            ada,
            ada_above_or_at_80,
            date_enrolled,
            category_quarter_percent_grade,
            category_quarter_average_all_courses,
            quarter_course_percent_grade,
            quarter_course_grade_points,
            quarter_citizenship,
            quarter_comment_value,
            scorepoints as raw_score,
            score_entered,
            assign_final_score_percent,
            is_exempt,
            is_late,
            is_missing,
            audit_category,
            cte_grouping,
            code_type,
            audit_flag_name,
            audit_flag_value as flag_value,
        from {{ ref("int_tableau__gradebook_audit_flags") }}
        where audit_category = 'Comments'
    )

select
    t.*,

    v.studentid,
    v.student_number,
    v.student_name,
    v.grade_level,
    v.salesforce_id,
    v.ktc_cohort,
    v.enroll_status,
    v.cohort,
    v.gender,
    v.ethnicity,
    v.advisory,
    v.year_in_school,
    v.year_in_network,
    v.rn_undergrad,
    v.is_out_of_district,
    v.is_retained_year,
    v.is_retained_ever,
    v.lunch_status,
    v.gifted_and_talented,
    v.iep_status,
    v.lep_status,
    v.is_504,
    v.is_counseling_services,
    v.is_student_athlete,
    v.ada,
    v.ada_above_or_at_80,
    v.date_enrolled,
    v.category_quarter_average_all_courses,
    v.quarter_course_percent_grade,
    v.quarter_course_grade_points,
    v.quarter_citizenship,
    v.quarter_comment_value,
    v.raw_score,
    v.score_entered,
    v.assign_final_score_percent,
    v.is_exempt,
    v.is_late,
    v.is_missing,

    e.category_quarter_percent_grade as effort_grade,

    coalesce(v.flag_value, 0) as flag_value,
from teacher_aggs as t
inner join
    valid_flags as v
    on t.academic_year = v.academic_year
    and t.region = v.region
    and t.schoolid = v.schoolid
    and t.quarter = v.quarter
    and t.audit_qt_week_number = v.audit_qt_week_number
    and t.sectionid = v.sectionid
    and t.teacher_number = v.teacher_number
    and t.audit_category = v.audit_category
    and t.cte_grouping = v.cte_grouping
    and t.audit_flag_name = v.audit_flag_name
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as e
    on v.academic_year = e.academic_year
    and v.region = e.region
    and v.schoolid = e.schoolid
    and v.quarter = e.quarter
    and v.audit_qt_week_number = e.week_number_quarter
    and v.sectionid = e.sectionid
    and v.student_number = e.student_number
    and e.audit_category = 'Effort Grade'
where
    t.code_type = 'Quarter'
    and t.audit_category = 'Comments'
    and t.audit_start_date <= current_date('{{ var("local_timezone") }}')
