with
    schedules as (
        select
            m._dbt_source_relation,
            m.cc_studentid,
            m.cc_academic_year,
            m.cc_course_number as course_number,
            m.cc_schoolid,
            m.cc_section_number as section_number,
            m.cc_teacherid as teacherid,
            m.courses_course_name as course_name,
            m.students_student_number as schedule_student_number,
            m.teacher_lastfirst as teacher_name,

            hos.head_of_school_preferred_name_lastfirst as hos,

            1 as scheduled,

            right(m.courses_course_name, 1) as schedule_student_grade_level,

        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_people__leadership_crosswalk") }} as hos
            on m.cc_schoolid = hos.home_work_location_powerschool_school_id
        where
            m.rn_course_number_year = 1
            and not m.is_dropped_section
            and m.cc_section_number not like '%SC%'
            and m.courses_course_name in (
                'ELA GrK',
                'ELA K',
                'ELA Gr1',
                'ELA Gr2'
                'ELA Gr3',
                'ELA Gr4',
                'ELA Gr5',
                'ELA Gr6',
                'ELA Gr7',
                'ELA Gr8'
            )
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.district,
    e.state,
    e.region,
    e.schoolid,
    e.school,
    e.studentid,
    e.student_number,
    e.student_name,
    e.grade_level as grade_level_int,
    e.is_out_of_district,
    e.gender,
    e.ethnicity,
    e.is_homeless,
    e.iep_status,
    e.is_504,
    e.lep_status,
    e.lunch_status,
    e.gifted_and_talented,
    e.enroll_status,
    e.advisory,
    e.cohort,

    pme.admin_season as expected_test,
    cast(a.round_number as string) as expected_round,
    pme.start_date,
    pme.end_date,
    pme.month_round,
    pme.grade as expected_grade_level_int,
    pme.expected_measure_name_code,
    pme.expected_measure_name,
    pme.expected_measure_standard,
    pme.benchmark_goal as admin_benchmark,

    g.cumulative_growth_words as goal,

    if(e.grade_level = 0, 'K', cast(e.grade_level as string)) as grade_level,

    m.schedule_student_number,
    m.schedule_student_grade_level,
    m.teacherid,
    m.teacher_name,
    m.course_name,
    m.course_number,
    m.section_number,
    m.scheduled,
    m.hos,

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
    a.boy_composite,
    a.moy_composite,
    a.eoy_composite,

    f.nj_student_tier,
    f.is_tutoring as tutoring_nj,

    pm.met_measure_standard_goal,
    pm.met_admin_benchmark_goal,
    pm.met_measure_name_code_goal,
    pm.met_pm_round_criteria,
    pm.met_pm_round_overall_criteria,

    'PM' as assessment_type,

    if(pme.grade = 0, 'K', cast(pme.grade as string)) as expected_grade_level,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_google_sheets__dibels_pm_expectations") }} as pme
    on e.academic_year = pme.academic_year
    and e.region = pme.region
    and e.grade_level = pme.grade
    and pme.pm_goal_include is null
inner join
    {{ ref("stg_google_sheets__dibels_pm_goals") }} as g
    on pme.academic_year = g.academic_year
    and pme.region = g.region
    and pme.admin_season = g.admin_season
    and pme.round_number = g.round_number
    and pme.grade = g.assessment_grade_int
    and pme.expected_measure_standard = g.measure_standard
    and pme.pm_goal_include is null
inner join
    {{ ref("int_amplify__all_assessments") }} as s
    on e.academic_year = s.academic_year
    and e.student_number = s.student_number
    and e.grade_level = s.assessment_grade_int
    and pme.admin_season = s.matching_season
    and s.measure_standard = 'Composite'
    and s.overall_probe_eligible = 'Yes'
left join
    schedules as m
    on e.academic_year = m.cc_academic_year
    and e.schoolid = m.cc_schoolid
    and e.student_number = m.schedule_student_number
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on s.academic_year = a.academic_year
    and s.student_number = a.student_number
    and s.matching_season = a.period
    and s.measure_standard = a.measure_standard
    and a.client_date between pme.start_date and pme.end_date
    and a.assessment_type = 'PM'
left join
    {{ ref("int_amplify__pm_met_criteria") }} as pm
    on e.academic_year = pm.academic_year
    and e.student_number = pm.student_number
    and pme.admin_season = pm.admin_season
    and pme.round_number = pm.round_number
    and pme.expected_measure_standard = pm.measure_standard
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on e.academic_year = f.academic_year
    and e.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="f") }}
    and f.iready_subject = 'Reading'
where not e.is_self_contained
