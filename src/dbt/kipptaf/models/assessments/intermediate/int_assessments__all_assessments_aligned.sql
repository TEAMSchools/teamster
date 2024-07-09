with
    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation as school,
            e.student_number,
            e.lastfirst as student_name,
            e.grade_level,
            e.cohort,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status,
            e.lep_status,
            e.is_504,

            a.scope,
            a.admin_season,
            a.month_round,
            a.discipline,
            a.subject_area,
            a.test_code,
            a.illuminate_subject,
            a.iready_subject,
            a.ps_credit_type,

            if(
                e.region = 'Miami', e.fleid, e.state_studentnumber
            ) as state_studentnumber,

            case
                when e.region = 'Miami' and e.ethnicity = 'T'
                then 'T'
                when e.region = 'Miami' and e.ethnicity = 'H'
                then 'H'
                when e.region = 'Miami'
                then e.ethnicity
                else null
            end as race_ethnicity,

            case
                when e.region != 'Miami'
                then null
                when e.region = 'Miami' and e.spedlep like '%SPED%'
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,

            case
                when e.school_level in ('ES', 'MS')
                then e.advisory_name
                when e.school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("stg_assessments__assessment_expectations") }} as a
            on e.academic_year = a.academic_year
            and e.region = a.region
            and e.grade_level = a.grade
            and a.assessment_type = 'State Assessment'
        where
            e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.rn_year = 1
            and e.grade_level > 2
            and e.schoolid != 999999
    ),

    assessments_nj as (
        select
            _dbt_source_relation,
            academic_year,
            statestudentidentifier as state_id,
            assessment_name,
            subject_area as discipline,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

            if(englishlearnerel = 'Y', true, false) as lep_status,

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

            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,

            case
                when studentwithdisabilities in ('IEP', 'B')
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,

        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= {{ var("current_academic_year") - 7 }}
    ),

    assessments_fl as (
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
                assessment_subject
                when 'ELAReading'
                then 'ELA'
                when 'Mathematics'
                then 'Math'
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
                test_name
                when 'B.E.S.T.Algebra1'
                then 'ALG01'
                when 'Civics'
                then 'SOC08'
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

            case
                test_grade_level when 5 then 'SCI05' when 8 then 'SCI08'
            end as test_code,

            'Spring' as season,
            'Science' as discipline,
            'Science' as subject,

        from {{ ref("stg_fldoe__science") }}
    )

select
    s.academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.student_name,
    s.grade_level,
    s.cohort,
    s.enroll_status,
    s.gender,
    s.lunch_status,
    s.advisory,

    a.race_ethnicity,
    a.lep_status,
    a.iep_status,
    a.is_504,
    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
    a.test_grade,
    a.admin,
    a.season,
    a.score,
    a.performance_band,
    a.performance_band_level,
    a.is_proficient,
from students as s
inner join
    assessments_nj as a
    on s.academic_year = a.academic_year
    and s.state_studentnumber = a.state_id
    and {{ union_dataset_join_clause(left_alias="s", right_alias="a") }}
    and a.score is not null

union all

select
    s.academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.student_name,
    s.grade_level,
    s.cohort,
    s.enroll_status,
    s.gender,
    s.lunch_status,
    s.advisory,
    s.race_ethnicity,
    s.lep_status,
    s.iep_status,
    s.is_504,

    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
    a.test_grade,
    a.admin,
    a.season,
    a.score,
    a.performance_band,
    a.performance_band_level,
    a.is_proficient,

from students as s
inner join
    assessments_fl as a
    on s.academic_year = a.academic_year
    and s.state_studentnumber = a.state_id
    and a.score is not null
