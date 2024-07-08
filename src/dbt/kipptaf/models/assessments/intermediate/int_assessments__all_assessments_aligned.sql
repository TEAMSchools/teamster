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
            end as lep_status,

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
            _dbt_source_relation,
            academic_year,
            is_proficient,
            student_id as state_id,
            achievement_level as performance_band,
            achievement_level_int as performance_band_level,
            scale_score as score,

            'EOC' as assessment_name,
            'PM3' as `admin`,
            'Spring' as season,

            if(test_name = 'B.E.S.T.Algebra1', 'Math', 'Civics') as discipline,
            if(test_name = 'B.E.S.T.Algebra1', 'Algebra I', 'Civics') as subject,
            if(test_name = 'B.E.S.T.Algebra1', 'ALG01', 'SOC08') as test_code,

            safe_cast(enrolled_grade as string) as test_grade,

        from {{ ref("stg_fldoe__eoc") }}
        where not is_invalidated

    ),

    assessments_fl_science as (
        select
            academic_year,
            is_proficient,
            student_id as state_id,
            achievement_level as performance_band,
            achievement_level_int as performance_band_level,
            scale_score as score,

            'Science' as assessment_name,
            'PM3' as `admin`,
            'Spring' as season,
            'Science' as discipline,
            'Science' as subject,

            if(test_grade_level = 5, 'SCI05', 'SCI08') as test_code,

            safe_cast(test_grade_level as string) as test_grade,

        from {{ ref("stg_fldoe__science") }}
    ),

    assessments_fl as (
        select
            academic_year,
            student_id as state_id,
            'FAST' as assessment_name,
            safe_cast(assessment_grade as string) as test_grade,
            administration_window as `admin`,
            scale_score as score,
            achievement_level as performance_band,
            achievement_level_int as performance_band_level,
            is_proficient,

            case
                administration_window
                when 'PM1'
                then 'Fall'
                when 'PM2'
                then 'Winter'
                when 'PM3'
                then 'Spring'
            end as season,

            if(assessment_subject = 'ELAReading', 'ELA', 'Math') as discipline,
            if(
                assessment_subject = 'ELAReading',
                'English Language Arts',
                'Mathematics'
            ) as subject,

            if(
                assessment_subject = 'ELAReading',
                concat('ELA0', assessment_grade),
                concat('MAT0', assessment_grade)
            ) as test_code,

        from {{ ref("stg_fldoe__fast") }}
        where achievement_level not in ('Insufficient to score', 'Invalidated')
        union all
        select
            academic_year,
            fleid as state_id,
            'FSA' as assessment_name,
            safe_cast(test_grade as string) as test_grade,
            'Spring' as `admin`,
            scale_score as score,
            achievement_level as performance_band,
            performance_level as performance_band_level,
            is_proficient,
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
            case
                when test_subject = 'ELA'
                then concat('ELA0', test_grade)
                when test_subject = 'SCIENCE'
                then concat('SCI0', test_grade)
                else concat('MAT0', test_grade)
            end as test_code,
        from {{ ref("stg_fldoe__fsa") }}
        where performance_level is not null
        union all
        select
            academic_year,
            state_id,
            assessment_name,
            test_grade,
            `admin`,
            score,
            performance_band,
            performance_band_level,
            is_proficient,
            season,
            discipline,
            subject,
            test_code,
        from assessments_fl_eoc
        union all
        select
            academic_year,
            state_id,
            assessment_name,
            test_grade,
            `admin`,
            score,
            performance_band,
            performance_band_level,
            is_proficient,
            season,
            discipline,
            subject,
            test_code,
        from assessments_fl_science

    ),

    nj_final as (
        select
            s._dbt_source_relation,
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
            s.ms_attended,
            s.advisory,

            a.state_id,
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
        from assessments_nj as a
        inner join
            students_nj as s
            on a.academic_year = s.academic_year
            and a.state_id = s.state_studentnumber
        where a.score is not null
    ),

    fl_final as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.region,
            s.schoolid,
            s.school,
            s.student_number,
            s.fleid as state_studentnumber,
            s.student_name,
            s.grade_level,
            s.cohort,
            s.enroll_status,
            s.gender,
            s.race_ethnicity,
            s.iep_status,
            s.is_504,
            s.lunch_status,
            s.lep_status,
            s.advisory,

            a.state_id,
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
        from assessments_fl as a
        inner join
            students_fl as s
            on a.academic_year = s.academic_year
            and a.state_id = s.fleid
        where a.score is not null
    ),

