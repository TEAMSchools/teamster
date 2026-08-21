with
    expectations as (
        select
            academic_year,
            region,
            assessment_type,
            admin_season,
            expected_measure_standard,
            grade,
            `start_date`,
            end_date,
            round_number,

            count(*) over (
                partition by academic_year, region, grade, admin_season, round_number
            ) as expected_measure_count,

        from {{ ref("int_google_sheets__dibels_expected_assessments") }}
        where assessment_include is null and pm_goal_include is null
    ),

    ela_sections as (
        select
            cc_academic_year,
            cc_schoolid,
            students_student_number,
            _dbt_source_project,

            courses_course_name as course_name,
            cc_course_number as course_number,
            cc_section_number as section_number,
            teacher_lastfirst as teacher_name,

            -- a handful of students are scheduled into two ELA courses in one
            -- year; take the lower course number so the attribute is stable
            -- rather than fanning the measure grain out
            row_number() over (
                partition by
                    cc_academic_year,
                    cc_schoolid,
                    students_student_number,
                    _dbt_source_project
                order by cc_course_number
            ) as rn_student_course,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_course_number_year = 1
            and not is_dropped_section
            and cc_section_number not like '%SC%'
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
    ),

    students as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.school,
            s.entrydate,
            s.exitdate,
            s.is_self_contained,
            s.is_out_of_district,

            c.course_name,
            c.course_number,
            c.section_number,
            c.teacher_name,

            coalesce(s.advisory, 'Unassigned') as advisory,

        from {{ ref("int_extracts__student_enrollments_subjects") }} as s
        left join
            ela_sections as c
            on s.academic_year = c.cc_academic_year
            and s.schoolid = c.cc_schoolid
            and s.student_number = c.students_student_number
            and s._dbt_source_project = c._dbt_source_project
            and c.rn_student_course = 1
        where
            s.discipline = 'ELA' and s.enroll_status in (0, 2, 3) and s.grade_level <= 8
    ),

    student_measures as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.school,
            s.advisory,
            s.is_self_contained,
            s.is_out_of_district,
            s.course_name,
            s.course_number,
            s.section_number,
            s.teacher_name,

            e.assessment_type,
            e.admin_season,
            e.expected_measure_standard,
            e.round_number,
            e.`start_date`,
            e.end_date,
            e.expected_measure_count,

        from students as s
        inner join
            expectations as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and (
                e.`start_date` between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
    ),

    spine as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            schoolid,
            school,
            advisory,
            is_self_contained,
            is_out_of_district,
            course_name,
            course_number,
            section_number,
            teacher_name,
            assessment_type,
            admin_season,
            expected_measure_standard,
            round_number,
            `start_date`,
            end_date,
            expected_measure_count,

            calendar_day,

        from student_measures
        cross join
            unnest(
                generate_date_array(`start_date`, end_date, interval 1 day)
            ) as calendar_day
    ),

    base as (
        select
            academic_year,
            region,
            student_number,
            assessment_type,
            assessment_grade_int,
            `period`,
            round_number,
            client_date,
            measure_standard,

        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark'

        union all

        select
            academic_year,
            region,
            student_number,
            assessment_type,
            assessment_grade_int,
            `period`,
            round_number,
            client_date,
            measure_standard,

        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'PM' and overall_probe_eligible = 'Yes'
    ),

    joined as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.school,
            s.advisory,
            s.is_self_contained,
            s.is_out_of_district,
            s.course_name,
            s.course_number,
            s.section_number,
            s.teacher_name,
            s.assessment_type,
            s.admin_season,
            s.expected_measure_standard,
            s.round_number,
            s.`start_date`,
            s.end_date,
            s.expected_measure_count,
            s.calendar_day,

            b.client_date,

            coalesce(b.client_date <= s.calendar_day, false) as finished_measure,
            coalesce(b.client_date = s.calendar_day, false) as finished_this_day,

        from spine as s
        left join
            base as b
            on s.academic_year = b.academic_year
            and s.region = b.region
            and s.student_number = b.student_number
            and s.assessment_type = b.assessment_type
            and s.admin_season = b.`period`
            and s.round_number = b.round_number
            and s.expected_measure_standard = b.measure_standard
            and s.grade_level = b.assessment_grade_int
        where s.academic_year = {{ var("current_academic_year") }}
    ),

    rolled as (
        select
            *,

            sum(if(finished_measure, 1, 0)) over (
                partition by
                    academic_year,
                    region,
                    assessment_type,
                    student_number,
                    admin_season,
                    round_number,
                    calendar_day
            ) as measures_finished_to_date,

        from joined
    )

select
    academic_year,
    region,
    student_number,
    grade_level,
    schoolid,
    school,
    advisory,
    is_self_contained,
    is_out_of_district,
    course_name,
    course_number,
    section_number,
    teacher_name,
    assessment_type,
    admin_season as `period`,
    expected_measure_standard,
    round_number,
    `start_date`,
    end_date,
    expected_measure_count,
    calendar_day,
    client_date,
    finished_measure,
    finished_this_day,
    measures_finished_to_date,

    if(
        measures_finished_to_date = expected_measure_count, true, false
    ) as finished_round,

from rolled
