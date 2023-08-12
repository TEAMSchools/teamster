{% set periods = ["BOY", "BOY->MOY", "MOY", "MOY->EOY", "EOY"] %}

with
    union_relations as (
        select
            bss.surrogate_key,
            bss.student_primary_id,
            bss.academic_year,
            bss.benchmark_period as period,
            bss.client_date,
            bss.sync_date,
            bss.reporting_class_id,
            bss.reporting_class_name,
            bss.assessing_teacher_staff_id,
            bss.assessing_teacher_name,
            bss.official_teacher_staff_id,
            bss.official_teacher_name,
            bss.assessment_grade,

            u.measure,
            u.score,
            u.level,
            u.national_norm_percentile,
            u.semester_growth,
            u.year_growth,

            null as score_change,
            null as probe_number,
            null as total_number_of_probes,

            'benchmark' as assessment_type,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key

        union all

        select
            surrogate_key,
            student_primary_id,
            academic_year,
            pm_period as period,
            client_date,
            sync_date,
            reporting_class_id,
            reporting_class_name,
            assessing_teacher_staff_id,
            assessing_teacher_name,
            official_teacher_staff_id,
            official_teacher_name,
            assessment_grade,
            measure,
            score,
            null as level,
            null as percentile,
            null as semester_growth,
            null as year_growth,
            score_change,
            probe_number,
            total_number_of_probes,

            'pm' as assessment_type,
        from {{ ref("stg_amplify__pm_student_summary") }}
    ),

    student_schedule_test as (
        select
            se.student_number,
            se.first_name,
            se.last_name,
            se.lastfirst,
            se.academic_year,
            se.region,
            se.school_level,
            se.schoolid,
            se.school_name,
            se.school_abbreviation,
            se.grade_level,
            se.gender,
            se.ethnicity,
            se.lunch_status,
            se.is_out_of_district,
            se.is_homeless,
            se.is_504,
            se.lep_status as is_lep,
            if(spedlep = 'No IEP' or se.spedlep is null, false, true) as is_sped,

            ce.cc_course_number as course_number,
            ce.cc_section_number as section_number,
            ce.cc_teacherid as teacher_id,
            ce.courses_course_name as course_name,
            ce.teachernumber as teacher_number,
            ce.teacher_lastfirst as teacher_name,
            if(ce.cc_studentid is null, true, false) as enrolled_but_not_scheduled,

            period,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref("base_powerschool__course_enrollments") }} as ce
            on se.studentid = ce.cc_studentid
            and se.yearid = ce.cc_yearid
            and ce.rn_course_number_year = 1
            and not ce.is_dropped_section
            and ce.courses_course_name
            in ('ELA GrK', 'ELA K', 'ELA Gr1', 'ELA Gr2', 'ELA Gr3', 'ELA Gr4')
        cross join unnest({{ periods }}) as period
        where se.rn_year = 1 and se.academic_year >= 2022 and se.grade_level <= 4
    ),

    student_data as (
        select
            s.student_number,
            s.lastfirst,
            s.last_name,
            s.first_name,
            s.academic_year,
            s.region,
            s.school_level,
            s.schoolid,
            s.school_name,
            s.school_abbreviation,
            s.grade_level,
            s.gender,
            s.ethnicity,
            s.lunch_status,
            s.is_out_of_district,
            s.is_sped,
            s.is_504,
            s.is_lep,
            s.is_homeless,
            s.teacher_id,
            s.teacher_name,
            s.course_number,
            s.course_name,
            s.section_number,
            s.period,

            -- Tagging students as enrolled in school but not scheduled for the course
            -- that would allow them to take the DIBELS test
            d.assessment_type,
            d.client_date,
            d.sync_date,
            d.reporting_class_id,
            d.reporting_class_name,
            d.assessment_grade,
            d.assessing_teacher_staff_id,
            d.assessing_teacher_name,
            d.official_teacher_staff_id,
            d.official_teacher_name,
            d.measure,
            d.score,
            d.level,
            d.national_norm_percentile,
            d.semester_growth,
            d.year_growth,
            d.score_change,
            d.probe_number,
            d.total_number_of_probes,
            if(
                d.student_primary_id is not null, true, false
            ) as student_has_assessment_data,

            'KIPP NJ/Miami' as district,
        from student_schedule_test as s
        left join
            union_relations as d
            on s.student_number = d.student_primary_id
            and s.academic_year = d.academic_year
            and s.period = d.period
    ),

    with_counts as (
        select
            *,

            -- Participation rates by School_Course_Section
            count(distinct student_number) over (
                partition by
                    academic_year, school_id, course_name, section_number, expected_test
            )
            as participation_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, course_name, section_number, school_id, expected_test
            )
            as participation_school_course_section_bm_pm_period_total_students_enrolled,

            -- Participation rates by School_Course
            count(distinct student_number) over (
                partition by academic_year, school_id, course_name, expected_test
            ) as participation_school_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, course_name, expected_test
            ) as participation_school_course_bm_pm_period_total_students_enrolled,

            -- Participation rates by School_Grade
            count(distinct student_number) over (
                partition by academic_year, school_id, grade_level, expected_test
            ) as participation_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, grade_level, expected_test
            ) as participation_school_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by School
            count(distinct student_number) over (
                partition by academic_year, school_id, expected_test
            ) as participation_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test
            ) as participation_school_bm_pm_period_total_students_enrolled,

            -- Participation rates by Region_Grade
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, expected_test
            ) as participation_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, grade_level, expected_test
            ) as participation_region_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by Region
            count(distinct student_number) over (
                partition by academic_year, region, expected_test
            ) as participation_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test
            ) as participation_region_bm_pm_period_total_students_enrolled,

            -- Participation rates by District_Grade
            count(distinct student_number) over (
                partition by academic_year, district, expected_test
            ) as participation_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test
            ) as participation_district_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by District
            count(distinct student_number) over (
                partition by academic_year, district, expected_test
            ) as participation_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test
            ) as participation_district_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Course_Section
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    measure,
                    measure_score
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    measure
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Course
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    expected_test,
                    measure,
                    measure_score
            )
            as measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, course_name, expected_test, measure
            ) as measure_score_met_school_course_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Grade
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    grade_level,
                    expected_test,
                    measure,
                    measure_score
            ) as measure_score_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, grade_level, expected_test, measure
            ) as measure_score_met_school_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School
            count(distinct student_number) over (
                partition by
                    academic_year, school_id, expected_test, measure, measure_score
            ) as measure_score_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test, measure
            ) as measure_score_met_school_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by Region_Grade
            count(distinct student_number) over (
                partition by
                    academic_year,
                    region,
                    grade_level,
                    expected_test,
                    measure,
                    measure_score
            ) as measure_score_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, grade_level, expected_test, measure
            ) as measure_score_met_region_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by Region
            count(distinct student_number) over (
                partition by
                    academic_year, region, expected_test, measure, measure_score
            ) as measure_score_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test, measure
            ) as measure_score_met_region_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by District_Grade
            count(distinct student_number) over (
                partition by
                    academic_year, district, expected_test, measure, measure_score
            ) as measure_score_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, measure
            ) as measure_score_met_district_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by District
            count(distinct student_number) over (
                partition by
                    academic_year, district, expected_test, measure, measure_score
            ) as measure_score_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, measure
            ) as measure_score_met_district_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Course_Section
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    measure,
                    measure_level
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    measure
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Course
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    expected_test,
                    measure,
                    measure_level
            )
            as measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, course_name, expected_test, measure
            ) as measure_level_met_school_course_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Grade
            count(distinct student_number) over (
                partition by
                    academic_year,
                    school_id,
                    grade_level,
                    expected_test,
                    measure,
                    measure_level
            ) as measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, grade_level, expected_test, measure
            ) as measure_level_met_school_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School
            count(distinct student_number) over (
                partition by
                    academic_year, school_id, expected_test, measure, measure_level
            ) as measure_level_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test, measure
            ) as measure_level_met_school_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by Region_Grade
            count(distinct student_number) over (
                partition by
                    academic_year,
                    region,
                    grade_level,
                    expected_test,
                    measure,
                    measure_level
            ) as measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, grade_level, expected_test, measure
            ) as measure_level_met_region_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by Region
            count(distinct student_number) over (
                partition by
                    academic_year, region, expected_test, measure, measure_level
            ) as measure_level_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test, measure
            ) as measure_level_met_region_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by District_Grade
            count(distinct student_number) over (
                partition by
                    academic_year, district, expected_test, measure, measure_level
            ) as measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, measure
            ) as measure_level_met_district_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by District
            count(distinct student_number) over (
                partition by
                    academic_year, district, expected_test, measure, measure_level
            ) as measure_level_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, measure
            ) as measure_level_met_district_bm_pm_period_total_students_enrolled,
        from student_data
    )

