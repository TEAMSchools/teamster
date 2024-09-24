with
    dibels as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.region,
            s.schoolid as school_id,
            s.school_name as school,
            s.school_abbreviation,
            s.studentid as student_id,
            s.student_number,
            s.lastfirst as student_name,
            s.first_name as student_first_name,
            s.last_name as student_last_name,

            c.mclass_period,
            c.mclass_measure_level as composite_level,
            c.mclass_measure_semester_growth,
            c.mclass_measure_year_growth,

            nc.mclass_measure as literacy_key_concept,
            nc.mclass_measure_level as performance_level,

            m.description,

            'KIPP NJ/MIAMI' as district,

            if(s.grade_level = 0, 'K', cast(s.grade_level as string)) as grade_level,

            case
                c.mclass_measure_level
                when 'Above Benchmark'
                then 'Exceeded'
                when 'At Benchmark'
                then 'Met'
                when 'Below Benchmark'
                then 'Not Met'
                when 'Well Below Benchmark'
                then 'Not Met'
            end as composite_expectations,
        from {{ ref("base_powerschool__student_enrollments") }} as s
        inner join
            {{ ref("int_amplify__all_assessments") }} as c
            on s.academic_year = c.mclass_academic_year
            and s.student_number = c.mclass_student_number
            and s.grade_level = c.mclass_assessment_grade_int
            and c.mclass_measure = 'Composite'
        inner join
            {{ ref("int_amplify__all_assessments") }} as nc
            on c.mclass_academic_year = nc.mclass_academic_year
            and c.mclass_student_number = nc.mclass_student_number
            and c.mclass_assessment_grade = nc.mclass_assessment_grade
            and c.mclass_period = nc.mclass_period
            and nc.assessment_type = 'Benchmark'
            and nc.mclass_measure != 'Composite'
        inner join
            {{ ref("stg_amplify__dibels_measures") }} as m
            on nc.mclass_assessment_grade = m.grade_level
            and nc.mclass_measure = m.measure_standard
        where
            s.academic_year = {{ var("current_academic_year") }}
            and s.rn_year = 1
            and s.enroll_status = 0
            and s.grade_level <= 4
    )

select
    academic_year,
    student_number,
    mclass_period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,

    'Not applicable' as growth_level,
    'Q1' as `quarter`,
from dibels
where mclass_period = 'BOY'

union all

select
    academic_year,
    student_number,
    mclass_period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    mclass_measure_semester_growth as growth_level,

    'Q2' as `quarter`,
from dibels
where mclass_period = 'MOY'

union all

select

    academic_year,
    student_number,
    mclass_period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    mclass_measure_semester_growth as growth_level,

    'Q3' as `quarter`,
from dibels
where mclass_period = 'MOY'

union all

select
    academic_year,
    student_number,
    mclass_period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    mclass_measure_year_growth as growth_level,

    'Q4' as `quarter`,
from dibels
where mclass_period = 'EOY'
