select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level as grade_level_int,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.is_homeless,
    s.iep_status,
    s.is_504,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.enroll_status,
    s.advisory,
    s.cohort,

    'Benchmark' as assessment_type,

    a.admin_season as expected_test,
    a.month_round as expected_month_round,
    a.grade as expected_grade_level_int,
    a.expected_measure_name_code,
    a.expected_measure_name,
    a.expected_measure_standard,

    g.benchmark_goal_season,
    g.grade_goal as admin_goal,
    g.grade_range_goal as admin_goal_grade_range,
    g.n_admin_season_school_gl_all,
    g.n_admin_season_school_gl_at_above,
    g.n_admin_season_school_gl_bl_wb,
    g.n_admin_season_school_gl_at_above_expected,
    g.n_admin_season_school_gl_at_above_gap,
    g.n_admin_season_region_gl_all,
    g.n_admin_season_region_gl_at_above,
    g.n_admin_season_region_gl_bl_wb,
    g.n_admin_season_region_gl_at_above_expected,
    g.n_admin_season_region_gl_at_above_gap,

    a.grade as grade_level,
    a.grade_level_text as expected_grade_level,
    null as average_starting_words,
    null as pm_round_days,
    null as pm_days,
    null as benchmark_goal,
    null as required_growth_words,
    null as daily_growth_rate,
    null as round_growth_words_goal,
    null as goal,

    c.students_student_number as schedule_student_number,
    c.cc_teacherid as teacherid,
    c.teacher_lastfirst as teacher_name,
    c.courses_course_name as course_name,
    c.cc_course_number as course_number,
    c.cc_section_number as section_number,

    b.student_number as mclass_student_number,
    b.assessment_grade,
    b.period,
    b.client_date,
    b.start_date,
    b.end_date,
    b.measure_name,
    b.measure_name_code,
    b.measure_standard,
    b.measure_standard_score,
    b.measure_standard_level,
    b.measure_standard_level_int,
    b.measure_percentile,
    b.measure_semester_growth,
    b.measure_year_growth,
    b.boy_composite,
    b.moy_composite,
    b.eoy_composite,

    r.enrollment_dates_account,
    r.expected_row_count,
    r.actual_row_count,
    r.completed_test_round,
    r.completed_test_round_int,

    null as met_measure_standard_goal,
    null as met_admin_benchmark_goal,
    null as met_measure_name_code_goal,
    null as met_pm_round_criteria,
    null as met_pm_round_overall_criteria,

    h.head_of_school_preferred_name_lastfirst as hos,

    f.nj_student_tier,
    f.is_tutoring as tutoring_nj,

    cast(a.round_number as string) as expected_round,

    right(c.courses_course_name, 1) as schedule_student_grade_level,

    if(c.students_student_number = s.student_number, 1, 0) as scheduled,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("stg_google_sheets__dibels_expected_assessments") }} as a
    on s.academic_year = a.academic_year
    and s.region = a.region
    and s.grade_level = a.grade
    and a.assessment_type = 'Benchmark'
    and a.assessment_include is null
left join
    {{ ref("rpt_gsheets__dibels_bm_goals_calculations") }} as g
    on a.academic_year = g.academic_year
    and a.region = g.region
    and a.grade = g.assessment_grade_int
    and a.admin_season = g.period
    and s.school = g.school
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on s.academic_year = c.cc_academic_year
    and s.schoolid = c.cc_schoolid
    and s.student_number = c.students_student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.cc_section_number not like '%SC%'
    and c.courses_course_name in (
        'ELA GrK',
        'ELA K',
        'ELA Gr1',
        'ELA Gr2',
        'ELA Gr3',
        'ELA Gr4',
        'ELA Gr5',
        'ELA Gr6',
        'ELA Gr7',
        'ELA Gr8'
    )
left join
    {{ ref("int_amplify__all_assessments") }} as b
    on a.academic_year = b.academic_year
    and a.admin_season = b.period
    and a.expected_measure_standard = b.measure_standard
    and s.student_number = b.student_number
left join
    {{ ref("int_students__dibels_participation_roster") }} as r
    on a.academic_year = r.academic_year
    and a.grade = r.grade_level
    and a.admin_season = r.admin_season
    and a.round_number = r.round_number
    and r.enrollment_dates_account
    and s.student_number = r.student_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as h
    on s.schoolid = h.home_work_location_powerschool_school_id
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on s.academic_year = f.academic_year
    and s.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="f") }}
    and f.iready_subject = 'Reading'
where not s.is_self_contained

