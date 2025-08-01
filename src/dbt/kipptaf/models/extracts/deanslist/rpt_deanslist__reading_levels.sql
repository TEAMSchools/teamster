with
    dibels as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.region,
            s.schoolid as school_id,
            s.student_number,
            s.lastfirst as student_name,
            s.first_name as student_first_name,
            s.last_name as student_last_name,

            c.period,
            c.measure_standard_level as composite_level,
            c.measure_semester_growth,
            c.measure_year_growth,

            nc.measure_standard as literacy_key_concept,
            nc.measure_standard_level as performance_level,

            m.description,
            m.description_translation as description_value_translated,
            m.measure_standard_translation as measure_standard_value_translated,

            'KIPP NJ/MIAMI' as district,

            if(s.grade_level = 0, 'K', cast(s.grade_level as string)) as grade_level,

            case
                c.measure_standard_level
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
            on s.academic_year = c.academic_year
            and s.student_number = c.student_number
            and s.grade_level = c.assessment_grade_int
            and c.measure_standard = 'Composite'
        inner join
            {{ ref("int_amplify__all_assessments") }} as nc
            on c.academic_year = nc.academic_year
            and c.student_number = nc.student_number
            and c.assessment_grade = nc.assessment_grade
            and c.period = nc.period
            and nc.assessment_type = 'Benchmark'
            and nc.measure_standard != 'Composite'
        inner join
            {{ ref("stg_google_sheets__dibels_measures") }} as m
            on nc.assessment_grade = m.grade_level
            and nc.measure_standard = m.measure_standard
        where
            s.academic_year = {{ var("current_academic_year") }}
            and s.enroll_status = 0
            and s.grade_level <= 4
    )

select
    academic_year,
    student_number,
    period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    measure_standard_value_translated,
    description_value_translated,

    'Not applicable' as growth_level,
    'Q1' as `quarter`,
from dibels
where period = 'BOY'

union all

select
    academic_year,
    student_number,
    period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    measure_standard_value_translated,
    description_value_translated,
    measure_semester_growth as growth_level,

    'Q2' as `quarter`,
from dibels
where period = 'MOY'

union all

select

    academic_year,
    student_number,
    period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    measure_standard_value_translated,
    description_value_translated,
    measure_semester_growth as growth_level,

    'Q3' as `quarter`,
from dibels
where period = 'MOY'

union all

select
    academic_year,
    student_number,
    period,
    composite_level,
    composite_expectations,
    literacy_key_concept,
    `description`,
    performance_level,
    measure_standard_value_translated,
    description_value_translated,
    measure_year_growth as growth_level,

    'Q4' as `quarter`,
from dibels
where period = 'EOY'
