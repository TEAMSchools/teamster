{% set academic_year = "2023" %}  -- CHANGE YEAR HERE ONLY

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

    students_nj as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation as school,
            e.student_number,
            e.state_studentnumber,
            e.lastfirst as student_name,
            e.grade_level,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status,
            e.is_504,
            e.lep_status,
            e.ethnicity as race_ethnicity,

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
            e.rn_year = 1
            and e.region in ('Camden', 'Newark')
            and e.schoolid != 999999
            and e.academic_year >= {{ academic_year }}
            and e.grade_level > 2
    ),

    schedules as (
        select
            e._dbt_source_relation,
            e.cc_academic_year,
            e.students_student_number,
            e.teacher_lastfirst as teacher_name,
            e.courses_course_name as course_name,
            e.cc_course_number as course_number,

            case
                e.courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,
        from {{ ref("base_powerschool__course_enrollments") }} as e
        where
            e.rn_credittype_year = 1
            and not e.is_dropped_section
            and e.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
            and e.cc_academic_year >= {{ academic_year }}
    ),

    assessments_nj as (
        select
            _dbt_source_relation,
            scale_score as score,
            performance_level as performance_band,
            academic_year,

            'Spring' as `admin`,
            'Spring' as season,

            safe_cast(state_student_identifier as string) as state_id,

            if(
                test_name
                in ('ELA Graduation Proficiency', 'Mathematics Graduation Proficiency'),
                'NJGPA',
                'NJSLA'
            ) as assessment_name,
            if(
                performance_level
                in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
                true,
                false
            ) as is_proficient,

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
            end as subject,
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
        from {{ ref("stg_pearson__student_list_report") }}
        where state_student_identifier is not null
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
    s.race_ethnicity,
    s.iep_status,
    s.is_504,
    s.lunch_status,
    s.ms_attended,
    s.lep_status,
    s.advisory,

    a.state_id,
    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
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

    'Preeliminary' as results_type,
    null as test_grade,
from students_nj as s
inner join
    assessments_nj as a
    on s.academic_year = a.academic_year
    and s.state_studentnumber = a.state_id
    and {{ union_dataset_join_clause(left_alias="s", right_alias="a") }}
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