union all

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level as grade_level_int,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.is_homeless,
    s.iep_status,
    s.is_504,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.enroll_status,
    s.advisory,
    s.cohort,

    'PM' as assessment_type,

    e.admin_season as expected_test,
    e.month_round as expected_month_round,
    e.grade as expected_grade_level_int,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,

    null as benchmark_goal_season,
    null as admin_goal,
    null as admin_goal_grade_range,
    null as n_admin_season_school_gl_all,
    null as n_admin_season_school_gl_at_above,
    null as n_admin_season_school_gl_bl_wb,
    null as n_admin_season_school_gl_at_above_expected,
    null as n_admin_season_school_gl_at_above_gap,
    null as n_admin_season_region_gl_all,
    null as n_admin_season_region_gl_at_above,
    null as n_admin_season_region_gl_bl_wb,
    null as n_admin_season_region_gl_at_above_expected,
    null as n_admin_season_region_gl_at_above_gap,

    g.assessment_grade_int as grade_level,
    g.assessment_grade as expected_grade_level,
    g.starting_words as average_starting_words,
    g.pm_round_days,
    g.pm_days,
    g.benchmark_goal,
    g.required_growth_words,
    g.daily_growth_rate,
    g.round_growth_words_goal,
    g.cumulative_growth_words as goal,

    c.students_student_number as schedule_student_number,
    c.cc_teacherid as teacherid,
    c.teacher_lastfirst as teacher_name,
    c.courses_course_name as course_name,
    c.cc_course_number as course_number,
    c.cc_section_number as section_number,

    a.student_number as mclass_student_number,
    a.assessment_grade,
    a.period,
    a.client_date,
    a.start_date,
    a.end_date,
    a.measure_name,
    a.measure_name_code,
    a.measure_standard,
    a.measure_standard_score,
    a.measure_standard_level,
    a.measure_standard_level_int,
    a.measure_percentile,
    a.measure_semester_growth,
    a.measure_year_growth,

    r.boy_composite,
    r.moy_composite,
    r.eoy_composite,

    rs.enrollment_dates_account,
    rs.expected_row_count,
    rs.actual_row_count,
    rs.completed_test_round,
    rs.completed_test_round_int,

    pm.met_measure_standard_goal,
    pm.met_admin_benchmark_goal,
    pm.met_measure_name_code_goal,
    pm.met_pm_round_criteria,
    pm.met_pm_round_overall_criteria,

    h.head_of_school_preferred_name_lastfirst as hos,

    f.nj_student_tier,
    f.is_tutoring as tutoring_nj,

    cast(e.round_number as string) as expected_round,

    right(c.courses_course_name, 1) as schedule_student_grade_level,

    if(c.students_student_number = s.student_number, 1, 0) as scheduled,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    {{ ref("int_google_sheets__dibels_pm_expectations") }} as e
    on s.academic_year = e.academic_year
    and s.region = e.region
    and s.grade_level = e.grade
    and e.pm_goal_include is null
inner join
    {{ ref("stg_google_sheets__dibels_pm_goals") }} as g
    on e.academic_year = g.academic_year
    and e.region = g.region
    and e.admin_season = g.admin_season
    and e.round_number = g.round_number
    and e.grade = g.assessment_grade_int
    and e.expected_measure_standard = g.measure_standard
    and g.pm_goal_include is null
inner join
    {{ ref("int_amplify__all_assessments") }} as r
    on s.academic_year = r.academic_year
    and s.student_number = r.student_number
    and s.grade_level = r.assessment_grade_int
    and e.admin_season = r.matching_season
    and r.measure_standard = 'Composite'
    and r.overall_probe_eligible = 'Yes'
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on s.academic_year = c.cc_academic_year
    and s.schoolid = c.cc_schoolid
    and s.student_number = c.students_student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.cc_section_number not like '%SC%'
    and c.courses_course_name in (
        'ELA GrK',
        'ELA K',
        'ELA Gr1',
        'ELA Gr2',
        'ELA Gr3',
        'ELA Gr4',
        'ELA Gr5',
        'ELA Gr6',
        'ELA Gr7',
        'ELA Gr8'
    )
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on e.academic_year = a.academic_year
    and e.admin_season = a.period
    and e.round_number = a.round_number
    and e.expected_measure_standard = a.measure_standard
    and s.student_number = a.student_number
left join
    {{ ref("int_students__dibels_participation_roster") }} as rs
    on e.academic_year = rs.academic_year
    and e.grade = rs.grade_level
    and e.admin_season = rs.admin_season
    and e.round_number = rs.round_number
    and rs.enrollment_dates_account
    and s.student_number = rs.student_number
left join
    {{ ref("int_amplify__pm_met_criteria") }} as pm
    on e.academic_year = pm.academic_year
    and e.grade = pm.assessment_grade_int
    and e.admin_season = pm.admin_season
    and e.round_number = pm.round_number
    and e.expected_measure_standard = pm.measure_standard
    and s.student_number = pm.student_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as h
    on s.schoolid = h.home_work_location_powerschool_school_id
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on s.academic_year = f.academic_year
    and s.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="f") }}
    and f.iready_subject = 'Reading'
where not s.is_self_contained
