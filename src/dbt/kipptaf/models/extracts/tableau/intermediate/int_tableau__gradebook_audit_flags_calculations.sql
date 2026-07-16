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
            comment_value as quarter_comment_value,

            'last_year' as grades_type,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }}
            and storecode_type = 'Q'
            and not is_transfer_grade
    )

-- teacher x section for healthy
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.school_level_alt as school_level,
    s.schoolid,
    s.school,

    null as students_dcid,
    null as studentid,
    null as student_number,
    cast(null as string) as student_name,
    null as grade_level,
    cast(null as date) as dateenrolled,
    cast(null as date) as dateleft,
    cast(null as string) as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    cast(null as string) as gender,
    cast(null as string) as ethnicity,
    cast(null as string) as advisory,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    cast(null as bool) as is_out_of_district,
    cast(null as bool) as is_self_contained,
    cast(null as bool) as is_retained_year,
    cast(null as bool) as is_retained_ever,
    cast(null as string) as lunch_status,
    cast(null as string) as gifted_and_talented,
    cast(null as string) as iep_status,
    cast(null as bool) as lep_status,
    cast(null as bool) as is_504,
    null as is_counseling_services,
    null as is_student_athlete,
    cast(null as float64) as `ada`,
    cast(null as bool) as ada_above_or_at_80,

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

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    'NC' as assignment_category_code,
    'No Category' as assignment_category_name,
    'NC' as assignment_category_term,
    0 as expectation,
    'No Notes' as notes,

    0.0 as quarter_course_percent_grade,
    cast(null as string) as quarter_comment_value,

    'sections_teacher' as cte_grouping,
    'No Flags' as audit_category,

    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,
    null as assignment_has_flags,

    false as qt_percent_grade_greater_100,
    false as qt_grade_70_comment_missing,

    null as total_assign_count_qtd_by_cat_section_actual,
    null as total_assign_count_qtd_by_cat_section_no_flags,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and s.exclude_from_gpa = 0

union all

-- assignment_teacher flags: prep work for expected_assign_count_not_met 
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.school_level_alt as school_level,
    s.schoolid,
    s.school,

    null as students_dcid,
    null as studentid,
    null as student_number,
    cast(null as string) as student_name,
    null as grade_level,
    cast(null as date) as dateenrolled,
    cast(null as date) as dateleft,
    cast(null as string) as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    cast(null as string) as gender,
    cast(null as string) as ethnicity,
    cast(null as string) as advisory,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    cast(null as bool) as is_out_of_district,
    cast(null as bool) as is_self_contained,
    cast(null as bool) as is_retained_year,
    cast(null as bool) as is_retained_ever,
    cast(null as string) as lunch_status,
    cast(null as string) as gifted_and_talented,
    cast(null as string) as iep_status,
    cast(null as bool) as lep_status,
    cast(null as bool) as is_504,
    null as is_counseling_services,
    null as is_student_athlete,
    cast(null as float64) as `ada`,
    cast(null as bool) as ada_above_or_at_80,

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

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    0.0 as quarter_course_percent_grade,
    cast(null as string) as quarter_comment_value,

    'assignment_teacher' as cte_grouping,
    'Teacher Gradebook Flags' as audit_category,

    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,
    r.assignment_has_flags,

    false as qt_percent_grade_greater_100,
    false as qt_grade_70_comment_missing,

    countif(r.duedate <= ge.week_end_sunday) over (
        partition by s._dbt_source_project, s.sectionid, ge.assignment_category_term
    ) as total_assign_count_qtd_by_cat_section_actual,

    countif(r.duedate <= ge.week_end_sunday and not r.assignment_has_flags) over (
        partition by s._dbt_source_project, s.sectionid, ge.assignment_category_term
    ) as total_assign_count_qtd_by_cat_section_no_flags,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.`quarter` = ge.`quarter`
left join
    {{ ref("int_powerschool__gradebook_assignment_scores_rollup") }} as r
    on s._dbt_source_project = r._dbt_source_project
    and s.sections_dcid = r.sectionsdcid
    and ge.assignment_category_code = r.category_code
    and r.duedate between s.quarter_start_date and s.quarter_end_date
    and r.scoretype in ('POINTS', 'PERCENT')
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and s.exclude_from_gpa = 0

union all

-- student_course flags: qt_grade_70_comment_missing and qt_percent_grade_greater_100
select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.school_level_alt as school_level,
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

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    'NC' as assignment_category_code,
    'No Category' as assignment_category_name,
    'NC' as assignment_category_term,
    0 as expectation,
    'No Notes' as notes,

    qg.quarter_course_percent_grade,
    qg.quarter_comment_value,

    'student_course' as cte_grouping,
    'EOQ' as audit_category,

    0 as assignmentid,
    'No Assignment' as assignment_name,
    cast(null as date) as duedate,
    'No Score Type' as scoretype,
    0 as totalpointvalue,
    cast(null as bool) as assignment_has_flags,

    if(
        qg.quarter_course_percent_grade > 100, true, false
    ) as qt_percent_grade_greater_100,

    if(
        qg.quarter_course_percent_grade < 70 and qg.quarter_comment_value is null,
        true,
        false
    ) as qt_grade_70_comment_missing,

    null as total_assign_count_qtd_by_cat_section_actual,
    null as total_assign_count_qtd_by_cat_section_no_flags,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
left join
    quarter_course_grades as qg
    on s.academic_year = qg.academic_year
    and s.studentid = qg.studentid
    and s.sectionid = qg.sectionid
    and s._dbt_source_project = qg._dbt_source_project
    and s.`quarter` = qg.storecode
    and qg.grades_type = 'current_year'  /* summer toggle: see skill */
where
    s.academic_year = {{ var("current_academic_year") }}  /* summer toggle: see skill */
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
    and s.rn_year = 1
    and s.enroll_status = 0
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and not s.is_out_of_district
    and s.exclude_from_gpa = 0
