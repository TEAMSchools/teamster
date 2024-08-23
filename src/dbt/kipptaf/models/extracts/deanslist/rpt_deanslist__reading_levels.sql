with
    students as (
        select
            s._dbt_source_relation,
            s.region,
            s.schoolid as school_id,
            s.school_name as school,
            s.school_abbreviation,
            s.studentid as student_id,
            s.student_number,
            s.lastfirst as student_name,
            s.first_name as student_first_name,
            s.last_name as student_last_name,
            s.academic_year,

            c.mclass_period,
            c.mclass_measure_level as composite_level,
            c.mclass_measure_semester_growth,
            c.mclass_measure_year_growth,

            nc.mclass_measure_level as literacy_key_concept,
            nc.mclass_measure_level as performance_level,

            m.description,

            'KIPP NJ/MIAMI' as district,

            if(
                s.grade_level = 0, 'K', safe_cast(s.grade_level as string)
            ) as grade_level,

            case
                when mclass_measure_level = 'Above Benchmark'
                then 'Exceeded'
                when mclass_measure_level = 'At Benchmark'
                then 'Met'
                when mclass_measure_level = 'Below Benchmark'
                then 'Not Met'
                when mclass_measure_level = 'Well Below Benchmark'
                then 'Not Met'
            end as composite_expectations,

        from {{ ref("base_powerschool__student_enrollments") }} as s
        left join
            {{ ref("int_amplify__all_assessments") }} as c
            on s.student_number = c.mclass_student_number
            and s.grade_level = c.mclass_assessment_grade
            and c.mclass_measure = 'Composite'
        left join
            {{ ref("int_amplify__all_assessments") }} as nc
            on c.academic_year = nc.academic_year
            and c.student_number = nc.mclass_student_number
            and c.mclass_assessment_grade = nc.mclass_assessment_grade
            and c.mclass_period = nc.mclass_period
            and nc.mclass_measure != 'Composite'
            and nc.assessment_type = 'Benchmark'
        inner join
            {{ ref("stg_assessments__mclass_dibels_measures") }} as m
            on nc.mclass_assessment_grade = m.grade_level
            and nc.mclass_measure = m.name
        where
            s.academic_year = {{ var("current_academic_year") }}
            and s.rn_year = 1
            and s.enroll_status = 0
            and s.grade_level <= 4
    )
/*
    q1 as (
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
        from composite_and_non_composite
        where mclass_period = 'BOY'
    ),

    q2 as (
        select
            academic_year,
            student_number,
            mclass_period,
            composite_level,
            composite_expectations,
            literacy_key_concept,
            `description`,
            performance_level,
            measure_semester_growth as growth_level,

            'Q2' as `quarter`,
        from composite_and_non_composite
        where mclass_period = 'MOY'
    ),

    q3 as (
        select
            academic_year,
            student_number,
            mclass_period,
            composite_level,
            composite_expectations,
            literacy_key_concept,
            `description`,
            performance_level,
            measure_semester_growth as growth_level,

            'Q3' as `quarter`,
        from composite_and_non_composite
        where mclass_period = 'MOY'
    ),

    q4 as (
        select
            academic_year,
            student_number,
            mclass_period,
            composite_level,
            composite_expectations,
            literacy_key_concept,
            `description`,
            performance_level,
            measure_year_growth as growth_level,

            'Q4' as `quarter`,
        from composite_and_non_composite
        where mclass_period = 'EOY'
    )*/
select
    academic_year,
    student_number,
    mclass_period,
    composite_level,
    composite_expectations,

    'Not applicable' as growth_level,
    'Q1' as `quarter`,
from students
where
    mclass_period = 'BOY'

    /*
select *,
from
    q1

union all

select *,
from q2

union all

select *,
from q3

union all

select *,
from q4
*/
    
