with
    enrolled_composites as (
        select
            a.academic_year,
            a.region,
            a.assessment_grade_int as grade_level,
            a.period,
            a.foundation_measure_standard_level,
            a.is_above_average_growth,

            s.student_number,
            s.schoolid,
            s.school,
            s._dbt_source_project,
            s.iep_status,
            s.lep_status,
            s.advisory,
            s.gender,
            s.ethnicity,
            s.lunch_status,
            s.gifted_and_talented,
            s.is_504,
            s.is_homeless,
            s.cohort,
            s.hos,
            s.is_tutoring,
            s.is_sipps,

            c.cc_teacherid as teacherid,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,
            c.cc_section_number as section_number,

        from {{ ref("int_amplify__all_assessments") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as s
            on a.academic_year = s.academic_year
            and a.region = s.region
            and a.student_number = s.student_number
            and a.assessment_grade_int = s.grade_level
            and a.client_date between s.entrydate and s.exitdate
        left join
            {{ ref("base_powerschool__course_enrollments") }} as c
            on s.academic_year = c.cc_academic_year
            and s.schoolid = c.cc_schoolid
            and s.student_number = c.students_student_number
            and s._dbt_source_project = c._dbt_source_project
            and c.rn_course_number_year = 1
            and not c.is_dropped_section
            and c.cc_section_number not like '%SC%'
            and c.courses_course_name in (
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
        where
            a.assessment_type = 'Benchmark'
            and a.measure_standard = 'Composite'
            and not s.is_self_contained
            and not s.is_out_of_district
            and s.enroll_status in (0, 2, 3)
    ),

    population_fanout as (
        select
            academic_year,
            region,
            grade_level,
            `period`,
            foundation_measure_standard_level,
            is_above_average_growth,
            student_number,
            school,
            advisory,
            gender,
            ethnicity,
            lunch_status,
            gifted_and_talented,
            is_504,
            is_homeless,
            cohort,
            hos,
            is_tutoring,
            is_sipps,
            teacherid,
            teacher_name,
            course_name,
            course_number,
            section_number,

            population,

        from enrolled_composites
        cross join
            unnest(
                array_concat(
                    ['All'],
                    if(iep_status = 'Has IEP', ['IEP'], []),
                    if(lep_status, ['MLL'], [])
                )
            ) as population
    ),

    group_counts as (
        select
            *,

            count(student_number) over (
                partition by academic_year, region, grade_level, `period`, population
            ) as n_all,

            countif(foundation_measure_standard_level = 'At/Above') over (
                partition by academic_year, region, grade_level, `period`, population
            ) as n_at_above,

            countif(foundation_measure_standard_level = 'Well Below') over (
                partition by academic_year, region, grade_level, `period`, population
            ) as n_well_below,

            countif(is_above_average_growth) over (
                partition by academic_year, region, grade_level, `period`, population
            ) as n_above_average_growth,

        from population_fanout
    ),

    goal_type_rows as (
        select
            c.* except (n_at_above, n_well_below),

            goal_type,

            c.foundation_measure_standard_level = goal_type as is_attained,

            if(goal_type = 'At/Above', c.n_at_above, c.n_well_below) as n_attained,

        from group_counts as c
        cross join unnest(['At/Above', 'Well Below']) as goal_type
    ),

    attainment as (
        select
            *,

            safe_divide(n_attained, n_all) as attained_rate,

            if(
                `period` = 'BOY', null, safe_divide(n_above_average_growth, n_all)
            ) as pct_above_average_growth,

        from goal_type_rows
    ),

    goals_joined as (
        select
            a.* except (foundation_measure_standard_level), f.grade_band, f.grade_goal,

        from attainment as a
        inner join
            {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f
            on a.academic_year = f.academic_year
            and a.region = f.region
            and a.grade_level = f.grade_level
            and a.period = f.period
            and a.population = f.population
            and a.goal_type = f.grade_goal_type
    ),

    gap_calc as (
        select
            *,

            round(
                if(
                    goal_type = 'At/Above',
                    (attained_rate - grade_goal) * 100,
                    (grade_goal - attained_rate) * 100
                ),
                0
            ) as gap,

        from goals_joined
    )

select
    g.academic_year,
    g.region,
    g.school,
    g.grade_level,
    g.period,
    g.population,
    g.goal_type,
    g.grade_band,
    g.student_number,
    g.advisory,
    g.gender,
    g.ethnicity,
    g.lunch_status,
    g.gifted_and_talented,
    g.is_504,
    g.is_homeless,
    g.cohort,
    g.hos,
    g.is_tutoring,
    g.is_sipps,
    g.teacherid,
    g.teacher_name,
    g.course_name,
    g.course_number,
    g.section_number,

    t.tier as brightspot_status,

    g.is_attained,
    g.is_above_average_growth,

    g.n_all,
    g.n_attained,
    g.attained_rate,
    g.grade_goal,
    g.gap,
    g.n_above_average_growth,
    g.pct_above_average_growth,

from gap_calc as g
inner join
    {{ ref("stg_google_sheets__dibels_brightspot_goals") }} as t
    on g.academic_year = t.academic_year
    and g.grade_band = t.grade_band
    and g.period = t.period
    and g.population = t.population
    and (t.gap_min is null or g.gap >= t.gap_min)
    and (t.gap_max is null or g.gap <= t.gap_max)
