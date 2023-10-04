{% set periods = ["BOY", "BOY->MOY", "MOY", "MOY->EOY", "EOY"] %}  -- Force expected assessments

-- Import CTEs
with
    iready_roster as (
        select *
        from {{ ref("base_iready__diagnostic_results") }}  -- Lists eligible 3rd and 4th students to take DIBELS based on iReady BOY placement
        where
            test_round = 'BOY'
            and student_grade in ('3', '4')
            and rn_subj_round = 1
            and overall_relative_placement_int <= 2
            and left(academic_year, 4)
            = cast({{ var("current_academic_year") }} as string)
            and subject = 'Reading'
    ),

    student_enrollment as (
        select *
        from {{ ref("base_powerschool__student_enrollments") }}  -- List only active students at or below 4th grade
        where
            academic_year = {{ var("current_academic_year") }}
            and enroll_status = 0
            and rn_year = 1
            and grade_level <= 4
    ),

    student_schedule as (
        select *
        from {{ ref("base_powerschool__course_enrollments") }}  -- List students' active schedule for ELA courses only
        where
            cc_academic_year = {{ var("current_academic_year") }}
            and not is_dropped_course
            and not is_dropped_section
            and rn_course_number_year = 1
            and courses_course_name
            in ('ELA GrK', 'ELA K', 'ELA Gr1', 'ELA Gr2', 'ELA Gr3', 'ELA Gr4')
    ),

    bm_summary as (
        select *
        from {{ ref("stg_amplify__benchmark_student_summary") }}  -- Brings the basic report for benchmark data for BOY, MOY and EOY
        where academic_year = {{ var("current_academic_year") }}
    ),

    unpivot_bm_summary as (
        select * from {{ ref("int_amplify__benchmark_student_summary_unpivot") }}  -- Brings the basic report for benchmark data for BOY, MOY and EOY in a pivot and grouped manner (to match pm_summary)
    ),

    pm_summary as (
        select *
        from {{ ref("stg_amplify__pm_student_summary") }}  -- Brings the probe data for the BOY-> MOY and MOY->EOY
        where academic_year = {{ var("current_academic_year") }}
    ),

    -- Logical CTEs
    student_k_2 as (
        select
            _dbt_source_relation,
            cast(academic_year as string) as academic_year,
            'KIPP NJ/MIAMI' as district,
            region,
            schoolid,
            school_name as school,
            school_abbreviation,
            student_number,
            studentid,
            lastfirst as student_name,
            first_name as student_first_name,
            last_name as student_last_name,
            case
                when cast(grade_level as string) = '0'
                then 'K'
                else cast(grade_level as string)
            end as grade_level,
            case when is_out_of_district = true then 1 else 0 end as ood,
            gender,
            ethnicity,
            case when is_homeless = true then 1 else 0 end as homeless,
            case when is_504 = true then 1 else 0 end as is_504,
            case when spedlep in ('No IEP', null) then 0 else 1 end as sped,
            case when lep_status = true then 1 else 0 end as lep,
            lunch_status as lunch_status
        from student_enrollment
        where grade_level <= 2
    ),

    student_3_4 as (
        select
            _dbt_source_relation,
            cast(e.academic_year as string) as academic_year,
            'KIPP NJ/MIAMI' as district,
            e.region,
            e.schoolid,
            e.school_name as school,
            e.school_abbreviation,
            e.student_number,
            e.studentid,
            e.lastfirst as student_name,
            e.first_name as student_first_name,
            e.last_name as student_last_name,
            cast(e.grade_level as string) as grade_level,
            case when e.is_out_of_district = true then 1 else 0 end as ood,
            e.gender,
            e.ethnicity,
            case when e.is_homeless = true then 1 else 0 end as homeless,
            case when e.is_504 = true then 1 else 0 end as is_504,
            case when e.spedlep in ('No IEP', null) then 0 else 1 end as sped,
            case when e.lep_status = true then 1 else 0 end as lep,
            e.lunch_status as lunch_status
        from student_enrollment as e
        inner join iready_roster as i on e.student_number = i.student_id
        where
            e.grade_level > 2
            and e.student_number in (select distinct student_id from iready_roster)
    ),

    students as (
        select *
        from student_k_2
        union all
        select *
        from student_3_4
    ),

    student_number as (
        select
            e._dbt_source_relation,
            cast(e.academic_year as string) as academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation,
            e.school_name,
            e.studentid,
            e.student_number,
            e.enroll_status,
            e.advisory_name
        from student_enrollment e
    ),

    schedules as (
        select
            c._dbt_source_relation,
            cast(c.cc_academic_year as string) as schedule_academic_year,
            'KIPP NJ/Miami' as schedule_district,
            e.region as schedule_region,
            c.cc_schoolid as schedule_schoolid,
            case
                when c.courses_course_name in ('ELA GrK', 'ELA K')
                then 'K'
                when c.courses_course_name = 'ELA Gr1'
                then '1'
                when c.courses_course_name = 'ELA Gr2'
                then '2'
                when c.courses_course_name = 'ELA Gr3'
                then '3'
                when c.courses_course_name = 'ELA Gr4'
                then '4'
            end as schedule_student_grade_level,
            e.student_number as schedule_student_number,  -- Needed to connect to MCLASS scores
            c.cc_teacherid as teacherid,
            c.teacher_lastfirst as teacher_number,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,
            c.cc_section_number as section_number,
            e.advisory_name,
            period as expected_test,
            1 as scheduled
        from student_schedule as c
        left join
            student_number as e
            on cast(c.cc_academic_year as string) = e.academic_year
            and c.cc_studentid = e.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="e") }}
        cross join unnest({{ periods }}) as period
    ),

    assessments_scores as (
        select
            left(bss.school_year, 4) as mclass_academic_year,  -- Needed to extract the academic year format that matches NJ's syntax
            bss.student_primary_id as mclass_student_number,
            'benchmark' as mclass_assessment_type,
            bss.assessment_grade as mclass_assessment_grade,
            bss.benchmark_period as mclass_period,
            bss.client_date as mclass_client_date,
            bss.sync_date as mclass_sync_date,

            u.measure as mclass_measure,
            u.score as mclass_measure_score,
            u.level as mclass_measure_level,
            case
                when u.level = 'Above Benchmark'
                then 4
                when u.level = 'At Benchmark'
                then 3
                when u.level = 'Below Benchmark'
                then 2
                when u.level = 'Well Below Benchmark'
                then 1
                else null
            end as mclass_measure_level_int,
            u.national_norm_percentile as mclass_measure_percentile,
            u.semester_growth as mclass_measure_semester_growth,
            u.year_growth as mclass_measure_year_growth,

            null as mclass_probe_number,
            null as mclass_total_number_of_probes,
            null as mclass_score_change

        from bm_summary as bss
        inner join unpivot_bm_summary as u on bss.surrogate_key = u.surrogate_key

        union all

        select
            left(school_year, 4) as mclass_academic_year,  -- Needed to extract the academic year format that matches NJ's syntax
            student_primary_id as mclass_student_number,
            'pm' as mclass_assessment_type,
            cast(assessment_grade as string) as mclass_assessment_grade,
            pm_period as mclass_period,
            client_date as mclass_client_date,
            sync_date as mclass_sync_date,

            measure as mclass_measure,
            score as mclass_measure_score,
            null as mclass_measure_level,
            null mclass_measure_level_int,
            null as mclass_measure_percentile,
            null as mclass_measure_semester_growth,
            null as mclass_measure_year_growth,

            probe_number as mclass_probe_number,
            total_number_of_probes as mclass_total_number_of_probes,
            score_change as mclass_score_change
        from pm_summary
    ),

    students_and_schedules as (
        select * except (_dbt_source_relation, studentid)
        from students as s
        left join
            schedules as m
            on s.academic_year = m.schedule_academic_year
            and s.schoolid = m.schedule_schoolid
            and s.student_number = m.schedule_student_number
    ),

    students_schedules_and_assessments_scores as (
        select
            *,
            -- participation rates by school_course_section
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.section_number,
                    s.expected_test
            ) as participation_school_course_section_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.section_number,
                    s.expected_test
            ) as participation_school_course_section_bm_total_students_scheduled,
            -- participation rates by school_course
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.expected_test
            ) as participation_school_course_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.expected_test
            ) as participation_school_course_bm_total_students_scheduled,
            -- participation rates by school_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_school_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_school_grade_bm_total_students_scheduled,
            -- participation rates by school
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_schoolid, s.expected_test
            ) as participation_school_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_schoolid, s.expected_test
            ) as participation_school_bm_total_students_scheduled,
            -- participation rates by region_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_region_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_region_grade_bm_total_students_scheduled,
            -- participation rates by region
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_region, s.expected_test
            ) as participation_region_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_region, s.expected_test
            ) as participation_region_bm_total_students_scheduled,
            -- participation rates by district_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_district_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.schedule_student_grade_level,
                    s.expected_test
            ) as participation_district_grade_bm_total_students_scheduled,
            -- participation rates by district
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_district, s.expected_test
            ) as participation_district_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year, s.schedule_district, s.expected_test
            ) as participation_district_bm_total_students_scheduled,
            -- measure level met rates by school_course_section
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.section_number,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_school_course_section_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.section_number,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_school_course_section_bm_total_students_scheduled,
            -- measure level met rates by school_course
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_school_course_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.course_name,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_school_course_bm_total_students_scheduled,
            -- measure level met rates by school_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_school_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_school_grade_bm_total_students_scheduled,
            -- measure level met rates by school
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_school_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_schoolid,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_school_bm_total_students_scheduled,
            -- measure level met rates by region_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_region_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_region_grade_bm_total_students_scheduled,
            -- measure level met rates by region
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_region_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_region,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_region_bm_total_students_scheduled,
            -- measure level met rates by district_grade
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_district_grade_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.schedule_student_grade_level,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_district_grade_bm_total_students_scheduled,
            -- measure level met rates by district
            count(distinct a.mclass_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.expected_test,
                    a.mclass_measure,
                    a.mclass_measure_level
            ) as measure_level_met_district_bm_total_students_assessed,
            count(distinct s.schedule_student_number) over (
                partition by
                    s.schedule_academic_year,
                    s.schedule_district,
                    s.expected_test,
                    a.mclass_measure
            ) as measure_level_met_district_bm_total_students_scheduled
        from students_and_schedules as s
        left join
            assessments_scores as a
            on s.schedule_academic_year = a.mclass_academic_year
            and s.schedule_student_number = a.mclass_student_number
            and s.expected_test = a.mclass_period
    ),

    composite_only  -- Extract final composite by student per window
    as (
        select distinct
            academic_year, student_number, expected_test, mclass_measure_level
        from students_schedules_and_assessments_scores
        where mclass_measure = 'Composite'
    ),

    overall_composite_by_window  -- Pivot final composite by student per window
    as (
        select distinct academic_year, student_number, p.boy, p.moy, p.eoy
        from
            composite_only pivot (
                max(mclass_measure_level) for expected_test in ('BOY', 'MOY', 'EOY')
            ) as p
    ),

    probe_eligible_tag as (
        select distinct
            s.academic_year,
            s.student_number,
            c.boy,
            c.moy,
            c.eoy,
            case
                when boy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                when boy is null
                then 'No data'
                else 'No'
            end as boy_probe_eligible,
            case
                when moy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                when moy is null
                then 'No data'
                else 'No'
            end as moy_probe_eligible
        from students_schedules_and_assessments_scores as s
        left join
            overall_composite_by_window as c
            on s.academic_year = c.academic_year
            and s.student_number = c.student_number
    ),

    base_roster as (
        select
            s.academic_year,
            s.district,
            s.region,
            s.schoolid,
            s.school,
            s.school_abbreviation,
            s.student_number,
            s.student_name,
            s.student_last_name,
            s.student_first_name,
            s.grade_level,
            s.schedule_academic_year,
            s.schedule_district,
            s.schedule_region,
            s.schedule_schoolid,
            s.schedule_student_number,
            s.schedule_student_grade_level,
            s.ood,
            s.gender,
            s.ethnicity,
            s.homeless,
            s.is_504,
            s.sped,
            s.lep,
            s.lunch_status,
            s.teacherid,
            s.teacher_name,
            s.course_name,
            s.course_number,
            s.section_number,
            s.advisory_name,
            s.expected_test,
            coalesce(s.scheduled, 0) as scheduled,
            s.mclass_student_number,
            s.mclass_assessment_grade,
            s.mclass_period,
            s.mclass_client_date,
            s.mclass_sync_date,
            coalesce(p.boy, 'No data') as boy_composite,
            coalesce(p.moy, 'No data') as moy_composite,
            coalesce(p.eoy, 'No data') as eoy_composite,
            coalesce(s.mclass_probe_number, 0) as mclass_probe_number,
            coalesce(
                s.mclass_total_number_of_probes, 0
            ) as mclass_total_number_of_probes,
            p.boy_probe_eligible,
            p.moy_probe_eligible,
            case
                when p.boy_probe_eligible = 'Yes' and s.expected_test = 'BOY->MOY'
                then p.boy_probe_eligible
                when p.moy_probe_eligible = 'Yes' and s.expected_test = 'MOY->EOY'
                then p.moy_probe_eligible
                when p.boy_probe_eligible = 'No' and s.expected_test = 'BOY->MOY'
                then 'No'
                when p.moy_probe_eligible = 'No' and s.expected_test = 'MOY->EOY'
                then 'No'
                else 'Not applicable'
            end as pm_probe_eligible,
            case
                when
                    p.boy_probe_eligible = 'Yes'
                    and s.expected_test = 'BOY->MOY'
                    and s.mclass_total_number_of_probes is not null
                then 'Yes'
                when
                    p.moy_probe_eligible = 'Yes'
                    and s.expected_test = 'MOY->EOY'
                    and s.mclass_total_number_of_probes is not null
                then 'Yes'
                when
                    p.boy_probe_eligible = 'Yes'
                    and s.expected_test = 'BOY->MOY'
                    and s.mclass_total_number_of_probes is null
                then 'No'
                when
                    p.moy_probe_eligible = 'Yes'
                    and s.expected_test = 'MOY->EOY'
                    and s.mclass_total_number_of_probes is null
                then 'No'
                else 'Not applicable'
            end as pm_probe_tested,
            s.mclass_measure,
            s.mclass_measure_score,
            s.mclass_score_change,
            s.mclass_measure_level,
            s.mclass_measure_level_int,
            s.mclass_measure_percentile,
            s.mclass_measure_semester_growth,
            s.mclass_measure_year_growth,
            participation_school_course_section_bm_total_students_assessed,
            participation_school_course_section_bm_total_students_scheduled,
            participation_school_course_bm_total_students_assessed,
            participation_school_course_bm_total_students_scheduled,
            participation_school_grade_bm_total_students_assessed,
            participation_school_grade_bm_total_students_scheduled,
            participation_school_bm_total_students_assessed,
            participation_school_bm_total_students_scheduled,
            participation_region_grade_bm_total_students_assessed,
            participation_region_grade_bm_total_students_scheduled,
            participation_region_bm_total_students_assessed,
            participation_region_bm_total_students_scheduled,
            participation_district_grade_bm_total_students_assessed,
            participation_district_grade_bm_total_students_scheduled,
            participation_district_bm_total_students_assessed,
            participation_district_bm_total_students_scheduled,
            measure_level_met_school_course_section_bm_total_students_assessed,
            measure_level_met_school_course_section_bm_total_students_scheduled,
            measure_level_met_school_course_bm_total_students_assessed,
            measure_level_met_school_course_bm_total_students_scheduled,
            measure_level_met_school_grade_bm_total_students_assessed,
            measure_level_met_school_grade_bm_total_students_scheduled,
            measure_level_met_school_bm_total_students_assessed,
            measure_level_met_school_bm_total_students_scheduled,
            measure_level_met_region_grade_bm_total_students_assessed,
            measure_level_met_region_grade_bm_total_students_scheduled,
            measure_level_met_region_bm_total_students_assessed,
            measure_level_met_region_bm_total_students_scheduled,
            measure_level_met_district_grade_bm_total_students_assessed,
            measure_level_met_district_grade_bm_total_students_scheduled,
            measure_level_met_district_bm_total_students_assessed,
            measure_level_met_district_bm_total_students_scheduled,
            safe_divide(
                participation_school_course_section_bm_total_students_assessed,
                participation_school_course_section_bm_total_students_scheduled
            ) as participation_school_course_section_bm_total_percent,
            safe_divide(
                participation_school_course_bm_total_students_assessed,
                participation_school_course_bm_total_students_scheduled
            ) as participation_school_course_bm_total_percent,
            safe_divide(
                participation_school_grade_bm_total_students_assessed,
                participation_school_grade_bm_total_students_scheduled
            ) as participation_school_grade_bm_total_percent,
            safe_divide(
                participation_school_bm_total_students_assessed,
                participation_school_bm_total_students_scheduled
            ) as participation_school_bm_total_percent,
            safe_divide(
                participation_region_grade_bm_total_students_assessed,
                participation_region_grade_bm_total_students_scheduled
            ) as participation_region_grade_bm_total_percent,
            safe_divide(
                participation_region_bm_total_students_assessed,
                participation_region_bm_total_students_scheduled
            ) as participation_region_bm_total_percent,
            safe_divide(
                participation_district_grade_bm_total_students_assessed,
                participation_district_grade_bm_total_students_scheduled
            ) as participation_district_grade_bm_total_percent,
            safe_divide(
                participation_district_bm_total_students_assessed,
                participation_district_bm_total_students_scheduled
            ) as participation_district_bm_total_percent,
            safe_divide(
                measure_level_met_school_course_section_bm_total_students_assessed,
                measure_level_met_school_course_section_bm_total_students_scheduled
            ) as measure_level_met_school_course_section_bm_total_percent,
            safe_divide(
                measure_level_met_school_course_bm_total_students_assessed,
                measure_level_met_school_course_bm_total_students_scheduled
            ) as measure_level_met_school_course_bm_total_percent,
            safe_divide(
                measure_level_met_school_grade_bm_total_students_assessed,
                measure_level_met_school_grade_bm_total_students_scheduled
            ) as measure_level_met_school_grade_bm_total_percent,
            safe_divide(
                measure_level_met_school_bm_total_students_assessed,
                measure_level_met_school_bm_total_students_scheduled
            ) as measure_level_met_school_bm_total_percent,
            safe_divide(
                measure_level_met_region_grade_bm_total_students_assessed,
                measure_level_met_region_grade_bm_total_students_scheduled
            ) as measure_level_met_region_grade_bm_total_percent,
            safe_divide(
                measure_level_met_region_bm_total_students_assessed,
                measure_level_met_region_bm_total_students_scheduled
            ) as measure_level_met_region_bm_total_percent,
            safe_divide(
                measure_level_met_district_grade_bm_total_students_assessed,
                measure_level_met_district_grade_bm_total_students_scheduled
            ) as measure_level_met_district_grade_bm_total_percent,
            safe_divide(
                measure_level_met_district_bm_total_students_assessed,
                measure_level_met_district_bm_total_students_scheduled
            ) as measure_level_met_district_bm_total_percent

        from students_schedules_and_assessments_scores as s
        left join
            probe_eligible_tag as p
            on s.academic_year = p.academic_year
            and s.student_number = p.student_number
    )

select *
from base_roster
