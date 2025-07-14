{{ config(materialized="table", cluster_by="cte_grouping") }}

with
    student_unpivot as (
        select u.*, 'assignment_student' as cte_grouping,

        from
            {{ ref("int_tableau__gradebook_audit_assignments_student") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    assign_null_score,
                    assign_score_above_max,
                    assign_exempt_with_score,
                    assign_w_score_less_5,
                    assign_f_score_less_5,
                    assign_w_missing_score_not_5,
                    assign_f_missing_score_not_5,
                    assign_h_missing_score_not_5,
                    assign_w_missing_score_not_0,
                    assign_f_missing_score_not_0,
                    assign_h_missing_score_not_0,
                    assign_s_score_less_50p,
                    assign_s_ms_score_not_conversion_chart_options,
                    assign_s_hs_score_not_conversion_chart_options
                )
            ) as u
        /* these exceptions exist here because if they are placed upstream on
        int_tableau__gradebook_audit_assignments_student, then we will be
        incorrectly omitting flags for effort grade, conduct code, grade > 100, and
        summative or formative grades missing for COCUR, RHET, SCI, and SOC */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on u.academic_year = e1.academic_year
            and u.region = e1.region
            and u.school_level = e1.school_level
            and u.credit_type = e1.credit_type
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'student_unpivot'
            and e1.is_quarter_end_date_range is null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on u.academic_year = e2.academic_year
            and u.region = e2.region
            and u.course_number = e2.course_number
            and u.is_quarter_end_date_range = e2.is_quarter_end_date_range
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'student_unpivot'
            and e2.is_quarter_end_date_range is not null
        where e1.`include` is null and e2.`include` is null
    ),

    teacher_unpivot_cca as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    w_assign_max_score_not_10,
                    h_assign_max_score_not_10,
                    f_assign_max_score_not_10,
                    s_max_score_greater_100
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'class_category_assignment'
        /* these exceptions exist here because if they are placed upstream on
        int_tableau__gradebook_audit_assignments_teacher, then we will be
        incorrectly omitting flags for effort grade, conduct code, grade > 100, and
        summative or formative grades missing for COCUR, RHET, SCI, and SOC */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on r.academic_year = e.academic_year
            and r.region = e.region
            and r.school_level = e.school_level
            and r.credit_type = e.credit_type
            and e.view_name = 'int_tableau__gradebook_audit_flags'
            and e.cte = 'teacher_unpivot_cca'
        where e.`include` is null
    ),

    teacher_unpivot_cc as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_categories_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_teacher_s_total_greater_200,
                    qt_teacher_s_total_less_200,
                    qt_teacher_s_total_greater_100,
                    qt_teacher_s_total_less_100,
                    w_expected_assign_count_not_met,
                    h_expected_assign_count_not_met,
                    f_expected_assign_count_not_met,
                    s_expected_assign_count_not_met,
                    w_percent_graded_min_not_met,
                    h_percent_graded_min_not_met,
                    f_percent_graded_min_not_met,
                    s_percent_graded_min_not_met
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'class_category'
    ),

    eoq_items as (
        select  -- All but Conduct Code
            r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_student_scaffold") }}
            unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_comment_missing,
                    qt_es_comment_missing,
                    qt_grade_70_comment_missing,
                    qt_g1_g8_conduct_code_missing,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_percent_grade_greater_100,
                    qt_student_is_ada_80_plus_gpa_less_2
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping in ('student_course', 'student')
            and f.audit_category != 'Conduct Code'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'eoq_items'
            and e1.audit_flag_name = 'qt_comment_missing'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.school_level = e2.school_level
            and r.credit_type = e2.credit_type
            and r.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'eoq_items'
            and e2.audit_flag_name
            in ('qt_g1_g8_conduct_code_missing', 'qt_g1_g8_conduct_code_incorrect')
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e3
            on r.academic_year = e3.academic_year
            and r.region = e3.region
            and r.course_number = e3.course_number
            and r.audit_flag_name = e3.audit_flag_name
            and e3.view_name = 'int_tableau__gradebook_audit_flags'
            and e3.cte = 'eoq_items'
            and e3.course_number is not null
        where e1.`include` is null and e2.`include` is null and e3.`include` is null
    ),

    eoq_items_conduct_code as (
        select  -- Conduct Code for ES (requires grade level join)
            r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_student_scaffold") }}
            unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_kg_conduct_code_not_hr,
                    qt_g1_g8_conduct_code_missing,
                    qt_g1_g8_conduct_code_incorrect
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.grade_level = f.grade_level
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'student_course'
            and f.audit_category = 'Conduct Code'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'eoq_items_conduct_code'
            and e1.credit_type is not null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.course_number = e2.course_number
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'eoq_items_conduct_code'
            and e2.credit_type is null
        where r.school_level = 'ES' and e1.`include` is null and e2.`include` is null
    ),

    /* w_grade_inflation, qt_effort_grade_missing, qt_formative_grade_missing,
    qt_summative_grade_missing */
    student_course_category as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_student_category_scaffold"
                )
            }}
            unpivot (
                audit_flag_value for audit_flag_name in (qt_effort_grade_missing)
            ) as r

        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and r.assignment_category_code = 'W'
            and f.cte_grouping = 'student_course_category'

        union all

        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_student_category_scaffold"
                )
            }}
            unpivot (audit_flag_value for audit_flag_name in (w_grade_inflation)) as r

        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and r.assignment_category_code = 'W'
            and f.cte_grouping = 'student_course_category'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'student_course_category'
            and e1.credit_type is not null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.course_number = e2.course_number
            and r.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'student_course_category'
            and e2.credit_type is null
        where e1.`include` is null and e2.`include` is null

        union all

        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_student_category_scaffold"
                )
            }}
            unpivot (
                audit_flag_value for audit_flag_name in (qt_formative_grade_missing)
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and r.assignment_category_code = 'F'
            and f.cte_grouping = 'student_course_category'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'student_course_category'
            and e1.credit_type is not null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.course_number = e2.course_number
            and r.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'student_course_category'
            and e2.credit_type is null
        where e1.`include` is null and e2.`include` is null

        union all

        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_student_category_scaffold"
                )
            }}
            unpivot (
                audit_flag_value for audit_flag_name in (qt_summative_grade_missing)
            ) as r

        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.quarter = f.code
            and r.audit_flag_name = f.audit_flag_name
            and r.assignment_category_code = 'S'
            and f.cte_grouping = 'student_course_category'
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and r.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'int_tableau__gradebook_audit_flags'
            and e1.cte = 'student_course_category'
            and e1.credit_type is not null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.course_number = e2.course_number
            and r.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'int_tableau__gradebook_audit_flags'
            and e2.cte = 'student_course_category'
            and e2.credit_type is null
        where e1.`include` is null and e2.`include` is null
    )