select
    s.academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.state_id,
    s.student_name,
    s.grade_level,
    s.cohort,
    s.enroll_status,
    s.gender,
    s.race_ethnicity,
    s.iep_status,
    s.is_504,
    s.lunch_status,
    s.ms_attended,
    s.lep_status,
    s.advisory,
    s.assessment_name,
    s.discipline,
    s.subject,
    s.test_code,
    s.test_grade,
    s.admin,
    s.season,
    s.score,
    s.performance_band,
    s.performance_band_level,
    s.is_proficient,

    c.city as proficiency_city,
    c.state as proficiency_state,

    g.grade_level as assessment_grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    sf.nj_student_tier,

    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_name_current,

    'Actual' as results_type,
from nj_final as s
left join
    state_comps as c
    on s.academic_year = c.academic_year
    and s.assessment_name = c.test_name
    and s.test_code = c.test_code
    and s.region = c.region
left join
    goals as g
    on s.academic_year = g.academic_year
    and s.schoolid = g.school_id
    and s.test_code = g.state_assessment_code
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.student_number = m.students_student_number
    and s.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on s.academic_year = sf.academic_year
    and s.discipline = sf.discipline
    and s.student_number = sf.student_number
union all
select
    s.academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.state_id,
    s.student_name,
    s.grade_level,
    s.cohort,
    s.enroll_status,
    s.gender,
    s.race_ethnicity,
    s.iep_status,
    s.is_504,
    s.lunch_status,
    null as ms_attended,
    s.lep_status,
    s.advisory,
    s.assessment_name,
    s.discipline,
    s.subject,
    s.test_code,
    s.test_grade,
    s.admin,
    s.season,
    s.score,
    s.performance_band,
    s.performance_band_level,
    s.is_proficient,

    c.city as proficiency_city,
    c.state as proficiency_state,

    g.grade_level as assessment_grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    sf.nj_student_tier,

    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_name_current,

    'Actual' as results_type,
from fl_final as s
left join
    state_comps as c
    on s.academic_year = c.academic_year
    and s.assessment_name = c.test_name
    and s.test_code = c.test_code
    and s.region = c.region
left join
    goals as g
    on s.academic_year = g.academic_year
    and s.schoolid = g.school_id
    and s.test_code = g.state_assessment_code
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.student_number = m.students_student_number
    and s.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on s.academic_year = sf.academic_year
    and s.discipline = sf.discipline
    and s.student_number = sf.student_number
union all
select
    academic_year,
    region,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    state_id,
    student_name,
    grade_level,
    cohort,
    enroll_status,
    gender,
    race_ethnicity,
    iep_status,
    is_504,
    lunch_status,
    ms_attended,
    lep_status,
    advisory,
    assessment_name,
    discipline,
    subject,
    test_code,
    cast(test_grade as string) as test_grade,
    admin,
    season,
    score,
    performance_band,
    performance_band_level,
    is_proficient,
    proficiency_city,
    proficiency_state,
    assessment_grade_level,
    grade_goal,
    school_goal,
    region_goal,
    organization_goal,
    nj_student_tier,
    teacher_name,
    course_number,
    course_name,
    teacher_name_current,
    results_type,
from {{ ref("rpt_tableau__state_assessments_dashboard_nj_preelim") }}
