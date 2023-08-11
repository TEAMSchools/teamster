with
    student_schedule_test as (
        select
            se.studentid as student_id,
            se.student_number,
            se.first_name as student_first_name,
            se.last_name as student_last_name,
            se.lastfirst as student_name,
            se.academic_year,
            se.region,
            se.school_level,
            se.schoolid as school_id,
            se.school_name,
            se.school_abbreviation,
            se.gender,
            se.ethnicity,
            se.is_out_of_district,
            se.is_homeless,
            se.is_504,
            se.lep_status,
            se.lunch_status as economically_disadvantaged,
            if(spedlep = 'No IEP' or se.spedlep is null, false, true) as sped,

            ce.cc_course_number as course_number,
            ce.cc_section_number as section_number,
            ce.cc_teacherid as teacher_id,
            ce.courses_course_name as course_name,
            ce.teachernumber as teacher_number,
            ce.teacher_lastfirst as teacher_name,
            if(ce.cc_studentid is null, true, false) as enrolled_but_not_scheduled,

            x.expected_test,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref("base_powerschool__course_enrollments") }} as ce
            on se.studentid = ce.cc_studentid
            and se.yearid = ce.cc_yearid
            and ce.rn_course_number_year = 1
            and not ce.is_dropped_section
            and ce.courses_course_name
            in ('ELA GrK', 'ELA K', 'ELA Gr1', 'ELA Gr2', 'ELA Gr3', 'ELA Gr4')
        cross join grangel.amplify_dibels_expected_tests as x
        where se.rn_year = 1 and se.academic_year >= 2022 and se.grade_level <= 4
    ),

    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__benchmark_student_summary_unpivot"),
                    ref("stg_amplify__pm_student_summary"),
                ]
            )
        }}
    ),

    student_data as (
        select
            s.academic_year,
            s.school_level,
            s.school_id,
            s.school,
            s.school_abbreviation,
            s.student_number_enrollment,
            s.student_name,
            s.student_last_name,
            s.student_first_name,
            s.grade_level,
            s.ood,
            s.gender,
            s.ethnicity,
            s.homeless,
            s.is_504,
            s.sped,
            s.lep,
            s.economically_disadvantaged,
            s.region,
            s.reporting_school_id,
            s.teacher_id,
            s.teacher_name,
            s.course_name,
            s.course_number,
            s.section_number,
            s.expected_test,

            -- Tagging students as enrolled in school but not scheduled for the course
            -- that would allow them to take the DIBELS test
            d.mclass_reporting_class_name,
            d.mclass_reporting_class_id,
            d.mclass_official_teacher_name,
            d.mclass_official_teacher_staff_id,
            d.mclass_assessing_teacher_name,
            d.mclass_assessing_teacher_staff_id,
            d.mclass_assessment,
            d.mclass_assessment_edition,
            d.mclass_assessment_grade,
            d.mclass_period,
            d.mclass_client_date,
            d.mclass_sync_date,
            d.mclass_probe_number,
            d.mclass_total_number_of_probes,
            d.mclass_measure,
            d.mclass_score_change,
            d.mclass_measure_level,
            d.measure_percentile,
            d.measure_semester_growth,
            d.measure_year_growth,
            d.mclass_measure_score,
            -- Another tag for students who tested for benchmarks
            if(
                d.mclass_period in ('BOY', 'MOY', 'EOY'), d.mclass_student_number, null
            ) as mclass_student_number_bm,
            -- Another tag for students who tested for progress monitoring
            if(
                d.mclass_period in ('BOY->MOY', 'MOY->EOY'),
                d.mclass_student_number,
                null
            ) as mclass_student_number_pm,
            -- Tagging students who are schedule for the correct class but have not
            -- tested yet for the expected assessment term
            if(
                d.mclass_student_number is not null, true, false
            ) as student_has_assessment_data,

            'KIPP NJ/Miami' as district,
        from student_schedule_test as s
        left join
            union_relations as d
            on m.academic_year = d.mclass_academic_year
            and m.student_number_schedule = d.mclass_student_number
            and m.expected_test = d.mclass_period
    ),

    with_counts as (
        select
            *,

            -- Participation rates by School_Course_Section
            count(distinct mclass_student_number) over (
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
            count(distinct mclass_student_number) over (
                partition by academic_year, school_id, course_name, expected_test
            ) as participation_school_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, course_name, expected_test
            ) as participation_school_course_bm_pm_period_total_students_enrolled,

            -- Participation rates by School_Grade
            count(distinct mclass_student_number) over (
                partition by academic_year, school_id, grade_level, expected_test
            ) as participation_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, grade_level, expected_test
            ) as participation_school_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by School
            count(distinct mclass_student_number) over (
                partition by academic_year, school_id, expected_test
            ) as participation_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test
            ) as participation_school_bm_pm_period_total_students_enrolled,

            -- Participation rates by Region_Grade
            count(distinct mclass_student_number) over (
                partition by academic_year, region, grade_level, expected_test
            ) as participation_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, grade_level, expected_test
            ) as participation_region_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by Region
            count(distinct mclass_student_number) over (
                partition by academic_year, region, expected_test
            ) as participation_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test
            ) as participation_region_bm_pm_period_total_students_enrolled,

            -- Participation rates by District_Grade
            count(distinct mclass_student_number) over (
                partition by academic_year, district, expected_test
            ) as participation_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test
            ) as participation_district_grade_bm_pm_period_total_students_enrolled,

            -- Participation rates by District
            count(distinct mclass_student_number) over (
                partition by academic_year, district, expected_test
            ) as participation_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test
            ) as participation_district_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Course_Section
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    mclass_measure
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Course
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            )
            as measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, course_name, expected_test, mclass_measure
            ) as measure_score_met_school_course_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    grade_level,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, grade_level, expected_test, mclass_measure
            ) as measure_score_met_school_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by School
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test, mclass_measure
            ) as measure_score_met_school_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by Region_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    region,
                    grade_level,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, region, grade_level, expected_test, mclass_measure
            ) as measure_score_met_region_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by Region
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    region,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test, mclass_measure
            ) as measure_score_met_region_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by District_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    district,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, mclass_measure
            ) as measure_score_met_district_grade_bm_pm_period_total_students_enrolled,

            -- Measure score met rates by District
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    district,
                    expected_test,
                    mclass_measure,
                    mclass_measure_score
            ) as measure_score_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, mclass_measure
            ) as measure_score_met_district_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Course_Section
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    section_number,
                    expected_test,
                    mclass_measure
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Course
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    course_name,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            )
            as measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, course_name, expected_test, mclass_measure
            ) as measure_level_met_school_course_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    grade_level,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, school_id, grade_level, expected_test, mclass_measure
            ) as measure_level_met_school_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by School
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    school_id,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, school_id, expected_test, mclass_measure
            ) as measure_level_met_school_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by Region_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    region,
                    grade_level,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by
                    academic_year, region, grade_level, expected_test, mclass_measure
            ) as measure_level_met_region_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by Region
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    region,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, region, expected_test, mclass_measure
            ) as measure_level_met_region_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by District_Grade
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    district,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, mclass_measure
            ) as measure_level_met_district_grade_bm_pm_period_total_students_enrolled,

            -- Measure level met rates by District
            count(distinct mclass_student_number) over (
                partition by
                    academic_year,
                    district,
                    expected_test,
                    mclass_measure,
                    mclass_measure_level
            ) as measure_level_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number_schedule) over (
                partition by academic_year, district, expected_test, mclass_measure
            ) as measure_level_met_district_bm_pm_period_total_students_enrolled,
        from student_data
    )

