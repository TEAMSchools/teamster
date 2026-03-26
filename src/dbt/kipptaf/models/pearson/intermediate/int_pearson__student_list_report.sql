with
    scores as (
        select
            _dbt_source_relation,
            academic_year,
            state_student_identifier,
            local_student_identifier,
            last_or_surname,
            first_name,
            date_of_birth,
            test_type,
            scale_score,
            performance_level,
            administration,

            'Preliminary' as results_type,
            'KTAF NJ' as district_state,

            case
                when test_name like '%Mathematics%'
                then 'Math'
                when test_name in ('Algebra I', 'Geometry')
                then 'Math'
                else 'ELA'
            end as discipline,

            case
                when test_name like '%Mathematics%'
                then 'Mathematics'
                when test_name in ('Algebra I', 'Geometry')
                then 'Mathematics'
                else 'English Language Arts'
            end as `subject`,

            case
                when test_name = 'ELA Graduation Proficiency'
                then 'ELAGP'
                when test_name = 'Mathematics Graduation Proficiency'
                then 'MATGP'
                when test_name = 'Geometry'
                then 'GEO01'
                when test_name = 'Algebra I'
                then 'ALG01'
                when test_name like '%Mathematics%'
                then concat('MAT', regexp_extract(test_name, r'.{6}(.{2})'))
                when test_name like '%ELA%'
                then concat('ELA', regexp_extract(test_name, r'.{6}(.{2})'))
            end as test_code,

            case
                when performance_level = 'Did Not Yet Meet Expectations'
                then 1
                when performance_level = 'Partially Met Expectations'
                then 2
                when performance_level = 'Approached Expectations'
                then 3
                when performance_level = 'Met Expectations'
                then 4
                when performance_level = 'Exceeded Expectations'
                then 5
                when performance_level = 'Not Yet Graduation Ready'
                then 1
                when performance_level = 'Graduation Ready'
                then 2
            end as performance_band_level,

        from {{ ref("stg_pearson__student_list_report") }}
    )

select
    *,

    if(
        performance_level
        in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
        true,
        false
    ) as is_proficient,

from scores
