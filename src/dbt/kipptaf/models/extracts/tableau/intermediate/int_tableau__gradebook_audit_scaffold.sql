select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.schoolid,
    s.school,

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

    s.school_level_alt as school_level,

    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    'teacher_scaffold_course' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.schoolid,
    s.school,

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

    s.school_level_alt as school_level,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    'teacher_scaffold_category' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.schoolid,
    s.school,

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

    s.school_level_alt as school_level,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    'teacher_scaffold_assignment' as scaffold_name,

from {{ ref("int_extracts__course_schedule_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
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

    s.school_level_alt as school_level,

    null as assignment_category_code,
    null as assignment_category_name,
    null as assignment_category_term,
    null as expectation,
    null as notes,

    'student_scaffold_course' as scaffold_name,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.rn_year = 1
    and s.enroll_status = 0
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and not s.is_out_of_district

union all

select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region_school_level_alt as region_school_level,
    s.region,
    s.schoolid,
    s.school,

    s.students_dcid,
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

    s.school_level_alt as school_level,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    'student_scaffold_category' as scaffold_name,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
inner join
    {{ ref("int_powerschool__u_expectations_qtd_unpivot") }} as ge
    on s.region = ge.region
    and s.school_level_alt = ge.school_level
    and s.academic_year = ge.academic_year
    and s.quarter = ge.quarter
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.rn_year = 1
    and s.enroll_status = 0
    and s.school_level_alt != 'ES'
    and s._dbt_source_project != 'kippmiami'
    and not s.is_out_of_district
