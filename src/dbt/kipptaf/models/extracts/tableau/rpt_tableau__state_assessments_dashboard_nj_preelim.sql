with
    ms_grad_sub as (
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

    ms_grad as (
        select _dbt_source_relation, student_number, ms_attended,
        from ms_grad_sub
        where rn = 1
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

            case
                when e.spedlep like '%SPED%' then 'Has IEP' else 'No IEP'
            end as iep_status,

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
        where
            -- edit the academic_year to ensure the grade levels are correct for NJ
            -- preelim results
            e.academic_year = 2022
            and e.rn_year = 1
            and e.region in ('Camden', 'Newark')
            and e.grade_level > 2
            and e.schoolid != 999999
    ),

    schedules_current as (
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
            -- edit the academic_year to ensure the grade levels are correct for NJ
            -- preelim results
            cc_academic_year = 2022
            and rn_credittype_year = 1
            and not is_dropped_section
            and courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    schedules as (
        select
            e._dbt_source_relation,
            e.cc_academic_year,
            e.students_student_number,
            e.teacher_lastfirst as teacher_name,
            e.courses_course_name as course_name,
            e.cc_course_number as course_number,

            c.teacher_name as teacher_name_current,

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
        left join
            schedules_current as c
            on e.students_student_number = c.students_student_number
            and e.courses_credittype = c.courses_credittype
        where
            -- edit the academic_year only if the SIS has been rolled over to school
            -- year AFTER the preelim results school year
            e.cc_academic_year = 2022
            and e.rn_credittype_year = 1
            and not e.is_dropped_section
            and e.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    assessments_nj as (
        select
            safe_cast(state_student_identifier as string) as state_id,
            scale_score as score,
            performance_level as performance_band,

            -- change academic year here
            2022 as academic_year,
            'Spring' as admin,
            'Spring' as season,

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

    nj_final as (
        select
            s._dbt_source_relation,
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
            s.ms_attended,
            s.advisory,
            s.race_ethnicity,
            s.iep_status,
            s.is_504,
            s.lep_status,

            a.academic_year,
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
        from assessments_nj as a
        inner join
            students_nj as s
            on a.academic_year = s.academic_year
            and a.state_id = s.state_studentnumber
    ),

    state_comps as (
        select academic_year, test_name, test_code, region, city, state,
        from
            {{ ref("stg_assessments__state_test_comparison") }}
            pivot (avg(percent_proficient) for comparison_entity in ('City', 'State'))
    ),

    goals as (
        select
            academic_year,
            school_id,
            state_assessment_code,
            grade_level,
            grade_goal,
            school_goal,
            region_goal,
            organization_goal,
        from {{ ref("stg_assessments__academic_goals") }}
        where state_assessment_code is not null
    )

select
    safe_cast(s.academic_year as string) as academic_year,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.state_id,
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
    s.assessment_name,
    s.discipline,
    s.subject,
    s.test_code,
    '' as test_grade,
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

    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_name_current,

    'Preeliminary' as results_type,
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