select
    *,
    safe_divide(
        participation_school_course_section_bm_pm_period_total_students_assessed,
        participation_school_course_section_bm_pm_period_total_students_enrolled
    ) as participation_school_course_section_bm_pm_period_percent,
    safe_divide(
        participation_school_course_bm_pm_period_total_students_assessed,
        participation_school_course_bm_pm_period_total_students_enrolled
    ) as participation_school_course_bm_pm_period_percent,
    safe_divide(
        participation_school_grade_bm_pm_period_total_students_assessed,
        participation_school_grade_bm_pm_period_total_students_enrolled
    ) as participation_school_grade_bm_pm_period_percent,
    safe_divide(
        participation_school_bm_pm_period_total_students_assessed,
        participation_school_bm_pm_period_total_students_enrolled
    ) as participation_school_bm_pm_period_percent,
    safe_divide(
        participation_region_grade_bm_pm_period_total_students_assessed,
        participation_region_grade_bm_pm_period_total_students_enrolled
    ) as participation_region_grade_bm_pm_period_percent,
    safe_divide(
        participation_region_bm_pm_period_total_students_assessed,
        participation_region_bm_pm_period_total_students_enrolled
    ) as participation_region_bm_pm_period_percent,
    safe_divide(
        participation_district_grade_bm_pm_period_total_students_assessed,
        participation_district_grade_bm_pm_period_total_students_enrolled
    ) as participation_district_grade_bm_pm_period_percent,
    safe_divide(
        participation_district_bm_pm_period_total_students_assessed,
        participation_district_bm_pm_period_total_students_enrolled
    ) as participation_district_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
        measure_score_met_school_course_section_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_course_section_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
        measure_score_met_school_course_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_course_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_grade_bm_pm_period_total_students_assessed,
        measure_score_met_school_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_grade_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_bm_pm_period_total_students_assessed,
        measure_score_met_school_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_bm_pm_period_percent,
    safe_divide(
        measure_score_met_region_grade_bm_pm_period_total_students_assessed,
        measure_score_met_region_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_region_grade_bm_pm_period_percent,
    safe_divide(
        measure_score_met_region_bm_pm_period_total_students_assessed,
        measure_score_met_region_bm_pm_period_total_students_enrolled
    ) as measure_score_met_region_bm_pm_period_percent,
    safe_divide(
        measure_score_met_district_grade_bm_pm_period_total_students_assessed,
        measure_score_met_district_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_district_grade_bm_pm_period_percent_met,
    safe_divide(
        measure_score_met_district_bm_pm_period_total_students_assessed,
        measure_score_met_district_bm_pm_period_total_students_enrolled
    ) as measure_score_met_district_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
        measure_level_met_school_course_section_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_course_section_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
        measure_level_met_school_course_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_course_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_grade_bm_pm_period_total_students_assessed,
        measure_level_met_school_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_grade_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_bm_pm_period_total_students_assessed,
        measure_level_met_school_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_bm_pm_period_percent,
    safe_divide(
        measure_level_met_region_grade_bm_pm_period_total_students_assessed,
        measure_level_met_region_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_region_grade_bm_pm_period_percent,
    safe_divide(
        measure_level_met_region_bm_pm_period_total_students_assessed,
        measure_level_met_region_bm_pm_period_total_students_enrolled
    ) as measure_level_met_region_bm_pm_period_percent,
    safe_divide(
        measure_level_met_district_grade_bm_pm_period_total_students_assessed,
        measure_level_met_district_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_district_grade_bm_pm_period_percent_met,
    safe_divide(
        measure_level_met_district_bm_pm_period_total_students_assessed,
        measure_level_met_district_bm_pm_period_total_students_enrolled
    ) as measure_level_met_district_bm_pm_period_percent,
from student_data
