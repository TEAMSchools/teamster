select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
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
    e.start_date,
    e.end_date,
    e.month_round,
    e.grade as expected_grade_level_int,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,
    e.benchmark_goal as admin_benchmark,

    g.assessment_grade as grade_level,
    g.assessment_grade_int as expected_grade_level,
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
    and e.expected_measure_standard = a.measure_standard
    and e.round_number = a.round_number
    and e.admin_season = a.period
    and s.student_number = a.student_number
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
