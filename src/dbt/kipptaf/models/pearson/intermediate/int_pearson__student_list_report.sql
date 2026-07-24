with
    scores as (
        select
            _dbt_source_relation,
            _dbt_source_project,
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

            cast(state_student_identifier as string) as state_id,

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
                then
                    concat(
                        'MAT', lpad(regexp_extract(test_name, r'Grade (\d+)'), 2, '0')
                    )
                when test_name like '%ELA%'
                then
                    concat(
                        'ELA', lpad(regexp_extract(test_name, r'Grade (\d+)'), 2, '0')
                    )
            end as aligned_test_code,

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

    case
        when test_type = 'NJSLA' and performance_band_level <= 2
        then 'Not Proficient (1-2)'
        when test_type = 'NJSLA' and performance_band_level = 3
        then 'Bubble (3)'
        when test_type = 'NJSLA' and performance_band_level >= 4
        then 'Proficient (4-5)'
    end as njsla_performance_band_group_label,

    case
        when performance_level = 'Did Not Yet Meet Expectations'
        then 'Lvl 1'
        when performance_level = 'Partially Met Expectations'
        then 'Lvl 2'
        when
            performance_level in ('Approached Expectations', 'Not Yet Graduation Ready')
        then 'Lvl 3'
        when performance_level in ('Met Expectations', 'Graduation Ready')
        then 'Lvl 4'
        when performance_level = 'Exceeded Expectations'
        then 'Lvl 5'
    end as aligned_performance_band_group,

    if(
        performance_level
        in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
        true,
        false
    ) as is_proficient,

    if(
        performance_level
        in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
        1,
        0
    ) as is_proficient_int,

from scores