select
    *,
    round(
        safe_divide(
            participation_school_course_section_bm_pm_period_total_students_assessed,
            participation_school_course_section_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_school_course_section_bm_pm_period_percent,
    round(
        safe_divide(
            participation_school_course_bm_pm_period_total_students_assessed,
            participation_school_course_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_school_course_bm_pm_period_percent,
    round(
        safe_divide(
            participation_school_grade_bm_pm_period_total_students_assessed,
            participation_school_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_school_grade_bm_pm_period_percent,
    round(
        safe_divide(
            participation_school_bm_pm_period_total_students_assessed,
            participation_school_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_school_bm_pm_period_percent,
    round(
        safe_divide(
            participation_region_grade_bm_pm_period_total_students_assessed,
            participation_region_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_region_grade_bm_pm_period_percent,
    round(
        safe_divide(
            participation_region_bm_pm_period_total_students_assessed,
            participation_region_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_region_bm_pm_period_percent,
    round(
        safe_divide(
            participation_district_grade_bm_pm_period_total_students_assessed,
            participation_district_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_district_grade_bm_pm_period_percent,
    round(
        safe_divide(
            participation_district_bm_pm_period_total_students_assessed,
            participation_district_bm_pm_period_total_students_enrolled
        ),
        4
    ) as participation_district_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
            measure_score_met_school_course_section_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_school_course_section_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
            measure_score_met_school_course_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_school_course_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_school_grade_bm_pm_period_total_students_assessed,
            measure_score_met_school_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_school_grade_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_school_bm_pm_period_total_students_assessed,
            measure_score_met_school_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_school_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_region_grade_bm_pm_period_total_students_assessed,
            measure_score_met_region_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_region_grade_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_region_bm_pm_period_total_students_assessed,
            measure_score_met_region_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_region_bm_pm_period_percent,
    round(
        safe_divide(
            measure_score_met_district_grade_bm_pm_period_total_students_assessed,
            measure_score_met_district_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_district_grade_bm_pm_period_percent_met,
    round(
        safe_divide(
            measure_score_met_district_bm_pm_period_total_students_assessed,
            measure_score_met_district_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_score_met_district_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            measure_level_met_school_course_section_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_school_course_section_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
            measure_level_met_school_course_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_school_course_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            measure_level_met_school_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_school_grade_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_school_bm_pm_period_total_students_assessed,
            measure_level_met_school_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_school_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            measure_level_met_region_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_region_grade_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_region_bm_pm_period_total_students_assessed,
            measure_level_met_region_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_region_bm_pm_period_percent,
    round(
        safe_divide(
            measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            measure_level_met_district_grade_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_district_grade_bm_pm_period_percent_met,
    round(
        safe_divide(
            measure_level_met_district_bm_pm_period_total_students_assessed,
            measure_level_met_district_bm_pm_period_total_students_enrolled
        ),
        4
    ) as measure_level_met_district_bm_pm_period_percent
from student_data