-- this captures all flags from assignment_student
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
    r.week_number_academic_year,
    r.week_number_quarter,
    r.quarter_course_percent_grade,
    r.quarter_course_grade_points,
    r.quarter_citizenship,
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
    r.category_name,
    r.scorepoints,
    r.actualscoreentered,
    r.is_late,
    r.is_exempt,
    r.is_missing,
    r.is_zero,
    r.score_entered,
    r.assign_final_score_percent,
    r.assign_expected_to_be_scored,
    r.assign_scored,
    r.assign_expected_with_score,

    r.cte_grouping,
    r.audit_flag_name,

    t.n_students,
    t.n_late,
    t.n_exempt,
    t.n_missing,
    t.n_null,
    t.n_is_null_missing,
    t.n_is_null_not_missing,
    t.n_expected,
    t.n_expected_scored,
    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    t.sum_totalpointvalue_section_quarter_category,
    t.running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,
    t.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,
    f.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between r.week_start_monday and r.week_end_sunday,
        true,
        false
    ) as is_current_week,

from student_unpivot as r
inner join
    {{ ref("stg_google_sheets__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping = 'assignment_student'
left join
    {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} as t
    on r.region = t.region
    and r.schoolid = t.schoolid
    and r.quarter = t.quarter
    and r.week_number_quarter = t.week_number_quarter
    and r.sectionid = t.sectionid
    and r.assignmentid = t.assignmentid

union all
/* this captures all student_course_category: qt_effort_grade_missing,
qt_formative_grade_missing, qt_summative_grade_missing, and
w_grade_inflation */
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
    quarter,
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
    week_number_academic_year,
    week_number_quarter,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_citizenship,
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
    null as category_name,
    null as scorepoints,
    null as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as is_zero,
    null as score_entered,
    null as assign_final_score_percent,
    null as assign_expected_to_be_scored,
    null as assign_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    null as um_totalpointvalue_section_quarter_category,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between week_start_monday and week_end_sunday,
        true,
        false
    ) as is_current_week,

from student_course_category

union all
-- this captures all eoq items except conduct_code
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
    quarter,
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
    week_number_academic_year,
    week_number_quarter,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_citizenship,
    quarter_comment_value,
    section_or_period,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,
    null as category_name,
    null as scorepoints,
    null as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as is_zero,
    null as score_entered,
    null as assign_final_score_percent,
    null as assign_expected_to_be_scored,
    null as assign_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    null as sum_totalpointvalue_section_quarter_category,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between week_start_monday and week_end_sunday,
        true,
        false
    ) as is_current_week,

from eoq_items

union all
-- this captures conduct_code
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
    quarter,
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
    week_number_academic_year,
    week_number_quarter,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_citizenship,
    quarter_comment_value,
    section_or_period,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,
    null as category_name,
    null as scorepoints,
    null as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as is_zero,
    null as score_entered,
    null as assign_final_score_percent,
    null as assign_expected_to_be_scored,
    null as assign_scored,
    null as assign_expected_with_score,

    cte_grouping,
    audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    null as sum_totalpointvalue_section_quarter_category,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between week_start_monday and week_end_sunday,
        true,
        false
    ) as is_current_week,

