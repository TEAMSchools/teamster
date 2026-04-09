with
    student_unpivoted as (
        select *,
        from
            {{ ref("int_tableau__gradebook_audit_assignments_student") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    assign_null_score,
                    assign_score_above_max,
                    assign_w_score_less_5,
                    assign_h_score_less_5,
                    assign_f_score_less_5,
                    assign_w_missing_score_not_5,
                    assign_f_missing_score_not_5,
                    assign_h_missing_score_not_5,
                    assign_w_missing_score_not_0,
                    assign_f_missing_score_not_0,
                    assign_h_missing_score_not_0,
                    assign_s_missing_score_not_0,
                    assign_s_score_less_50p,
                    assign_s_hs_score_less_50p,
                    assign_s_ms_score_not_conversion_chart_options,
                    assign_s_hs_score_not_conversion_chart_options
                )
            )
    ),

    student_unpivot as (
        select u.*, f.cte_grouping, f.audit_category, f.code_type,
        from student_unpivoted as u
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on u.academic_year = f.academic_year
            and u.region = f.region
            and u.school_level = f.school_level
            and u.assignment_category_code = f.code
            and u.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'assignment_student'
        -- temporarily remove flags during non-eoq times
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on u.academic_year = e1.academic_year
            and u.region = e1.region
            and u.course_number = e1.course_number
            and u.audit_flag_name = e1.audit_flag_name
            and u.is_quarter_end_date_range = e1.is_quarter_end_date_range
            and e1.view_name = 'audit_flags'
            and e1.cte = 'student_unpivot'
            and e1.is_quarter_end_date_range is not null
        -- temporarily remove flags during non-eoq times
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on u.academic_year = e2.academic_year
            and u.region = e2.region
            and u.course_number = e2.course_number
            and u.assignment_category_code = e2.gradebook_category
            and u.audit_flag_name = e2.audit_flag_name
            and u.is_quarter_end_date_range = e2.is_quarter_end_date_range
            and e2.view_name = 'audit_flags'
            and e2.cte = 'student_unpivot'
            and e2.is_quarter_end_date_range is not null
        -- permanently remove flags by credit type and gradebook category
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e3
            on u.academic_year = e3.academic_year
            and u.region = e3.region
            and u.school_level = e3.school_level
            and u.credit_type = e3.credit_type
            and u.assignment_category_code = e3.gradebook_category
            and e3.view_name = 'audit_flags'
            and e3.cte = 'student_unpivot'
            and e3.is_quarter_end_date_range is null
        where
            e1.include_row is null and e2.include_row is null and e3.include_row is null
    ),

    eoq_items_unpivoted as (
        select *,
        from
            {{ ref("int_tableau__gradebook_audit_student_scaffold") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_comment_missing,
                    qt_es_comment_missing,
                    qt_grade_70_comment_missing,
                    qt_g1_g8_conduct_code_missing,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_percent_grade_greater_100,
                    qt_student_is_ada_80_plus_gpa_less_2
                )
            )
    ),

    eoq_items as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,
        from eoq_items_unpivoted as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.academic_year = f.academic_year
            and r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and r.scaffold_name = 'student_scaffold'
            and f.cte_grouping in ('student_course', 'student')
            and f.audit_category != 'Conduct Code'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'audit_flags'
            and e1.cte = 'eoq_items'
            and e1.credit_type is not null
        where e1.include_row is null
    ),

    eoq_items_conduct_code_unpivoted as (
        select *,
        from
            {{ ref("int_tableau__gradebook_audit_student_scaffold") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_kg_conduct_code_not_hr,
                    qt_g1_g8_conduct_code_missing,
                    qt_g1_g8_conduct_code_incorrect
                )
            )
    ),

    -- Conduct Code for ES (requires grade level join)
    eoq_items_conduct_code as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,
        from eoq_items_conduct_code_unpivoted as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.academic_year = f.academic_year
            and r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.grade_level = f.grade_level
            and r.audit_flag_name = f.audit_flag_name
            and r.scaffold_name = 'student_scaffold'
            and f.cte_grouping = 'student_course'
            and f.audit_category = 'Conduct Code'
        -- permanently remove flags by credit type
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'audit_flags'
            and e1.cte = 'eoq_items_conduct_code'
            and e1.credit_type is not null
        -- permanently remove flags by course number
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.school_level = e2.school_level
            and r.course_number = e2.course_number
            and r.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'audit_flags'
            and e2.cte = 'eoq_items_conduct_code'
            and e2.credit_type is null
        where
            r.school_level = 'ES' and e1.include_row is null and e2.include_row is null
    ),

    student_course_category_unpivoted as (
        select *,
        from
            {{ ref("int_tableau__gradebook_audit_student_scaffold") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_effort_grade_missing,
                    w_grade_inflation,
                    qt_formative_grade_missing,
                    qt_summative_grade_missing
                )
            )
    ),

    student_course_category as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,
        from student_course_category_unpivoted as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.academic_year = f.academic_year
            and r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.assignment_category_code = f.alt_code
            and r.audit_flag_name = f.audit_flag_name
            and r.scaffold_name = 'student_category_scaffold'
            and f.cte_grouping = 'student_course_category'
        -- temporarily remove flags
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on r.academic_year = e.academic_year
            and r.region = e.region
            and r.course_number = e.course_number
            and r.audit_flag_name = e.audit_flag_name
            and r.is_quarter_end_date_range = e.is_quarter_end_date_range
            and e.view_name = 'audit_flags'
            and e.cte = 'student_course_category'
            and e.is_quarter_end_date_range is not null
        where e.include_row is null
    )

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    r.students_dcid,
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
    r.region_school_level,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_self_contained,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.ada,
    r.ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    r.date_enrolled,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,
    r.is_ap_course,
    r.teacher_tableau_username,
    r.school_leader,
    r.school_leader_tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.quarter_end_date_insession,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.is_current_week,
    r.quarter_course_percent_grade,
    r.quarter_course_grade_points,
    r.quarter_conduct,
    r.quarter_comment_value,
    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,
    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,
    r.scorepoints,
    r.is_expected_late,
    r.is_exempt,
    r.is_expected_missing,
    r.is_expected_zero,
    r.is_expected_academic_dishonesty,
    r.score_entered,
    r.assign_final_score_percent,
    r.assign_expected_to_be_scored,
    r.assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    t.n_students,
    t.n_late,
    t.n_exempt,
    t.n_missing,
    t.n_academic_dishonesty,
    t.n_null,
    t.n_is_null_missing,
    t.n_is_null_not_missing,
    t.n_expected,
    t.n_expected_scored,

    t.sum_totalpointvalue_section_quarter_category,
    t.teacher_running_total_assign_by_cat,
    t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from student_unpivot as r
