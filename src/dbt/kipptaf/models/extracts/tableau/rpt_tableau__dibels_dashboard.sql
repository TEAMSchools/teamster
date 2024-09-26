with
    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.district,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.studentid,
            e.student_number,
            e.student_name,
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

            a.admin_season as expected_test,
            a.test_code,
            a.month_round,

            a.grade as expected_grade_level,
            regexp_extract(
                a.assessment_subject_area, r'^[^_]*'
            ) as expected_mclass_measure_name_code,
            regexp_substr(
                a.assessment_subject_area, r'_(.*?)_'
            ) as expected_mclass_measure_name,
            regexp_substr(
                a.assessment_subject_area, r'[^_]+$'
            ) as expected_mclass_measure_standard,

            if(e.grade_level = 0, 'K', cast(e.grade_level as string)) as grade_level,

            if(
                e.academic_year = 2024
                or (e.academic_year = 2023 and e.grade_level <= 2),
                true,
                false
            ) as year_grade_filter,
        from {{ ref("int_tableau__student_enrollments") }} as e
        inner join
            {{ ref("stg_assessments__assessment_expectations") }} as a
            on e.academic_year = a.academic_year
            and e.region = a.region
            and e.grade_level = a.grade
            and a.scope = 'DIBELS'
        where
            not e.is_self_contained
            and e.academic_year >= {{ var("current_academic_year") - 1 }}
            and e.grade_level <= 8
    ),

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
            and m.cc_academic_year >= {{ var("current_academic_year") - 1 }}
            and m.cc_section_number not like '%SC%'
            and m.courses_course_name in (
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
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.district,
    s.region,
    s.state,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.enroll_status,
    s.is_homeless,
    s.is_504,
    s.iep_status,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.advisory,
    s.cohort,
    s.expected_test,
    s.month_round,
    s.expected_mclass_measure_name_code,
    s.expected_mclass_measure_name,
    s.expected_mclass_measure_standard,
    null as goal,

    m.schedule_student_number,
    m.schedule_student_grade_level,
    m.teacherid,
    m.teacher_name,
    m.course_name,
    m.course_number,
    m.section_number,
    m.scheduled,
    m.hos,

    a.mclass_student_number,
    a.assessment_type,
    a.mclass_assessment_grade,
    a.mclass_period,
    a.mclass_client_date,
    a.mclass_measure_name,
    a.mclass_measure_name_code,
    a.mclass_measure_standard,
    a.mclass_measure_standard_score,
    a.mclass_measure_standard_level,
    a.mclass_measure_standard_level_int,
    a.mclass_measure_percentile,
    a.mclass_measure_semester_growth,
    a.mclass_measure_year_growth,
    a.boy_composite,
    a.moy_composite,
    a.eoy_composite,

    t.start_date,
    t.end_date,

    f.nj_student_tier,
    f.tutoring_nj,

    right(s.test_code, 1) as expected_round,

    if(
        s.expected_grade_level = 0, 'K', cast(s.expected_grade_level as string)
    ) as expected_grade_level,

from students as s
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.schoolid = m.cc_schoolid
    and s.student_number = m.schedule_student_number
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on s.academic_year = a.mclass_academic_year
    and s.student_number = a.mclass_student_number
    and s.expected_test = a.mclass_period
    and a.assessment_type = 'Benchmark'
left join
    {{ ref("stg_reporting__terms") }} as t
    on s.academic_year = t.academic_year
    and s.expected_test = t.name
    and s.region = t.region
    and t.type = 'LIT'
left join
    {{ ref("int_reporting__student_filters") }} as f
    on s.academic_year = f.academic_year
    and s.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="f") }}
    and f.iready_subject = 'Reading'
where s.year_grade_filter

union all

select
    _dbt_source_relation,
    academic_year,
    district,
    region,
    state,
    schoolid,
    school,
    studentid,
    student_number,
    student_name,
    grade_level,
    is_out_of_district,
    gender,
    ethnicity,
    enroll_status,
    is_homeless,
    is_504,
    iep_status,
    lep_status,
    lunch_status,
    gifted_and_talented,
    advisory,
    cohort,
    expected_test,
    month_round,
    expected_mclass_measure_name_code,
    expected_mclass_measure_name,
    expected_mclass_measure_standard,
    goal,

    schedule_student_number,
    schedule_student_grade_level,
    teacherid,
    teacher_name,
    course_name,
    course_number,
    section_number,
    scheduled,
    hos,

    mclass_student_number,
    assessment_type,
    mclass_assessment_grade,
    mclass_period,
    mclass_client_date,
    mclass_measure_name,
    mclass_measure_name_code,
    mclass_measure_standard,
    mclass_measure_standard_score,
    mclass_measure_standard_level,
    mclass_measure_standard_level_int,
    mclass_measure_percentile,
    mclass_measure_semester_growth,
    mclass_measure_year_growth,
    boy_composite,
    moy_composite,
    eoy_composite,

    start_date,
    end_date,

    nj_student_tier,
    tutoring_nj,

    expected_round,
    expected_grade_level,
from {{ ref("rpt_tableau__dibels_pm_dashboard") }}
