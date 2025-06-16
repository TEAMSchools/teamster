with
    eligible_students as (
        select
            academic_year,
            student_number,
            assessment_grade_int,
            pm_season,
            max(pm_eligible) as pm_eligible,

        from
            {{ ref("int_amplify__all_assessments") }} unpivot (
                pm_eligible
                for pm_season
                in (boy_probe_eligible as 'BOY->MOY', moy_probe_eligible as 'MOY->EOY')
            ) as upvt
        where
            assessment_type = 'Benchmark'
            and assessment_grade_int <= 2
            and academic_year >= 2024
            and measure_standard = 'Composite'
        group by all
    ),

    students as (
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

            a.period as expected_test,
            cast(a.pm_round as string) as expected_round,
            a.start_date,
            a.end_date,
            a.grade_level as expected_grade_level,
            a.measure_level_code as expected_measure_name_code,
            a.measure_standard as expected_measure_standard,
            a.goal,

            concat(e.grade_level, a.period, a.pm_round) as goal_filter,

            format_datetime('%B', a.start_date) as month_round,

            if(e.grade_level = 0, 'K', cast(e.grade_level as string)) as grade_level,

            if(
                a.period = 'BOY->MOY', a.moy_benchmark, a.eoy_benchmark
            ) as admin_benchmark,

            case
                a.measure_level_code
                when 'LNF'
                then 'Letter Names'
                when 'PSF'
                then 'Phonological Awareness'
                when 'NWF'
                then 'Nonsense Word Fluency'
                when 'WRF'
                then 'Word Reading Fluency'
                when 'ORF'
                then 'Oral Reading Fluency'
                else a.measure_level_code
            end as expected_measure_name,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("stg_amplify__dibels_pm_expectations") }} as a
            on e.academic_year = a.academic_year
            and e.region = a.region
            and e.grade_level = a.grade_level
        inner join
            eligible_students as s
            on e.student_number = s.student_number
            and e.grade_level = s.assessment_grade_int
            and a.period = s.pm_season
            and s.pm_eligible = 'Yes'
        where
            not e.is_self_contained
            and e.academic_year >= 2024
            and e.grade_level <= 2
            and e.region != 'Miami'
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

    met_overall_goal_or_bm_modified as (
        select
            s.academic_year,
            s.student_number,
            s.grade_level,
            s.expected_test,
            s.expected_round,
            s.expected_measure_standard,
            s.goal,

            a.measure_standard_score,

            if(a.measure_standard_score >= s.goal, true, false) as met_overall_goal,

            if(
                a.measure_standard_score >= s.admin_benchmark, true, false
            ) as met_admin_benchmark,

        from students as s
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.student_number = a.student_number
            and s.expected_test = a.period
            and s.expected_measure_standard = a.measure_standard
            and a.client_date between s.start_date and s.end_date
            and a.assessment_type = 'PM'
        where
            s.goal_filter in (
                '1BOY->MOY3',
                '1BOY->MOY4',
                '0BOY->MOY4',
                '1MOY->EOY7',
                '2MOY->EOY7',
                '0MOY->EOY9'
            )
            and a.measure_standard_score is not null
    ),

    met_overall_goal_calculation_modified as (
        select
            academic_year,
            student_number,
            grade_level,
            expected_test,
            expected_round,

            max(psf) as psf,
            max(cls) as cls,
            max(wrc) as wrc,
            max(orf_acc) as orf_acc,
            max(orf) as orf,

            case
                when
                    grade_level = '1'
                    and expected_round = '3'
                    and (max(psf) = true or (max(cls) = true and max(wrc) = true))
                then true
                when
                    grade_level = '1'
                    and expected_round = '4'
                    and (max(psf) = true or (max(cls) = true and max(wrc) = true))
                then true
                when
                    grade_level = '1'
                    and expected_round = '7'
                    and (
                        max(orf_acc) = true
                        and max(orf) = true
                        and max(cls) = true
                        and max(wrc) = true
                    )
                then true
                when
                    grade_level = '2'
                    and expected_round = '7'
                    and (
                        max(orf_acc) = true
                        and max(orf) = true
                        and max(cls) = true
                        and max(wrc) = true
                    )
                then true
                when
                    grade_level = '0'
                    and expected_round = '9'
                    and (max(wrf) = true and max(wrc) = true)
                then true
                else false
            end as met_overall_goal,

        from
            met_overall_goal_or_bm_modified pivot (
                max(met_overall_goal)
                for expected_measure_standard in (
                    'Phonemic Awareness (PSF)' as psf,
                    'Letter Sounds (NWF-CLS)' as cls,
                    'Decoding (NWF-WRC)' as wrc,
                    'Reading Accuracy (ORF-Accu)' as orf_acc,
                    'Reading Fluency (ORF)' as orf,
                    'Word Reading (WRF)' as wrf
                )
            ) as pvt
        group by all
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
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
    s.start_date,
    s.end_date,
    s.month_round,
    s.expected_measure_name_code,
    s.expected_measure_name,
    s.expected_measure_standard,
    s.goal,
    s.admin_benchmark,

    m.schedule_student_number,
    m.schedule_student_grade_level,
    m.teacherid,
    m.teacher_name,
    m.course_name,
    m.course_number,
    m.section_number,
    m.scheduled,
    m.hos,

    a.student_number,
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

    coalesce(a.assessment_type, 'PM') as assessment_type,

    if(
        s.expected_grade_level = 0, 'K', cast(s.expected_grade_level as string)
    ) as expected_grade_level,

    if(
        a.measure_standard_score is null,
        null,
        if(a.measure_standard_score >= s.goal, true, false)
    ) as met_standard_goal,

    case
        when
            s.grade_level = '1'
            and s.expected_test = 'BOY->MOY'
            and s.expected_round in ('3', '4')
            and a.measure_standard_score is not null
        then mod.met_overall_goal
        when
            s.grade_level = '1'
            and s.expected_test = 'BOY->MOY'
            and s.expected_round in ('3', '4')
            and a.measure_standard_score is null
        then null
        when
            s.grade_level = '1'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '7'
            and a.measure_standard_score is not null
        then mod.met_overall_goal
        when
            s.grade_level = '1'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '7'
            and a.measure_standard_score is null
        then null
        when
            s.grade_level = '2'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '7'
            and a.measure_standard_score is not null
        then mod.met_overall_goal
        when
            s.grade_level = '2'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '7'
            and a.measure_standard_score is null
        then null
        when
            s.grade_level = '0'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '9'
            and a.measure_standard_score is not null
        then mod.met_overall_goal
        when
            s.grade_level = '0'
            and s.expected_test = 'MOY->EOY'
            and s.expected_round = '9'
            and a.measure_standard_score is null
        then null
        when a.measure_standard_score is null
        then null
        when a.measure_standard_score >= s.goal
        then true
    end as met_overall_goal,

    case
        when a.measure_standard_score is null
        then null
        when a.measure_standard_score >= s.admin_benchmark
        then true
        else false
    end as met_bm_goal,

from students as s
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.schoolid = m.cc_schoolid
    and s.student_number = m.schedule_student_number
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on s.academic_year = a.academic_year
    and s.student_number = a.student_number
    and s.expected_test = a.period
    and s.expected_measure_standard = a.measure_standard
    and a.client_date between s.start_date and s.end_date
    and a.assessment_type = 'PM'
left join
    met_overall_goal_calculation_modified as mod
    on s.academic_year = mod.academic_year
    and s.student_number = mod.student_number
    and s.expected_test = mod.expected_test
    and s.expected_round = mod.expected_round
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as f
    on s.academic_year = f.academic_year
    and s.student_number = f.student_number
    and {{ union_dataset_join_clause(left_alias="s", right_alias="f") }}
    and f.iready_subject = 'Reading'
