select
    _dbt_source_relation,
    academic_year,
    assessment_name,
    season,
    discipline,
    test_code,
    is_proficient,
    administration_window as admin,
    assessment_subject as subject,
    student_id as state_id,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    scale_score as score,

    safe_cast(enrolled_grade as string) as test_grade,
from {{ ref("stg_fldoe__eoc") }}
where not is_invalidated

union all

select
    _dbt_source_relation,
    academic_year,
    assessment_name,
    season,
    discipline,
    test_code,
    is_proficient,
    administration_window as admin,
    assessment_subject as subject,
    student_id as state_id,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    scale_score as score,

    safe_cast(test_grade_level as string) as test_grade,
from {{ ref("stg_fldoe__science") }}

union all

select
    _dbt_source_relation,
    academic_year,
    assessment_name,
    season,
    discipline,
    test_code,
    is_proficient,
    administration_window as admin,
    assessment_subject as subject,
    student_id as state_id,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    scale_score as score,

    safe_cast(assessment_grade as string) as test_grade,

from {{ ref("stg_fldoe__fast") }}
where achievement_level not in ('Insufficient to score', 'Invalidated')

union all

select
    _dbt_source_relation,
    academic_year,
    test_name as assessment_name,
    'Spring' as season,
    discipline,
    test_code,
    is_proficient,
    administration_round as admin,
    assessment_subject as subject,
    fleid as state_id,
    achievement_level as performance_band,
    performance_level as performance_band_level,
    scale_score as score,

    safe_cast(test_grade as string) as test_grade,

from {{ ref("stg_fldoe__fsa") }}
where performance_level is not null
