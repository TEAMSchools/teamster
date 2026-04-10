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
            {{ ref("int_tableau__gradebook_audit_section_week_student_scaffold") }}
            unpivot (
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
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_category_student_scaffold"
                )
            }}
            unpivot (
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
    r.region,
    r.schoolid,
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
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
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
    r.date_enrolled,
    r.sectionid,
    r.teacher_number,
    r.quarter,
    r.week_number_quarter,
    r.assignment_category_term,
    r.assignmentid,
    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    r.quarter_course_percent_grade,
    r.quarter_course_grade_points,
    r.quarter_conduct,
    r.quarter_comment_value,
    r.scorepoints,
    r.score_entered,
    r.assign_final_score_percent,
    r.is_exempt,
    r.is_expected_late,
    r.is_expected_missing,
    r.is_expected_academic_dishonesty,
    r.cte_grouping,
    r.audit_flag_name,
    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from student_unpivot as r

union all

select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
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
    sectionid,
    teacher_number,
    `quarter`,
    week_number_quarter,
    assignment_category_term,
    cast(null as int64) as assignmentid,
    category_quarter_percent_grade,
    category_quarter_average_all_courses,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    cast(null as float64) as scorepoints,
    cast(null as float64) as score_entered,
    cast(null as float64) as assign_final_score_percent,
    cast(null as int64) as is_exempt,
    cast(null as int64) as is_expected_late,
    cast(null as int64) as is_expected_missing,
    cast(null as int64) as is_expected_academic_dishonesty,
    cte_grouping,
    audit_flag_name,
    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from student_course_category

union all

select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
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
    sectionid,
    teacher_number,
    `quarter`,
    week_number_quarter,
    cast(null as string) as assignment_category_term,
    cast(null as int64) as assignmentid,
    cast(null as float64) as category_quarter_percent_grade,
    cast(null as float64) as category_quarter_average_all_courses,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    cast(null as float64) as scorepoints,
    cast(null as float64) as score_entered,
    cast(null as float64) as assign_final_score_percent,
    cast(null as int64) as is_exempt,
    cast(null as int64) as is_expected_late,
    cast(null as int64) as is_expected_missing,
    cast(null as int64) as is_expected_academic_dishonesty,
    cte_grouping,
    audit_flag_name,
    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items

union all

select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
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
    sectionid,
    teacher_number,
    `quarter`,
    week_number_quarter,
    cast(null as string) as assignment_category_term,
    cast(null as int64) as assignmentid,
    cast(null as float64) as category_quarter_percent_grade,
    cast(null as float64) as category_quarter_average_all_courses,
    quarter_course_percent_grade,
    quarter_course_grade_points,
    quarter_conduct,
    quarter_comment_value,
    cast(null as float64) as scorepoints,
    cast(null as float64) as score_entered,
    cast(null as float64) as assign_final_score_percent,
    cast(null as int64) as is_exempt,
    cast(null as int64) as is_expected_late,
    cast(null as int64) as is_expected_missing,
    cast(null as int64) as is_expected_academic_dishonesty,
    cte_grouping,
    audit_flag_name,
    audit_category,
    code_type,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items_conduct_code
