with
    quarter_course_grades as (
        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            termbin_start_date,
            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_grade_points as quarter_course_grade_points,
            comment_value as quarter_comment_value,

            'current_year' as grades_type,

        from {{ ref("base_powerschool__final_grades") }}

        union all

        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            null as termbin_start_date,
            `percent` as quarter_course_percent_grade,
            gpa_points as quarter_course_grade_points,
            comment_value as quarter_comment_value,

            'last_year' as grades_type,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }}
            and storecode_type = 'Q'
            and not is_transfer_grade
    )

-- student_course flags: qt_grade_70_comment_missing and qt_percent_grade_greater_100
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.school_level_alt as school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.dateenrolled,
    s.dateleft,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
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

    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.section_or_period,
    s.teacher_number,
    s.teacher_name,
    s.school_leader,
    s.manager_employee_number,
    s.manager_name,
    s.hos,

    s.teacher_tableau_username,
    s.manager_tableau_username,
    s.school_leader_tableau_username,

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    -- these values will be null
    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,
    null as week_end_sunday,

    qg.quarter_course_percent_grade,
    qg.quarter_course_grade_points,
    qg.quarter_comment_value,

    null as category_quarter_percent_grade,

    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,

    null as scorepoints,
    null as is_expected_late,
    null as is_exempt,
    null as is_expected_missing,
    null as is_expected_zero,
    null as is_expected_academic_dishonesty,
    null as score_entered,
    null as assign_final_score_percent,

    false as assign_null_score,
    false as assign_score_above_max,
    false as assign_w_score_less_5,
    false as assign_h_score_less_5,
    false as assign_f_score_less_5,
    false as assign_w_missing_score_not_5,
    false as assign_f_missing_score_not_5,
    false as assign_h_missing_score_not_5,
    false as assign_w_missing_score_not_0,
    false as assign_f_missing_score_not_0,
    false as assign_h_missing_score_not_0,
    false as assign_s_missing_score_not_0,
    false as assign_s_score_less_50p,
    false as assign_s_hs_score_less_50p,

    false as assign_max_score_not_10,

    if(
        qg.quarter_course_percent_grade > 100, true, false
    ) as qt_percent_grade_greater_100,

    if(
        qg.quarter_course_percent_grade < 70 and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_grade_70_comment_missing,

    false as percent_graded_min_not_met,

    null as teacher_running_total_assign_by_cat,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
left join
    quarter_course_grades as qg
    on s.academic_year = qg.academic_year
    and s.studentid = qg.studentid
    and s.sectionid = qg.sectionid
    and s._dbt_source_project = qg._dbt_source_project
    and s.quarter = qg.storecode
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
    and qg.grades_type = 'current_year'  /* summer toggle: see skill */
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.rn_year = 1
    and s.enroll_status = 0
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and not s.is_out_of_district

union all

/* assignment_student flags: assign_null_score,assign_score_above_max,
   assign_w_score_less_5,assign_h_score_less_5,assign_f_score_less_5,
   assign_w_missing_score_not_5,assign_f_missing_score_not_5
   assign_h_missing_score_not_5,assign_w_missing_score_not_0,
   assign_f_missing_score_not_0,assign_h_missing_score_not_0,
   assign_s_missing_score_not_0,assign_s_score_less_50p,
   assign_s_hs_score_less_50p */
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.school_level_alt as school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.dateenrolled,
    s.dateleft,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
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

    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.section_or_period,
    s.teacher_number,
    s.teacher_name,
    s.school_leader,
    s.manager_employee_number,
    s.manager_name,
    s.hos,

    s.teacher_tableau_username,
    s.manager_tableau_username,
    s.school_leader_tableau_username,

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,
    ge.week_end_sunday,

    qg.quarter_course_percent_grade,
    qg.quarter_course_grade_points,
    qg.quarter_comment_value,

    cg.percent_grade as category_quarter_percent_grade,

    a.assignmentid,
    a.assignment_name,
    a.duedate,
    a.scoretype,
    a.totalpointvalue,

    a.scorepoints,
    a.is_expected_late,
    a.is_exempt,
    a.is_expected_missing,
    a.is_expected_zero,
    a.is_expected_academic_dishonesty,
    a.score_entered,
    a.assign_final_score_percent,

    a.assign_null_score,
    a.assign_score_above_max,
    a.assign_w_score_less_5,
    a.assign_h_score_less_5,
    a.assign_f_score_less_5,
    a.assign_w_missing_score_not_5,
    a.assign_f_missing_score_not_5,
    a.assign_h_missing_score_not_5,
    a.assign_w_missing_score_not_0,
    a.assign_f_missing_score_not_0,
    a.assign_h_missing_score_not_0,
    a.assign_s_missing_score_not_0,
    a.assign_s_score_less_50p,
    a.assign_s_hs_score_less_50p,

    false as assign_max_score_not_10,

    false as qt_percent_grade_greater_100,
    false as qt_grade_70_comment_missing,

    false as percent_graded_min_not_met,

    null as teacher_running_total_assign_by_cat,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
left join
    quarter_course_grades as qg
    on s.academic_year = qg.academic_year
    and s.studentid = qg.studentid
    and s.sectionid = qg.sectionid
    and s._dbt_source_project = qg._dbt_source_project
    and s.quarter = qg.storecode
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
    and qg.grades_type = 'current_year'  /* summer toggle: see skill */
left join
    {{ ref("int_powerschool__category_grades") }} as cg
    on s.academic_year = cg.academic_year
    and s.studentid = cg.studentid
    and s.sectionid = cg.sectionid
    and s._dbt_source_project = cg._dbt_source_project
    and s.quarter = cg.storecode
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
left join
    {{ ref("int_powerschool__gradebook_assignments_scores") }} as a
    on s.sections_dcid = a.sectionsdcid
    and s.students_dcid = a.students_dcid
    and s.assignment_category_code = a.category_code
    and a.duedate between s.quarter_start_date and s.quarter_end_date
    and s.dateenrolled <= a.duedate
    and s._dbt_source_project = a._dbt_source_project
    and a.iscountedinfinalgrade = 1
    and a.scoretype in ('POINTS', 'PERCENT')
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.rn_year = 1
    and s.enroll_status = 0
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and not s.is_out_of_district

union all

/* assignment_teacher flags: assign_max_score_not_10, percent_graded_min_not_met,
   expected_assign_count_not_met */
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.school_level_alt as school_level,
    s.region,
    s.schoolid,
    s.school,

    null as students_dcid,
    null as studentid,
    null as student_number,
    null as student_name,
    null as grade_level,
    null as dateenrolled,
    null as dateleft,
    null as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    null as gender,
    null as ethnicity,
    null as advisory,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    null as is_out_of_district,
    null as is_self_contained,
    null as is_retained_year,
    null as is_retained_ever,
    null as lunch_status,
    null as gifted_and_talented,
    null as iep_status,
    null as lep_status,
    null as is_504,
    null as is_counseling_services,
    null as is_student_athlete,
    null as `ada`,
    null as ada_above_or_at_80,

    s.course_number,
    s.course_name,
    s.credit_type,
    s.exclude_from_gpa,
    s.sections_dcid,
    s.sectionid,
    s.section_number,
    s.external_expression,
    s.section_or_period,
    s.teacher_number,
    s.teacher_name,
    s.school_leader,
    s.manager_employee_number,
    s.manager_name,
    s.hos,

    s.teacher_tableau_username,
    s.manager_tableau_username,
    s.school_leader_tableau_username,

    s.quarter,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,
    ge.week_end_sunday,

    null as quarter_course_percent_grade,
    null as quarter_course_grade_points,
    null as quarter_comment_value,

    null as category_quarter_percent_grade,

    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,

    null as scorepoints,
    null as is_expected_late,
    null as is_exempt,
    null as is_expected_missing,
    null as is_expected_zero,
    null as is_expected_academic_dishonesty,
    null as score_entered,
    null as assign_final_score_percent,

    false as assign_null_score,
    false as assign_score_above_max,
    false as assign_w_score_less_5,
    false as assign_h_score_less_5,
    false as assign_f_score_less_5,
    false as assign_w_missing_score_not_5,
    false as assign_f_missing_score_not_5,
    false as assign_h_missing_score_not_5,
    false as assign_w_missing_score_not_0,
    false as assign_f_missing_score_not_0,
    false as assign_h_missing_score_not_0,
    false as assign_s_missing_score_not_0,
    false as assign_s_score_less_50p,
    false as assign_s_hs_score_less_50p,

    r.assign_max_score_not_10,

    false as qt_percent_grade_greater_100,
    false as qt_grade_70_comment_missing,

    if(r.assign_percent_graded < 0.90, true, false) as percent_graded_min_not_met,

    countif(r.duedate <= ge.week_end_sunday) over (
        partition by s._dbt_source_project, s.sectionid, s.assignment_category_term
    ) as teacher_running_total_assign_by_cat,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
left join
    {{ ref("int_powerschool__gradebook_assignment_score_rollup") }} as r
    on s._dbt_source_project = r._dbt_source_project
    and s.sections_dcid = r.sectionsdcid
    and s.assignment_category_code = r.category_code
    and r.duedate between s.quarter_start_date and s.quarter_end_date
    and r.scoretype in ('POINTS', 'PERCENT')
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
