select
    _dbt_source_relation,
    academic_year,
    localstudentidentifier,
    statestudentidentifier as state_id,
    assessment_name,
    discipline,
    testscalescore as score,
    testperformancelevel as performance_band_level,
    is_proficient,
    testperformancelevel_text as performance_band,
    test_grade,
    lep_status as state_lep_status,
    is_504 as state_is_504,
    iep_status as state_iep_status,
    race_ethnicity as state_race_ethnicity,

    'Actual' as results_type,

    if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,

    if(`period` = 'FallBlock', 'Fall', `period`) as season,

    if(
        `subject` = 'English Language Arts/Literacy', 'English Language Arts', `subject`
    ) as `subject`,

    case
        testcode
        when 'SC05'
        then 'SCI05'
        when 'SC08'
        then 'SCI08'
        when 'SC11'
        then 'SCI11'
        else testcode
    end as test_code,

from {{ ref("int_pearson__all_assessments") }}
where and testscalescore is not null

union all

select
    _dbt_source_relation,
    academic_year,
    null as localstudentidentifier,
    student_id as state_id,
    assessment_name,
    discipline,
    scale_score as score,
    performance_level as performance_band_level,
    is_proficient,
    achievement_level as performance_band,
    cast(assessment_grade as int) as test_grade,
    null as lep_status,
    null as is_504,
    null as iep_status,
    null as race_ethnicity,

    'Actual' as results_type,

    administration_window as `admin`,

    season,

    assessment_subject as `subject`,

    test_code,

from {{ ref("int_fldoe__all_assessments") }}
where scale_score is not null