left join
    {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} as t
    on r.region = t.region
    and r.schoolid = t.schoolid
    and r.quarter = t.quarter
    and r.week_number_quarter = t.week_number_quarter
    and r.sectionid = t.sectionid
    and r.assignmentid = t.assignmentid

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    yearid,
    region,
    school_level,
    schoolid,
    school,
    students_dcid,
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
    hos,
    region_school_level,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_out_of_district,
    is_self_contained,
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
    sectionid,
    course_number,
    date_enrolled,
    sections_dcid,
    section_number,
    external_expression,
    termid,
    credit_type,
    course_name,
    exclude_from_gpa,
    teacher_number,
    teacher_name,
    is_ap_course,
    teacher_tableau_username,
    school_leader,
    school_leader_tableau_username,
    `quarter`,
    semester,
    quarter_start_date,
    quarter_end_date,
    is_current_term,
    is_quarter_end_date_range,
    week_start_date,
    week_end_date,
    week_start_monday,
    week_end_sunday,
    school_week_start_date_lead,
    quarter_end_date_insession,
    week_number_academic_year,
    week_number_quarter,
    is_current_week,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    section_or_period,
    assignment_category_name,
    assignment_category_code,
    assignment_category_term,
    expectation,
    notes,
    category_quarter_percent_grade,
    category_quarter_average_all_courses,

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
    null as assign_expected_to_be_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_academic_dishonesty,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as sum_totalpointvalue_section_quarter_category,
    cast(null as float64) as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_course_category

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    yearid,
    region,
    school_level,
    schoolid,
    school,
    students_dcid,
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
    hos,
    region_school_level,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_out_of_district,
    is_self_contained,
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
    sectionid,
    course_number,
    date_enrolled,
    sections_dcid,
    section_number,
    external_expression,
    termid,
    credit_type,
    course_name,
    exclude_from_gpa,
    teacher_number,
    teacher_name,
    is_ap_course,
    teacher_tableau_username,
    school_leader,
    school_leader_tableau_username,
    `quarter`,
    semester,
    quarter_start_date,
    quarter_end_date,
    is_current_term,
    is_quarter_end_date_range,
    week_start_date,
    week_end_date,
    week_start_monday,
    week_end_sunday,
    school_week_start_date_lead,
    quarter_end_date_insession,
    week_number_academic_year,
    week_number_quarter,
    is_current_week,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    section_or_period,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    cast(null as float64) as expectation,
    null as notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
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
    null as assign_expected_to_be_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_academic_dishonesty,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as sum_totalpointvalue_section_quarter_category,
    cast(null as float64) as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    yearid,
    region,
    school_level,
    schoolid,
    school,
    students_dcid,
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
    hos,
    region_school_level,
    year_in_school,
    year_in_network,
    rn_undergrad,
    is_out_of_district,
    is_self_contained,
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
    sectionid,
    course_number,
    date_enrolled,
    sections_dcid,
    section_number,
    external_expression,

    null as termid,

    credit_type,
    course_name,
    exclude_from_gpa,
    teacher_number,
    teacher_name,
    is_ap_course,
    teacher_tableau_username,
    school_leader,
    school_leader_tableau_username,
    `quarter`,
    semester,
    quarter_start_date,
    quarter_end_date,
    is_current_term,
    is_quarter_end_date_range,
    week_start_date,
    week_end_date,
    week_start_monday,
    week_end_sunday,
    school_week_start_date_lead,
    quarter_end_date_insession,
    week_number_academic_year,
    week_number_quarter,
    is_current_week,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    section_or_period,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    cast(null as float64) as expectation,
    null as notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
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
    null as assign_expected_to_be_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_academic_dishonesty,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as sum_totalpointvalue_section_quarter_category,
    cast(null as float64) as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items_conduct_code
