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
            and academic_year = '2022-2023'
            and subject = 'Reading'
    ),

    student_enrollment as (
        select *
        from {{ ref("base_powerschool__student_enrollments") }}  -- List only active students at or below 4th grade
        where
            academic_year = 2022
            and enroll_status = 0
            and rn_year = 1
            and grade_level <= 4
    ),

    student_schedule as (
        select *
        from {{ ref("base_powerschool__course_enrollments") }}  -- List students' active schedule for ELA courses only
        where
            cc_academic_year = 2022
            and not is_dropped_course
            and not is_dropped_section
            and rn_course_number_year = 1
            and courses_course_name
            in ('ELA GrK', 'ELA K', 'ELA Gr1', 'ELA Gr2', 'ELA Gr3', 'ELA Gr4')
    ),

    bm_summary as (
        select * from {{ ref("stg_amplify__benchmark_student_summary") }}  -- Brings the basic report for benchmark data for BOY, MOY and EOY
    -- where school_year = '2023-2024'
    ),

    unpivot_bm_summary as (
        select * from {{ ref("int_amplify__benchmark_student_summary_unpivot") }}  -- Brings the basic report for benchmark data for BOY, MOY and EOY in a pivot and grouped manner (to match pm_summary)
    ),

    pm_summary as (
        select * from {{ ref("stg_amplify__pm_student_summary") }}  -- Brings the probe data for the BOY-> MOY and MOY->EOY
    -- where school_year = '2023-2024'
    ),

    -- Logical CTEs
    student_k_2 as (
        select
            _dbt_source_relation,
            cast(academic_year as string) as academic_year,
            'KIPP NJ/MIAMI' as district,
            region,
            schoolid,
            school_name,
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
            e.school_name,
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

    schedules as (
        select
            c._dbt_source_relation,
            cast(c.cc_academic_year as string) as schedule_academic_year,
            'KIPP NJ/Miami' as schedule_district,
            e.region as schedule_region,
            c.cc_schoolid as schedule_school_id,
            e.student_number as student_number_schedule,  -- Needed to connect to MCLASS scores
            e.grade_level as schedule_student_grade_level,
            c.cc_teacherid as teacher_id,
            c.teacher_lastfirst as teacher_number,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,
            c.cc_section_number as section_number,
            e.advisory_name,
            period as expected_test
        from student_schedule as c
        left join
            student_enrollment as e
            on c.cc_academic_year = e.academic_year
            and c.cc_studentid = e.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="e") }}
        cross join unnest({{ periods }}) as period
    ),

    assessments_scores as (
        select
            left(bss.school_year, 4) as mclass_academic_year,  -- Needed to extract the academic year format that matches NJ's syntax
            bss.student_primary_id as mclass_student_number,
            'benchmark' as mclass_assessment_type,
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

    composite_only  -- Extract final composite by student per window
    as (
        select distinct
            mclass_academic_year,
            mclass_student_number,
            mclass_period,
            mclass_measure_level
        from assessments_scores
        where mclass_measure = 'Composite'
    ),

    overall_composite_by_window  -- Pivot final composite by student per window
    as (
        select distinct mclass_academic_year, mclass_student_number, p.boy, p.moy, p.eoy
        from
            composite_only pivot (
                max(mclass_measure_level) for mclass_period in ('BOY', 'MOY', 'EOY')
            ) as p
    ),

    probe_eligible_tag as (
        select distinct
            s.mclass_academic_year,
            s.mclass_student_number,
            c.boy,
            c.moy,
            c.eoy,
            s.mclass_period,
            case
                when boy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                when moy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                else 'No'
            end as probe_eligible
        from assessments_scores as s
        left join
            overall_composite_by_window as c
            on s.mclass_academic_year = c.mclass_academic_year
            and s.mclass_student_number = c.mclass_student_number
        where s.mclass_period not in ('BOY', 'MOY', 'EOY')
    ),

    assessment_counts as (
        select
            s.academic_year,
            s.schoolid,
            s.student_number,
            s.grade_level,
            m.schedule_academic_year,
            m.schedule_school_id,
            m.course_name,
            m.course_number,
            m.section_number,
            m.expected_test,
            m.student_number_schedule,
            m.schedule_student_grade_level,
            d.mclass_student_number,
            d.mclass_period,
            d.mclass_measure,
            d.mclass_measure_level,
            -- participation rates by school_course_section
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.section_number,
                    m.expected_test
            )
            as participation_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.section_number,
                    m.expected_test
            )
            as participation_school_course_section_bm_pm_period_total_students_scheduled,
            -- participation rates by school_course
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.expected_test
            ) as participation_school_course_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.expected_test
            ) as participation_school_course_bm_pm_period_total_students_scheduled,
            -- participation rates by school_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_school_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_school_grade_bm_pm_period_total_students_scheduled,
            -- participation rates by school
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year, m.schedule_school_id, m.expected_test
            ) as participation_school_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year, m.schedule_school_id, m.expected_test
            ) as participation_school_bm_pm_period_total_students_scheduled,
            -- participation rates by region_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_region_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_region_grade_bm_pm_period_total_students_scheduled,
            -- participation rates by region
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year, m.schedule_region, m.expected_test
            ) as participation_region_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year, m.schedule_region, m.expected_test
            ) as participation_region_bm_pm_period_total_students_scheduled,
            -- participation rates by district_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_district_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.schedule_student_grade_level,
                    m.expected_test
            ) as participation_district_grade_bm_pm_period_total_students_scheduled,
            -- participation rates by district
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year, m.schedule_district, m.expected_test
            ) as participation_district_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year, m.schedule_district, m.expected_test
            ) as participation_district_bm_pm_period_total_students_scheduled,
            -- measure level met rates by school_course_section
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.section_number,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_assessed
            ,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.section_number,
                    m.expected_test,
                    d.mclass_measure
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_scheduled

            ,
            -- measure level met rates by school_course
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_school_course_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.course_name,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_school_course_bm_pm_period_total_students_scheduled,
            -- measure level met rates by school_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_school_grade_bm_pm_period_total_students_scheduled,
            -- measure level met rates by school
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_school_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_school_id,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_school_bm_pm_period_total_students_scheduled,
            -- measure level met rates by region_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_region_grade_bm_pm_period_total_students_scheduled,
            -- measure level met rates by region
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_region_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_region,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_region_bm_pm_period_total_students_scheduled,
            -- measure level met rates by district_grade
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.schedule_student_grade_level,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_district_grade_bm_pm_period_total_students_scheduled,
            -- measure level met rates by district
            count(distinct d.mclass_student_number) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.expected_test,
                    d.mclass_measure,
                    d.mclass_measure_level
            ) as measure_level_met_district_bm_pm_period_total_students_assessed,
            count(distinct m.student_number_schedule) over (
                partition by
                    m.schedule_academic_year,
                    m.schedule_district,
                    m.expected_test,
                    d.mclass_measure
            ) as measure_level_met_district_bm_pm_period_total_students_scheduled

        from students as s
        left join
            schedules as m
            on s.academic_year = m.schedule_academic_year
            and s.student_number = m.student_number_schedule
        left join
            assessments_scores as d
            on m.schedule_academic_year = d.mclass_academic_year
            and m.student_number_schedule = d.mclass_student_number
            and m.expected_test = d.mclass_period  -- this last join on field is to ensure rows are generated for all expected tests, even if the student did not assess for them
    ),

    assessment_rates as (
        select
            *,
            safe_divide(
                participation_school_course_section_bm_pm_period_total_students_assessed,
                participation_school_course_section_bm_pm_period_total_students_scheduled
            ) as participation_school_course_section_bm_pm_period_percent,
            safe_divide(
                participation_school_course_bm_pm_period_total_students_assessed,
                participation_school_course_bm_pm_period_total_students_scheduled
            ) as participation_school_course_bm_pm_period_percent,
            safe_divide(
                participation_school_grade_bm_pm_period_total_students_assessed,
                participation_school_grade_bm_pm_period_total_students_scheduled
            ) as participation_school_grade_bm_pm_period_percent,
            safe_divide(
                participation_school_bm_pm_period_total_students_assessed,
                participation_school_bm_pm_period_total_students_scheduled
            ) as participation_school_bm_pm_period_percent,
            safe_divide(
                participation_region_grade_bm_pm_period_total_students_assessed,
                participation_region_grade_bm_pm_period_total_students_scheduled
            ) as participation_region_grade_bm_pm_period_percent,
            safe_divide(
                participation_region_bm_pm_period_total_students_assessed,
                participation_region_bm_pm_period_total_students_scheduled
            ) as participation_region_bm_pm_period_percent,
            safe_divide(
                participation_district_grade_bm_pm_period_total_students_assessed,
                participation_district_grade_bm_pm_period_total_students_scheduled
            ) as participation_district_grade_bm_pm_period_percent,
            safe_divide(
                participation_district_bm_pm_period_total_students_assessed,
                participation_district_bm_pm_period_total_students_scheduled
            ) as participation_district_bm_pm_period_percent,
            safe_divide(
                measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
                measure_level_met_school_course_section_bm_pm_period_total_students_scheduled
            ) as measure_level_met_school_course_section_bm_pm_period_percent,
            safe_divide(
                measure_level_met_school_course_bm_pm_period_total_students_assessed,
                measure_level_met_school_course_bm_pm_period_total_students_scheduled
            ) as measure_level_met_school_course_bm_pm_period_percent,
            safe_divide(
                measure_level_met_school_grade_bm_pm_period_total_students_assessed,
                measure_level_met_school_grade_bm_pm_period_total_students_scheduled
            ) as measure_level_met_school_grade_bm_pm_period_percent,
            safe_divide(
                measure_level_met_school_bm_pm_period_total_students_assessed,
                measure_level_met_school_bm_pm_period_total_students_scheduled
            ) as measure_level_met_school_bm_pm_period_percent,
            safe_divide(
                measure_level_met_region_grade_bm_pm_period_total_students_assessed,
                measure_level_met_region_grade_bm_pm_period_total_students_scheduled
            ) as measure_level_met_region_grade_bm_pm_period_percent,
            safe_divide(
                measure_level_met_region_bm_pm_period_total_students_assessed,
                measure_level_met_region_bm_pm_period_total_students_scheduled
            ) as measure_level_met_region_bm_pm_period_percent,
            safe_divide(
                measure_level_met_district_grade_bm_pm_period_total_students_assessed,
                measure_level_met_district_grade_bm_pm_period_total_students_scheduled
            ) as measure_level_met_district_grade_bm_pm_period_percent,
            safe_divide(
                measure_level_met_district_bm_pm_period_total_students_assessed,
                measure_level_met_district_bm_pm_period_total_students_scheduled
            ) as measure_level_met_district_bm_pm_period_percent
        from assessment_counts
    ),

    assessment_counts_and_rates_probe_tag as (
        select
            c.academic_year,
            c.schoolid,
            c.student_number,
            c.grade_level,
            c.schedule_academic_year,
            c.schedule_school_id,
            c.course_name,
            c.course_number,
            c.section_number,
            c.expected_test,
            c.student_number_schedule,
            c.schedule_student_grade_level,
            c.mclass_student_number,
            c.mclass_period,
            c.mclass_measure,
            c.mclass_measure_level,
            c.participation_school_course_section_bm_pm_period_total_students_assessed,
            c.participation_school_course_section_bm_pm_period_total_students_scheduled,
            c.participation_school_course_bm_pm_period_total_students_assessed,
            c.participation_school_course_bm_pm_period_total_students_scheduled,
            c.participation_school_grade_bm_pm_period_total_students_assessed,
            c.participation_school_grade_bm_pm_period_total_students_scheduled,
            c.participation_school_bm_pm_period_total_students_assessed,
            c.participation_school_bm_pm_period_total_students_scheduled,
            c.participation_region_grade_bm_pm_period_total_students_assessed,
            c.participation_region_grade_bm_pm_period_total_students_scheduled,
            c.participation_region_bm_pm_period_total_students_assessed,
            c.participation_region_bm_pm_period_total_students_scheduled,
            c.participation_district_grade_bm_pm_period_total_students_assessed,
            c.participation_district_grade_bm_pm_period_total_students_scheduled,
            c.participation_district_bm_pm_period_total_students_assessed,
            c.participation_district_bm_pm_period_total_students_scheduled,
            c.measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            c.measure_level_met_school_course_section_bm_pm_period_total_students_scheduled,
            c.measure_level_met_school_course_bm_pm_period_total_students_assessed,
            c.measure_level_met_school_course_bm_pm_period_total_students_scheduled,
            c.measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            c.measure_level_met_school_grade_bm_pm_period_total_students_scheduled,
            c.measure_level_met_school_bm_pm_period_total_students_assessed,
            c.measure_level_met_school_bm_pm_period_total_students_scheduled,
            c.measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            c.measure_level_met_region_grade_bm_pm_period_total_students_scheduled,
            c.measure_level_met_region_bm_pm_period_total_students_assessed,
            c.measure_level_met_region_bm_pm_period_total_students_scheduled,
            c.measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            c.measure_level_met_district_grade_bm_pm_period_total_students_scheduled,
            c.measure_level_met_district_bm_pm_period_total_students_assessed,
            c.measure_level_met_district_bm_pm_period_total_students_scheduled,
            r.participation_school_course_section_bm_pm_period_percent,
            r.participation_school_course_bm_pm_period_percent,
            r.participation_school_grade_bm_pm_period_percent,
            r.participation_school_bm_pm_period_percent,
            r.participation_region_grade_bm_pm_period_percent,
            r.participation_region_bm_pm_period_percent,
            r.participation_district_grade_bm_pm_period_percent,
            r.participation_district_bm_pm_period_percent,
            r.measure_level_met_school_course_section_bm_pm_period_percent,
            r.measure_level_met_school_course_bm_pm_period_percent,
            r.measure_level_met_school_grade_bm_pm_period_percent,
            r.measure_level_met_school_bm_pm_period_percent,
            r.measure_level_met_region_grade_bm_pm_period_percent,
            r.measure_level_met_region_bm_pm_period_percent,
            r.measure_level_met_district_grade_bm_pm_period_percent,
            r.measure_level_met_district_bm_pm_period_percent,
            p.probe_eligible,
            p.boy as boy_composite,
            p.moy as moy_composite,
            p.eoy as eoy_composite
        from assessment_counts as c
        left join
            assessment_rates as r
            on c.academic_year = r.academic_year
            and c.schoolid = r.schoolid
            and c.grade_level = r.grade_level
            and c.course_number = r.course_number
            and c.section_number = r.section_number
            and c.expected_test = r.expected_test
            and c.mclass_measure = r.mclass_measure
            and c.mclass_measure_level = r.mclass_measure_level
        left join
            probe_eligible_tag as p
            on c.academic_year = p.mclass_academic_year
            and c.student_number = p.mclass_student_number
            and c.mclass_period = p.mclass_period
    ),

    base_roster as (
        select
            s.academic_year,
            m.schedule_academic_year,
            s.district,
            m.schedule_district,
            s.region,
            m.schedule_region,
            s.schoolid,
            m.schedule_school_id,
            s.school_name,
            s.school_abbreviation,
            s.student_number,
            m.student_number_schedule,
            s.student_name,
            s.student_last_name,
            s.student_first_name,
            s.grade_level,
            m.schedule_student_grade_level,
            s.ood,
            s.gender,
            s.ethnicity,
            s.homeless,
            s.is_504,
            s.sped,
            s.lep,
            s.lunch_status,
            m.teacher_id,
            m.teacher_name,
            m.course_name,
            m.course_number,
            m.section_number,
            m.advisory_name,
            m.expected_test,
        from students as s
        left join
            schedules as m
            on s.academic_year = m.schedule_academic_year
            and s.student_number = m.student_number_schedule
    ),

    -- Final CTE
    final as (
        select
            b.academic_year,
            b.schedule_academic_year,
            b.district,
            b.schedule_district,
            b.region,
            b.schedule_region,
            b.schoolid,
            b.schedule_school_id,
            b.school_name,
            b.school_abbreviation,
            b.student_number,
            b.student_number_schedule,
            b.student_name,
            b.student_last_name,
            b.student_first_name,
            b.grade_level,
            b.schedule_student_grade_level,
            b.ood,
            b.gender,
            b.ethnicity,
            b.homeless,
            b.is_504,
            b.sped,
            b.lep,
            b.lunch_status,
            b.teacher_id,
            b.teacher_name,
            b.course_name,
            b.course_number,
            b.section_number,
            b.advisory_name,
            b.expected_test,
            a.mclass_student_number,
            a.mclass_period,
            a.mclass_measure,
            a.mclass_measure_level,
            a.participation_school_course_section_bm_pm_period_total_students_assessed,
            a.participation_school_course_section_bm_pm_period_total_students_scheduled,
            a.participation_school_course_bm_pm_period_total_students_assessed,
            a.participation_school_course_bm_pm_period_total_students_scheduled,
            a.participation_school_grade_bm_pm_period_total_students_assessed,
            a.participation_school_grade_bm_pm_period_total_students_scheduled,
            a.participation_school_bm_pm_period_total_students_assessed,
            a.participation_school_bm_pm_period_total_students_scheduled,
            a.participation_region_grade_bm_pm_period_total_students_assessed,
            a.participation_region_grade_bm_pm_period_total_students_scheduled,
            a.participation_region_bm_pm_period_total_students_assessed,
            a.participation_region_bm_pm_period_total_students_scheduled,
            a.participation_district_grade_bm_pm_period_total_students_assessed,
            a.participation_district_grade_bm_pm_period_total_students_scheduled,
            a.participation_district_bm_pm_period_total_students_assessed,
            a.participation_district_bm_pm_period_total_students_scheduled,
            a.measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            a.measure_level_met_school_course_section_bm_pm_period_total_students_scheduled,
            a.measure_level_met_school_course_bm_pm_period_total_students_assessed,
            a.measure_level_met_school_course_bm_pm_period_total_students_scheduled,
            a.measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            a.measure_level_met_school_grade_bm_pm_period_total_students_scheduled,
            a.measure_level_met_school_bm_pm_period_total_students_assessed,
            a.measure_level_met_school_bm_pm_period_total_students_scheduled,
            a.measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            a.measure_level_met_region_grade_bm_pm_period_total_students_scheduled,
            a.measure_level_met_region_bm_pm_period_total_students_assessed,
            a.measure_level_met_region_bm_pm_period_total_students_scheduled,
            a.measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            a.measure_level_met_district_grade_bm_pm_period_total_students_scheduled,
            a.measure_level_met_district_bm_pm_period_total_students_assessed,
            a.measure_level_met_district_bm_pm_period_total_students_scheduled,
            a.participation_school_course_section_bm_pm_period_percent,
            a.participation_school_course_bm_pm_period_percent,
            a.participation_school_grade_bm_pm_period_percent,
            a.participation_school_bm_pm_period_percent,
            a.participation_region_grade_bm_pm_period_percent,
            a.participation_region_bm_pm_period_percent,
            a.participation_district_grade_bm_pm_period_percent,
            a.participation_district_bm_pm_period_percent,
            a.measure_level_met_school_course_section_bm_pm_period_percent,
            a.measure_level_met_school_course_bm_pm_period_percent,
            a.measure_level_met_school_grade_bm_pm_period_percent,
            a.measure_level_met_school_bm_pm_period_percent,
            a.measure_level_met_region_grade_bm_pm_period_percent,
            a.measure_level_met_region_bm_pm_period_percent,
            a.measure_level_met_district_grade_bm_pm_period_percent,
            a.measure_level_met_district_bm_pm_period_percent,
            a.probe_eligible,
            a.boy_composite,
            a.moy_composite,
            a.eoy_composite
        from base_roster as b
        left join
            assessment_counts_and_rates_probe_tag as a
            on b.academic_year = a.academic_year
            and b.schoolid = a.schoolid
            and b.grade_level = a.grade_level
            and b.course_number = a.course_number
            and b.section_number = a.section_number
            and b.expected_test = a.expected_test
    )

select *
from final