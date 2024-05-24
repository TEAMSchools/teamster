with
    ms_grad as (
        select
            _dbt_source_relation,
            student_number,
            school_abbreviation as ms_attended,

            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'MS'
    ),

    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation as school,
            e.student_number,
            e.state_studentnumber,
            e.fleid,
            e.lastfirst as student_name,
            e.grade_level,
            e.enroll_status,
            e.is_out_of_district,
            e.ethnicity as race_ethnicity,
            e.gender,
            e.lunch_status,
            e.is_504,
            e.lep_status,

            m.ms_attended,

            if(e.spedlep like '%SPED%', 'Has IEP', 'No IEP') as iep_status,

            case
                when e.school_level in ('ES', 'MS')
                then e.advisory_name
                when e.school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            ms_grad as m
            on e.student_number = m.student_number
            and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
            and m.rn = 1
        where
            e.academic_year >= {{ var("current_academic_year") }} - 7
            and e.rn_year = 1
            and e.grade_level > 2
            and e.schoolid != 999999
    ),

    schedules as (
        select
            _dbt_source_relation,
            cc_academic_year,
            students_student_number,
            courses_credittype,
            teacher_lastfirst as teacher_name,
            courses_course_name as course_name,
            cc_course_number as course_number,
            case
                courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year >= {{ var("current_academic_year") }} - 7
            and rn_credittype_year = 1
            and not is_dropped_section
            and courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
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

            if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,
            if(`period` = 'FallBlock', 'Fall', `period`) as season,
            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
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
            case
                englishlearnerel when 'Y' then true when 'N' then false
            end as lep_status,
        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= {{ var("current_academic_year") }} - 7
    ),

    assessments_fl as (
        select
            _dbt_source_relation,
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
            _dbt_source_relation,
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
            end as `subject`,
        from {{ ref("stg_fldoe__fsa") }}
        where performance_level is not null

        union all

        select
            _dbt_source_relation,
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

            if(test_name = 'B.E.S.T.Algebra1', 'Math', test_name) as discipline,
            if(test_name = 'B.E.S.T.Algebra1', 'Algebra I', test_name) as `subject`,
        from {{ ref("stg_fldoe__eoc") }}
        where not is_invalidated

        union all

        select
            _dbt_source_relation,
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
            'Science' as `subject`,
        from {{ ref("stg_fldoe__science") }}
    ),

    state_comps as (
        select academic_year, test_name, test_code, region, city, `state`,
        from
            {{ ref("stg_assessments__state_test_comparison") }}
            pivot (avg(percent_proficient) for comparison_entity in ('City', 'State'))
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
    s.enroll_status,
    s.gender,
    s.lunch_status,
    s.advisory,
    s.ms_attended,

    a.race_ethnicity,
    a.lep_status,
    a.iep_status,
    a.is_504,
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

    m.teacher_name,
    m.course_number,
    m.course_name,

    mcur.teacher_name as teacher_name_current,

    c.city as proficiency_city,
    c.state as proficiency_state,

    g.grade_level as assessment_grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    'Actual' as results_type,
from students as s
inner join
    assessments_nj as a
    on s.academic_year = a.academic_year
    and s.state_studentnumber = a.state_id
    and {{ union_dataset_join_clause(left_alias="s", right_alias="a") }}
    and a.score is not null
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.student_number = m.students_student_number
    and a.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
left join
    schedules as mcur
    on s.student_number = mcur.students_student_number
    and a.discipline = mcur.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="mcur") }}
    and mcur.cc_academic_year = {{ var("current_academic_year") }}
left join
    state_comps as c
    on s.academic_year = c.academic_year
    and s.region = c.region
    and a.assessment_name = c.test_name
    and a.test_code = c.test_code
left join
    {{ ref("stg_assessments__academic_goals") }} as g
    on s.academic_year = g.academic_year
    and s.schoolid = g.school_id
    and a.test_code = g.state_assessment_code

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
    s.enroll_status,
    s.gender,
    s.lunch_status,
    s.advisory,
    s.ms_attended,
    s.race_ethnicity,
    s.lep_status,
    s.iep_status,
    s.is_504,

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

    m.teacher_name,
    m.course_number,
    m.course_name,

    mcur.teacher_name as teacher_name_current,

    c.city as proficiency_city,
    c.state as proficiency_state,

    g.grade_level as assessment_grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    'Actual' as results_type,
from students as s
inner join
    assessments_fl as a
    on s.academic_year = a.academic_year
    and s.fleid = a.state_id
    and {{ union_dataset_join_clause(left_alias="s", right_alias="a") }}
    and a.score is not null
left join
    schedules as m
    on s.academic_year = m.cc_academic_year
    and s.student_number = m.students_student_number
    and a.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
left join
    schedules as mcur
    on s.student_number = mcur.students_student_number
    and a.discipline = mcur.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="mcur") }}
    and mcur.cc_academic_year = {{ var("current_academic_year") }}
left join
    state_comps as c
    on s.academic_year = c.academic_year
    and s.region = c.region
    and a.assessment_name = c.test_name
    and a.test_code = c.test_code
left join
    {{ ref("stg_assessments__academic_goals") }} as g
    on s.academic_year = g.academic_year
    and s.schoolid = g.school_id
    and a.test_code = g.state_assessment_code

union all

select
    academic_year,
    region,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    enroll_status,
    gender,
    race_ethnicity,
    iep_status,
    is_504,
    lunch_status,
    lep_status,
    advisory,
    ms_attended,
    state_id,
    assessment_name,
    discipline,
    `subject`,
    test_code,
    test_grade,
    `admin`,
    season,
    score,
    performance_band,
    performance_band_level,
    is_proficient,
    teacher_name,
    course_number,
    course_name,
    teacher_name_current,
    proficiency_city,
    proficiency_state,
    assessment_grade_level,
    grade_goal,
    school_goal,
    region_goal,
    organization_goal,
    results_type,
from {{ ref("rpt_tableau__state_assessments_dashboard_nj_preelim") }}
