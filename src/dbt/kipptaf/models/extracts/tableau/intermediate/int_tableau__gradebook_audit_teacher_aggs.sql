with
    /* Branch 1: Aggregate 16 student assignment flags to teacher×assignment grain */
    student_assignment_rollup as (
        select
            _dbt_source_relation,
            sectionid,
            assignmentid,

            logical_or(assign_null_score) as assign_null_score,
            logical_or(assign_score_above_max) as assign_score_above_max,
            logical_or(assign_w_score_less_5) as assign_w_score_less_5,
            logical_or(assign_h_score_less_5) as assign_h_score_less_5,
            logical_or(assign_f_score_less_5) as assign_f_score_less_5,
            logical_or(assign_w_missing_score_not_5) as assign_w_missing_score_not_5,
            logical_or(assign_f_missing_score_not_5) as assign_f_missing_score_not_5,
            logical_or(assign_h_missing_score_not_5) as assign_h_missing_score_not_5,
            logical_or(assign_w_missing_score_not_0) as assign_w_missing_score_not_0,
            logical_or(assign_f_missing_score_not_0) as assign_f_missing_score_not_0,
            logical_or(assign_h_missing_score_not_0) as assign_h_missing_score_not_0,
            logical_or(assign_s_missing_score_not_0) as assign_s_missing_score_not_0,
            logical_or(assign_s_score_less_50p) as assign_s_score_less_50p,
            logical_or(assign_s_hs_score_less_50p) as assign_s_hs_score_less_50p,
            logical_or(
                assign_s_ms_score_not_conversion_chart_options
            ) as assign_s_ms_score_not_conversion_chart_options,
            logical_or(
                assign_s_hs_score_not_conversion_chart_options
            ) as assign_s_hs_score_not_conversion_chart_options,

        from {{ ref("int_tableau__gradebook_audit_assignments_student") }}
        group by _dbt_source_relation, sectionid, assignmentid
    ),

    /* Join rollup to assignments_teacher for context */
    student_assignment_with_flags as (
        select
            t.academic_year,
            t.academic_year_display,
            t.region,
            t.school_level,
            t.region_school_level,
            t.schoolid,
            t.school,
            t.`quarter`,
            t.semester,
            t.week_number_quarter,
            t.quarter_start_date,
            t.quarter_end_date,
            t.is_current_term,
            t.is_quarter_end_date_range,
            t.week_start_monday,
            t.week_end_sunday,
            t.school_week_start_date_lead,
            t.is_current_week,
            t.assignment_category_name,
            t.assignment_category_code,
            t.assignment_category_term,
            t.expectation,
            t.notes,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.section_number,
            t.external_expression,
            t.credit_type,
            t.course_number,
            t.course_name,
            t.exclude_from_gpa,
            t.is_ap_course,
            t.teacher_number,
            t.teacher_name,
            t.teacher_tableau_username,
            t.school_leader,
            t.school_leader_tableau_username,
            t.assignmentid,
            t.assignment_name,
            t.duedate,
            t.scoretype,
            t.totalpointvalue,
            t.n_students,
            t.n_late,
            t.n_exempt,
            t.n_missing,
            t.n_null,
            t.n_academic_dishonesty,
            t.n_is_null_missing,
            t.n_is_null_not_missing,
            t.n_expected,
            t.n_expected_scored,
            t.sum_totalpointvalue_section_quarter_category,
            t.teacher_running_total_assign_by_cat,
            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

            r.assign_null_score,
            r.assign_score_above_max,
            r.assign_w_score_less_5,
            r.assign_h_score_less_5,
            r.assign_f_score_less_5,
            r.assign_w_missing_score_not_5,
            r.assign_f_missing_score_not_5,
            r.assign_h_missing_score_not_5,
            r.assign_w_missing_score_not_0,
            r.assign_f_missing_score_not_0,
            r.assign_h_missing_score_not_0,
            r.assign_s_missing_score_not_0,
            r.assign_s_score_less_50p,
            r.assign_s_hs_score_less_50p,
            r.assign_s_ms_score_not_conversion_chart_options,
            r.assign_s_hs_score_not_conversion_chart_options,

        from {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} as t
        inner join
            student_assignment_rollup as r
            on t.sectionid = r.sectionid
            and t.assignmentid = r.assignmentid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="r") }}
    ),

    /* UNPIVOT student assignment flags */
    student_assignment_unpivoted as (
        select *,
        from
            student_assignment_with_flags unpivot (
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

    /* Apply flags + exceptions */
    student_assignment_unpivot as (
        select u.*, f.cte_grouping, f.audit_category, f.code_type,
        from student_assignment_unpivoted as u
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on u.academic_year = f.academic_year
            and u.region = f.region
            and u.school_level = f.school_level
            and u.assignment_category_code = f.code
            and u.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'assignment_student'
        /* temporarily remove flags during non-eoq times */
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
        /* temporarily remove flags during non-eoq times */
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
        /* permanently remove flags by credit type and gradebook category */
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

    /* Branch 2: Aggregate 4 student category flags to
       teacher×section×quarter×category grain */
    student_category_rollup as (
        select
            _dbt_source_relation,
            sectionid,
            `quarter`,
            assignment_category_code,

            logical_or(qt_effort_grade_missing) as qt_effort_grade_missing,
            logical_or(w_grade_inflation) as w_grade_inflation,
            logical_or(qt_formative_grade_missing) as qt_formative_grade_missing,
            logical_or(qt_summative_grade_missing) as qt_summative_grade_missing,

        from {{ ref("int_tableau__gradebook_audit_student_scaffold") }}
        where scaffold_name = 'student_category_scaffold'
        group by _dbt_source_relation, sectionid, `quarter`, assignment_category_code
    ),

    student_category_with_flags as (
        select
            t.academic_year,
            t.academic_year_display,
            t.region,
            t.school_level,
            t.region_school_level,
            t.schoolid,
            t.school,
            t.`quarter`,
            t.semester,
            t.week_number_quarter,
            t.quarter_start_date,
            t.quarter_end_date,
            t.is_current_term,
            t.is_quarter_end_date_range,
            t.week_start_monday,
            t.week_end_sunday,
            t.school_week_start_date_lead,
            t.is_current_week,
            t.assignment_category_name,
            t.assignment_category_code,
            t.assignment_category_term,
            t.expectation,
            t.notes,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.section_number,
            t.external_expression,
            t.credit_type,
            t.course_number,
            t.course_name,
            t.exclude_from_gpa,
            t.is_ap_course,
            t.teacher_number,
            t.teacher_name,
            t.teacher_tableau_username,
            t.school_leader,
            t.school_leader_tableau_username,

            r.qt_effort_grade_missing,
            r.w_grade_inflation,
            r.qt_formative_grade_missing,
            r.qt_summative_grade_missing,

        from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as t
        inner join
            student_category_rollup as r
            on t.sectionid = r.sectionid
            and t.quarter = r.quarter
            and t.assignment_category_code = r.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="t", right_alias="r") }}
        where t.scaffold_name = 'teacher_category_scaffold'
    ),

    /* UNPIVOT student category flags */
    student_category_unpivoted as (
        select *,
        from
            student_category_with_flags unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_effort_grade_missing,
                    w_grade_inflation,
                    qt_formative_grade_missing,
                    qt_summative_grade_missing
                )
            )
    ),

    student_category_unpivot as (
        select u.*, f.cte_grouping, f.audit_category, f.code_type,
        from student_category_unpivoted as u
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on u.academic_year = f.academic_year
            and u.region = f.region
            and u.school_level = f.school_level
            and u.quarter = f.code
            and u.assignment_category_code = f.alt_code
            and u.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'student_course_category'
        /* temporarily remove flags */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on u.academic_year = e.academic_year
            and u.region = e.region
            and u.course_number = e.course_number
            and u.audit_flag_name = e.audit_flag_name
            and u.is_quarter_end_date_range = e.is_quarter_end_date_range
            and e.view_name = 'audit_flags'
            and e.cte = 'student_course_category'
            and e.is_quarter_end_date_range is not null
        where e.include_row is null
    ),

    /* Branch 3: Aggregate 7 EOQ student flags to teacher×section×quarter grain */
    student_eoq_rollup as (
        select
            _dbt_source_relation,
            sectionid,
            `quarter`,

            logical_or(qt_comment_missing) as qt_comment_missing,
            logical_or(qt_es_comment_missing) as qt_es_comment_missing,
            logical_or(qt_grade_70_comment_missing) as qt_grade_70_comment_missing,
            logical_or(qt_g1_g8_conduct_code_missing) as qt_g1_g8_conduct_code_missing,
            logical_or(
                qt_g1_g8_conduct_code_incorrect
            ) as qt_g1_g8_conduct_code_incorrect,
            logical_or(qt_percent_grade_greater_100) as qt_percent_grade_greater_100,
            logical_or(
                qt_student_is_ada_80_plus_gpa_less_2
            ) as qt_student_is_ada_80_plus_gpa_less_2,

        from {{ ref("int_tableau__gradebook_audit_student_scaffold") }}
        where scaffold_name = 'student_scaffold'
        group by _dbt_source_relation, sectionid, `quarter`
    ),

    student_eoq_with_flags as (
        select
            t.academic_year,
            t.academic_year_display,
            t.region,
            t.school_level,
            t.region_school_level,
            t.schoolid,
            t.school,
            t.`quarter`,
            t.semester,
            t.week_number_quarter,
            t.quarter_start_date,
            t.quarter_end_date,
            t.is_current_term,
            t.is_quarter_end_date_range,
            t.week_start_monday,
            t.week_end_sunday,
            t.school_week_start_date_lead,
            t.is_current_week,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.section_number,
            t.external_expression,
            t.credit_type,
            t.course_number,
            t.course_name,
            t.exclude_from_gpa,
            t.is_ap_course,
            t.teacher_number,
            t.teacher_name,
            t.teacher_tableau_username,
            t.school_leader,
            t.school_leader_tableau_username,

            r.qt_comment_missing,
            r.qt_es_comment_missing,
            r.qt_grade_70_comment_missing,
            r.qt_g1_g8_conduct_code_missing,
            r.qt_g1_g8_conduct_code_incorrect,
            r.qt_percent_grade_greater_100,
            r.qt_student_is_ada_80_plus_gpa_less_2,

        from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as t
        inner join
            student_eoq_rollup as r
            on t.sectionid = r.sectionid
            and t.quarter = r.quarter
            and {{ union_dataset_join_clause(left_alias="t", right_alias="r") }}
        where t.scaffold_name = 'teacher_scaffold'
    ),

    /* UNPIVOT student EOQ flags */
    student_eoq_unpivoted as (
        select *,
        from
            student_eoq_with_flags unpivot (
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

    student_eoq_unpivot as (
        select u.*, f.cte_grouping, f.audit_category, f.code_type,
        from student_eoq_unpivoted as u
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on u.academic_year = f.academic_year
            and u.region = f.region
            and u.school_level = f.school_level
            and u.quarter = f.code
            and u.audit_flag_name = f.audit_flag_name
            and f.cte_grouping in ('student_course', 'student')
            and f.audit_category != 'Conduct Code'
        /* permanently remove flags by credit type */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on u.academic_year = e1.academic_year
            and u.region = e1.region
            and u.school_level = e1.school_level
            and u.credit_type = e1.credit_type
            and u.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'audit_flags'
            and e1.cte = 'eoq_items'
            and e1.credit_type is not null
        where e1.include_row is null
    ),

    /* Branch 4: Conduct code flags — UNPIVOT at student grain, filter by
       grade_level via flags join, apply exceptions, then aggregate to
       teacher×section×quarter×flag grain and join teacher context */
    student_conduct_unpivoted as (
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
        where scaffold_name = 'student_scaffold'
    ),

    student_conduct_filtered as (
        select
            u._dbt_source_relation,
            u.sectionid,
            u.`quarter`,
            u.audit_flag_name,
            u.audit_flag_value,

            f.cte_grouping,
            f.audit_category,
            f.code_type,

        from student_conduct_unpivoted as u
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on u.academic_year = f.academic_year
            and u.region = f.region
            and u.school_level = f.school_level
            and u.quarter = f.code
            and u.grade_level = f.grade_level
            and u.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'student_course'
            and f.audit_category = 'Conduct Code'
        /* permanently remove flags by credit type */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on u.academic_year = e1.academic_year
            and u.region = e1.region
            and u.school_level = e1.school_level
            and u.credit_type = e1.credit_type
            and u.audit_flag_name = e1.audit_flag_name
            and e1.view_name = 'audit_flags'
            and e1.cte = 'eoq_items_conduct_code'
            and e1.credit_type is not null
        /* permanently remove flags by course number */
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on u.academic_year = e2.academic_year
            and u.region = e2.region
            and u.school_level = e2.school_level
            and u.course_number = e2.course_number
            and u.audit_flag_name = e2.audit_flag_name
            and e2.view_name = 'audit_flags'
            and e2.cte = 'eoq_items_conduct_code'
            and e2.credit_type is null
        where
            u.school_level = 'ES' and e1.include_row is null and e2.include_row is null
    ),

    student_conduct_agg as (
        select
            _dbt_source_relation,
            sectionid,
            `quarter`,
            audit_flag_name,
            cte_grouping,
            audit_category,
            code_type,

            logical_or(audit_flag_value) as audit_flag_value,

        from student_conduct_filtered
        group by
            _dbt_source_relation,
            sectionid,
            `quarter`,
            audit_flag_name,
            cte_grouping,
            audit_category,
            code_type
    ),

    student_conduct_unpivot as (
        select
            t.academic_year,
            t.academic_year_display,
            t.region,
            t.school_level,
            t.region_school_level,
            t.schoolid,
            t.school,
            t.`quarter`,
            t.semester,
            t.week_number_quarter,
            t.quarter_start_date,
            t.quarter_end_date,
            t.is_current_term,
            t.is_quarter_end_date_range,
            t.week_start_monday,
            t.week_end_sunday,
            t.school_week_start_date_lead,
            t.is_current_week,
            t.section_or_period,
            t.sectionid,
            t.sections_dcid,
            t.section_number,
            t.external_expression,
            t.credit_type,
            t.course_number,
            t.course_name,
            t.exclude_from_gpa,
            t.is_ap_course,
            t.teacher_number,
            t.teacher_name,
            t.teacher_tableau_username,
            t.school_leader,
            t.school_leader_tableau_username,

            r.cte_grouping,
            r.audit_category,
            r.code_type,
            r.audit_flag_name,
            r.audit_flag_value,

        from {{ ref("int_tableau__gradebook_audit_teacher_scaffold") }} as t
        inner join
            student_conduct_agg as r
            on t.sectionid = r.sectionid
            and t.quarter = r.quarter
            and {{ union_dataset_join_clause(left_alias="t", right_alias="r") }}
        where t.scaffold_name = 'teacher_scaffold'
    )

/* Branch 1: student assignment flags (aggregated) */
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
    is_current_week,
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
    n_academic_dishonesty,
    n_is_null_missing,
    n_is_null_not_missing,
    n_expected,
    n_expected_scored,

    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,

    sum_totalpointvalue_section_quarter_category,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,
    audit_category,
    cte_grouping,
    code_type,
    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_assignment_unpivot

union all

/* Branch 2: student category flags (aggregated) */
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
    is_current_week,
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

    null as teacher_assign_id,
    null as teacher_assign_name,
    null as teacher_assign_due_date,
    null as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_academic_dishonesty,
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
    cte_grouping,
    code_type,
    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_category_unpivot

union all

/* Branch 3: EOQ flags (aggregated, excluding conduct code) */
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
    is_current_week,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,

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

    null as teacher_assign_id,
    null as teacher_assign_name,
    null as teacher_assign_due_date,
    null as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_academic_dishonesty,
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
    cte_grouping,
    code_type,
    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_eoq_unpivot

union all

/* Branch 4: conduct code flags (aggregated, ES only) */
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
    is_current_week,

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    null as expectation,
    null as notes,

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

    null as teacher_assign_id,
    null as teacher_assign_name,
    null as teacher_assign_due_date,
    null as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_null,
    null as n_academic_dishonesty,
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
    cte_grouping,
    code_type,
    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_conduct_unpivot

union all

/* Branches 5-6: existing teacher flags (already at teacher grain) */
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
    is_current_week,
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
    n_academic_dishonesty,
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
    audit_flag_value,

from {{ ref("int_tableau__gradebook_audit_flags__teacher") }}
