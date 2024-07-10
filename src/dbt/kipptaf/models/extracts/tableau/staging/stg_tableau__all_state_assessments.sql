with
    assessments_nj as (
        select
            academic_year,
            statestudentidentifier as state_id,
            assessment_name,
            subject_area as discipline,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,

            if(
                subject = 'English Language Arts/Literacy',
                'English Language Arts',
                subject
            ) as subject,

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

            case
                when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 2
                then 'Graduation Ready'
                when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 1
                then 'Not Yet Graduation Ready'
                else testperformancelevel_text
            end as performance_band,

        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= {{ var("current_academic_year") - 7 }}
    )

select
    academic_year,
    state_id,
    test_grade,
    `admin`,
    score,
    performance_band,
    performance_band_level,
    is_proficient,
    assessment_name,
    test_code,
    season,
    discipline,
    subject,
from assessments_nj

union all

select
    academic_year,
    student_id as state_id,
    assessment_grade as test_grade,

    administration_window as `admin`,
    scale_score as score,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    is_proficient,

    'FAST' as assessment_name,

    if(
        assessment_subject = 'ELAReading',
        concat('ELA0', assessment_grade),
        concat('MAT0', assessment_grade)
    ) as test_code,

    case
        administration_window
        when 'PM1'
        then 'Fall'
        when 'PM2'
        then 'Winter'
        when 'PM3'
        then 'Spring'
    end as season,

    case
        assessment_subject when 'ELAReading' then 'ELA' when 'Mathematics' then 'Math'
    end as discipline,

    case
        assessment_subject
        when 'ELAReading'
        then 'English Language Arts'
        when 'Mathematics'
        then 'Mathematics'
    end as `subject`,

from {{ ref("stg_fldoe__fast") }}
where achievement_level not in ('Insufficient to score', 'Invalidated')

union all

select
    academic_year,
    fleid as state_id,
    test_grade,

    'Spring' as `admin`,

    scale_score as score,
    achievement_level as performance_band,
    performance_level as performance_band_level,
    is_proficient,

    'FSA' as assessment_name,

    case
        when test_subject = 'ELA'
        then concat('ELA0', test_grade)
        when test_subject = 'SCIENCE'
        then concat('SCI0', test_grade)
        else concat('MAT0', test_grade)
    end as test_code,

    'Spring' as season,

    case
        test_subject
        when 'ELA'
        then 'ELA'
        when 'MATH'
        then 'Math'
        when 'SCIENCE'
        then 'Science'
    end as discipline,

    case
        test_subject
        when 'ELA'
        then 'English Language Arts'
        when 'MATH'
        then 'Mathematics'
        when 'SCIENCE'
        then 'Science'
    end as subject,

from {{ ref("stg_fldoe__fsa") }}
where performance_level is not null

union all

select
    academic_year,
    student_id as state_id,
    enrolled_grade as test_grade,

    'PM3' as `admin`,

    scale_score as score,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    is_proficient,

    'EOC' as assessment_name,

    case
        test_name when 'B.E.S.T.Algebra1' then 'ALG01' when 'Civics' then 'SOC08'
    end as test_code,

    'Spring' as season,

    if(test_name = 'B.E.S.T.Algebra1', 'Math', 'Civics') as discipline,

    if(test_name = 'B.E.S.T.Algebra1', 'Algebra I', 'Civics') as subject,

from {{ ref("stg_fldoe__eoc") }}
where not is_invalidated

union all

select
    academic_year,
    student_id as state_id,
    test_grade_level as test_grade,

    'PM3' as `admin`,

    scale_score as score,
    achievement_level as performance_band,
    achievement_level_int as performance_band_level,
    is_proficient,

    'Science' as assessment_name,

    case test_grade_level when 5 then 'SCI05' when 8 then 'SCI08' end as test_code,

    'Spring' as season,
    'Science' as discipline,
    'Science' as subject,

from {{ ref("stg_fldoe__science") }}
