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

            a.period as expected_test,
            a.pm_round as expected_round,
            a.measure_name as expected_mclass_measure_name,
            a.measure_standard as expected_mclass_measure_standard,
            a.goal,

            format_datetime("%B", a.start_date) as month_round,

            if(e.grade_level = 0, 'K', cast(e.grade_level as string)) as grade_level,
        from {{ ref("int_tableau__student_enrollments") }} as e
        inner join
            {{ ref("stg_amplify__dibels_pm_expectations") }} as a
            -- on e.academic_year = a.academic_year
            on e.region = a.region
            and e.grade_level = a.grade_level
        where not e.is_self_contained and e.academic_year >= 2024 and e.grade_level <= 2
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
            and m.cc_academic_year >= 2024
            and m.cc_section_number not like '%SC%'
            and m.courses_course_name in (
                'ELA GrK', 'ELA K', 'ELA Gr1', 'ELA Gr2'
            -- 'ELA Gr3',
            -- 'ELA Gr4',
            -- 'ELA Gr5',
            -- 'ELA Gr6',
            -- 'ELA Gr7',
            -- 'ELA Gr8'
            )
    ),

    expanded_terms as (
        select
            2024 as academic_year,
            period as name,
            region,
            grade_level,
            start_date,
            end_date,
        from {{ ref("stg_amplify__dibels_pm_expectations") }}
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
    s.expected_round,
    s.expected_mclass_measure_name,
    s.expected_mclass_measure_standard,
    s.goal,
    s.month_round,

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
    a.mclass_sync_date,
    a.mclass_measure,
    a.mclass_measure_code,
    a.mclass_measure_standard,
    a.mclass_measure_standard_score,
    a.mclass_measure_standard_level,
    a.mclass_measure_standard_level_int,
    a.mclass_measure_percentile,
    a.mclass_measure_semester_growth,
    a.mclass_measure_year_growth,
    a.mclass_score_change,

    t.name,
    t.grade_level as round_grade_level,
    t.start_date,
    t.end_date,

    f.nj_student_tier,
    f.tutoring_nj,

    coalesce(a.pm_probe_eligible, 'No data') as pm_probe_eligible,
    coalesce(a.pm_probe_tested, 'No data') as pm_probe_tested,
    coalesce(a.boy_probe_eligible, 'No data') as boy_probe_eligible,
    coalesce(a.moy_probe_eligible, 'No data') as moy_probe_eligible,
    coalesce(a.boy_composite, 'No data') as boy_composite,
    coalesce(a.moy_composite, 'No data') as moy_composite,
    coalesce(a.eoy_composite, 'No data') as eoy_composite,
    coalesce(a.mclass_probe_number, 0) as mclass_probe_number,
    coalesce(a.mclass_total_number_of_probes, 0) as mclass_total_number_of_probes,
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
    and a.assessment_type = 'PM'
left join
    expanded_terms as t
    on s.academic_year = t.academic_year
    and s.expected_test = t.name
    and s.grade = t.grade_level
    and s.region = t.region
left join
    {{ ref("int_reporting__student_filters") }} as f
    on s.academic_year = f.academic_year
    and s.student_number = f.student_number
    and regexp_extract(s._dbt_source_relation, r'(kipp\w+)_')
    = regexp_extract(f._dbt_source_relation, r'(kipp\w+)_')
    and f.iready_subject = 'Reading'
