with
    scores as (
        select
            student_test_uuid,
            academic_year,
            test_date,
            grade_level_when_assessed,
            discipline,
            test_code,
            student_growth_percentile,
            is_proficient,
            aligned_aggregate_ethnicity,
            is_student_with_disabilities,
            aligned_ml_status,
            is_economically_disadvantaged,

            {{ student_key("student_number") }} as student_key,
        from {{ ref("int_assessments__state_nj_scores") }}
        where student_growth_percentile is not null
    )

select
    s.student_test_uuid,
    s.student_key,
    s.academic_year,
    s.test_date,
    s.grade_level_when_assessed as grade_level_tested,
    s.discipline as subject,
    s.test_code,
    s.student_growth_percentile,
    s.is_proficient,
    s.is_student_with_disabilities,
    s.is_economically_disadvantaged,

    l.location_key,
    l.abbreviation as school,
    l.name as school_name,
    l.grade_band,

    r.name as region,

    if(
        s.aligned_aggregate_ethnicity = 'Other',
        'Two or more races',
        s.aligned_aggregate_ethnicity
    ) as race_ethnicity_group,

    s.aligned_ml_status = 'ML' as is_multilingual_learner,

    -- NJDOE's growth bands: below 35, 35 through 65, above 65
    case
        when s.student_growth_percentile < 35
        then 'Low'
        when s.student_growth_percentile > 65
        then 'High'
        else 'Typical'
    end as growth_level,
from scores as s
left join
    {{ ref("dim_student_enrollments") }} as e
    on s.student_key = e.student_key
    and s.academic_year = e.academic_year
    and s.test_date >= e.entry_date_key
    and s.test_date < e.exit_date_key
left join {{ ref("dim_locations") }} as l on e.location_key = l.location_key
left join {{ ref("dim_regions") }} as r on l.region_key = r.region_key