from eoq_items_conduct_code

union all
-- this captures 'class_category_assignment': f_assign_max_score_not_10,
-- w_assign_max_score_not_10, s_max_score_greater_100
select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,

    null as students_dcid,
    null as studentid,
    null as student_number,
    null as student_name,
    null as grade_level,
    null as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    null as gender,
    null as ethnicity,
    null as advisory,

    r.hos,
    r.region_school_level,

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
    null as ada,
    null as ada_above_or_at_80,

    r.sectionid,
    r.course_number,

    null as date_enrolled,

    r.sections_dcid,
    r.section_number,
    r.external_expression,

    null as termid,

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
    r.week_number_academic_year,
    r.week_number_quarter,

    null as quarter_course_percent_grade,
    null as quarter_course_grade_points,
    null as quarter_citizenship,
    null as quarter_comment_value,

    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,

    null as category_name,
    null as scorepoints,
    null as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as is_zero,
    null as score_entered,
    null as assign_final_score_percent,
    null as assign_expected_to_be_scored,
    null as assign_scored,
    null as assign_expected_with_score,

    r.cte_grouping,
    r.audit_flag_name,

    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_null,
    r.n_is_null_missing,
    r.n_is_null_not_missing,
    r.n_expected,
    r.n_expected_scored,
    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    null as sum_totalpointvalue_section_quarter_category,
    null as teacher_running_total_assign_by_cat,
    r.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between r.week_start_monday and r.week_end_sunday,
        true,
        false
    ) as is_current_week,

from teacher_unpivot_cca as r

union all
-- this captures 'class_category'
select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,

    null as students_dcid,
    null as studentid,
    null as student_number,
    null as student_name,
    null as grade_level,
    null as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    null as gender,
    null as ethnicity,
    null as advisory,

    r.hos,
    r.region_school_level,

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
    null as ada,
    null as ada_above_or_at_80,

    r.sectionid,
    r.course_number,

    null as date_enrolled,

    r.sections_dcid,
    r.section_number,
    r.external_expression,

    null as termid,

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
    r.week_number_academic_year,
    r.week_number_quarter,

    null as quarter_course_percent_grade,
    null as quarter_course_grade_points,
    null as quarter_citizenship,
    null as quarter_comment_value,

    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,
    null as category_name,
    null as scorepoints,
    null as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as is_zero,
    null as score_entered,
    null as assign_final_score_percent,
    null as assign_expected_to_be_scored,
    null as assign_scored,
    null as assign_expected_with_score,

    r.cte_grouping,
    r.audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,
    r.total_expected_scored_section_quarter_week_category,
    r.total_expected_section_quarter_week_category,
    r.percent_graded_for_quarter_week_class,
    r.sum_totalpointvalue_section_quarter_category,

    r.running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,

    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

    if(
        current_date('{{ var("local_timezone") }}')
        between r.week_start_monday and r.week_end_sunday,
        true,
        false
    ) as is_current_week,

from teacher_unpivot_cc as r
