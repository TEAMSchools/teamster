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

            a.admin_season as expected_test,
            a.month_round,

            if(e.grade_level = 0, 'K', cast(e.grade_level as string)) as grade_level,

        from {{ ref("int_tableau__student_enrollments") }} as e
        left join
            {{ ref("stg_assessments__assessment_expectations") }} as a
            on e.academic_year = a.academic_year
            and e.region = a.region
            and e.grade_level = a.grade
        -- and a.scope = 'DIBELS'
        where
            e.academic_year >= {{ var("current_academic_year") }} - 1
            and e.grade_level <= 8
            and not e.is_self_contained
            and a.scope = 'DIBELS'
    ),

    schedules as (

        select
            _dbt_source_relation,
            cc_academic_year,
            cc_schoolid,
            cc_studentid,
            students_student_number as student_number,
            cc_teacherid as teacherid,
            teacher_lastfirst as teacher_name,
            courses_course_name as course_name,
            cc_course_number as course_number,
            cc_section_number as section_number,

            1 as scheduled,

            right(courses_course_name, 1) as schedule_student_grade_level,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year >= {{ var("current_academic_year") }} - 1
            and not is_dropped_course
            and not is_dropped_section
            and rn_course_number_year = 1
            and courses_course_name in (
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
    s.expected_test,

    m.schedule_student_grade_level,
    m.teacherid,
    m.teacher_name,
    m.course_name,
    m.course_number,
    m.section_number,
    m.scheduled,

    a.mclass_student_number,
    a.assessment_type,
    a.mclass_assessment_grade,
    a.mclass_period,
    a.mclass_client_date,
    a.mclass_sync_date,
    a.mclass_measure,
    a.mclass_measure_score,
    a.mclass_measure_level,
    a.mclass_measure_level_int,
    a.mclass_measure_percentile,
    a.mclass_measure_semester_growth,
    a.mclass_measure_year_growth,
    a.mclass_score_change,

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
    and s.student_number = m.student_number
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on s.academic_year = a.mclass_academic_year
    and s.student_number = a.mclass_student_number
    and s.expected_test = a.mclass_period
where
    m.section_number not like '%SC%'

    /* PLEASE IGNORE THE REST - IT IS MY GUIDE TO REWRITING THIS QUERY FOR NEW DIBELS STUFF

with
    expanded_terms as (
        select
            academic_year,
            name,
            start_date,
            region,
            coalesce(
                lead(start_date, 1) over (
                    partition by academic_year, region order by code asc
                )
                - 1,
                date({{ var("current_academic_year") + 1 }}, 06, 30)
            ) as end_date,
        from {{ ref("stg_reporting__terms") }}
        where type = 'LIT' and academic_year >= {{ var("current_academic_year") }} - 1
    )

select
    b._dbt_source_relation,
    b.academic_year,
    b.district,
    b.region,
    b.schoolid,
    b.school,
    b.student_number,
    b.studentid,
    b.student_name,
    b.student_last_name,
    b.student_first_name,
    b.grade_level,
    b.schedule_academic_year,
    b.schedule_district,
    b.schedule_region,
    b.schedule_schoolid,
    b.schedule_student_number,
    b.schedule_student_grade_level,
    b.is_out_of_district,
    b.gender,
    b.ethnicity,
    b.gifted_and_talented,
    b.is_homeless,
    b.is_504,
    b.sped,
    b.lep_status,
    b.lunch_status,
    b.teacherid,
    b.teacher_name,
    b.course_name,
    b.course_number,
    b.section_number,
    b.advisory_name,
    b.expected_test,
    b.scheduled,
    b.mclass_student_number,
    b.mclass_assessment_grade,
    b.mclass_period,
    b.mclass_client_date,
    b.mclass_sync_date,
    b.boy_composite,
    b.moy_composite,
    b.eoy_composite,
    b.mclass_probe_number,
    b.mclass_total_number_of_probes,
    b.boy_probe_eligible,
    b.moy_probe_eligible,
    b.pm_probe_eligible,
    b.pm_probe_tested,
    b.mclass_measure,
    b.mclass_measure_score,
    b.mclass_score_change,
    b.mclass_measure_level,
    b.mclass_measure_level_int,
    b.mclass_measure_percentile,
    b.mclass_measure_semester_growth,
    b.mclass_measure_year_growth,

    t.name,
    t.start_date,
    t.end_date,

    f.nj_student_tier,
    f.tutoring_nj,

    hos.head_of_school_preferred_name_lastfirst as hos,
from base_roster as b
left join
    expanded_terms as t
    on cast(b.academic_year as int) = t.academic_year
    and b.expected_test = t.name
    and b.region = t.region
left join
    {{ ref("int_reporting__student_filters") }} as f
    on cast(b.academic_year as int) = f.academic_year
    and b.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="b", right_alias="f") }}
    and f.iready_subject = 'Reading'
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on b.schoolid = hos.home_work_location_powerschool_school_id
*/
    
