with
    student_k_2 as (
        select
            _dbt_source_relation,
            region as region,
            schoolid as school_id,
            school_name as school,
            school_abbreviation as school_abbreviation,
            studentid as student_id,
            student_number as student_number,
            lastfirst as student_name,
            first_name as student_first_name,
            last_name as student_last_name,
            academic_year,
            if(grade_level = 0, 'K', safe_cast(grade_level as string)) as grade_level,

            'KIPP NJ/MIAMI' as district,
        from {{ ref("base_powerschool__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and enroll_status = 0
            and grade_level <= 2
    ),

    assessments_scores as (
        select
            bss.student_primary_id as mclass_student_number,
            bss.benchmark_period as mclass_period,
            bss.academic_year as mclass_academic_year,

            u.measure as mclass_measure,
            u.level as mclass_measure_level,
            u.national_norm_percentile as measure_percentile,
            u.semester_growth as measure_semester_growth,
            u.year_growth as measure_year_growth,
            case
                u.level
                when 'Above Benchmark'
                then 4
                when 'At Benchmark'
                then 3
                when 'Below Benchmark'
                then 2
                when 'Well Below Benchmark'
                then 1
            end as mclass_measure_level_int,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        where bss.academic_year = {{ var("current_academic_year") }}
    ),

    roster_and_scores as (
        select
            s.academic_year,
            s.district,
            s.region,
            s.school_id,
            s.school,
            s.school_abbreviation,
            s.student_number,
            s.student_name,
            s.student_last_name,
            s.student_first_name,
            s.grade_level,

            m.mclass_period,
            m.mclass_measure,
            m.mclass_measure_level,
            m.measure_semester_growth,
            m.measure_year_growth,
        from student_k_2 as s
        left join
            assessments_scores as m
            on s.academic_year = m.mclass_academic_year
            and s.student_number = m.mclass_student_number
        where m.mclass_measure is not null
    ),

    non_composite_levels as (
        select
            r.academic_year,
            r.student_number,
            r.mclass_period,
            r.mclass_measure,
            r.mclass_measure_level,
            r.measure_semester_growth,
            r.measure_year_growth,

            v.description,
        from roster_and_scores as r
        inner join
            {{ ref("stg_assessments__mclass_dibels_measures") }} as v
            on r.grade_level = v.grade_level
            and r.mclass_measure = v.name
    ),

    composite_levels as (
        select
            academic_year,
            student_number,
            mclass_period,
            mclass_measure_level as composite_level,
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
        from roster_and_scores
        where mclass_measure = 'Composite'
    ),

    composite_and_non_composite as (
        select
            c.academic_year,
            c.student_number,
            c.mclass_period,
            c.composite_level,
            c.composite_expectations,

            n.mclass_measure as literacy_key_concept,
            n.description,
            n.mclass_measure_level as performance_level,
            n.measure_semester_growth,
            n.measure_year_growth,
        from composite_levels as c
        inner join
            non_composite_levels as n
            on c.academic_year = n.academic_year
            and c.student_number = n.student_number
            and c.mclass_period = n.mclass_period
    ),

    q1 as (
        select
            academic_year,
            student_number,
            mclass_period,
            composite_level,
            composite_expectations,
            literacy_key_concept,
            description,
            performance_level,

            'Not applicable' as growth_level,
            'Q1' as quarter,
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
            description,
            performance_level,
            measure_semester_growth as growth_level,

            'Q2' as quarter,
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
            description,
            performance_level,
            measure_semester_growth as growth_level,

            'Q3' as quarter,
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
            description,
            performance_level,
            measure_year_growth as growth_level,

            'Q4' as quarter,
        from composite_and_non_composite
        where mclass_period = 'EOY'
    )

select *
from q1
union all
select *
from q2
union all
select *
from q3
union all
select *
from q4
