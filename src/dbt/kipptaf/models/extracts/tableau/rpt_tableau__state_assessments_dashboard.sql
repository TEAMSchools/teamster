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
            e.lunch_status as lunch_status,

            m.ms_attended,

            case
                when e.school_level in ('ES', 'MS')
                then advisory_name
                when school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            ms_grad as m
            on e.student_number = m.student_number
            and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
        where
            e.academic_year >= {{ var("current_academic_year") }} - 2
            and e.rn_year = 1
            and e.region in ('Camden', 'Newark')
            and e.grade_level > 2
            and e.schoolid != 999999
    ),

    students_fl as (
        select
            _dbt_source_relation,
            academic_year,
            region,
            schoolid,
            school_abbreviation as school,
            student_number,
            fleid,
            lastfirst as student_name,
            grade_level,
            enroll_status,
            is_out_of_district,
            gender,
            is_504,
            lep_status,
            lunch_status as lunch_status,
            case
                ethnicity when 'T' then 'T' when 'H' then 'H' else ethnicity
            end as race_ethnicity,
            case
                when spedlep like '%SPED%' then 'Has IEP' else 'No IEP'
            end as iep_status,
            case
                when school_level in ('ES', 'MS')
                then advisory_name
                when school_level = 'HS'
                then advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }}
        where
            academic_year >= {{ var("current_academic_year") }} - 2
            and rn_year = 1
            and region = 'Miami'
            and grade_level > 2
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
            cc_academic_year = {{ var("current_academic_year") }}
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
            e.cc_academic_year >= {{ var("current_academic_year") }} - 2
            and e.rn_credittype_year = 1
            and not e.is_dropped_section
            and e.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    assessments_nj as (
        select
            cast(academic_year as int) as academic_year,
            statestudentidentifier as state_id,
            assessment_name,
            subject_area as discipline,
            testcode as test_code,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,
            case period when 'FallBlock' then 'Fall' else period end as admin,
            case period when 'FallBlock' then 'Fall' else period end as season,
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
                when studentwithdisabilities in ('504', 'B') then true else false
            end as is_504,
            case
                englishlearnerel
                when 'Y'
                then true
                when 'N'
                then false
                when null
                then null
            end as lep_status,
            case
                when assessmentgrade in ('Grade 10', 'Grade 11')
                then right(assessmentgrade, 2)
                when assessmentgrade is null
                then null
                else right(assessmentgrade, 1)
            end as test_grade,
            case
                when subject = 'English Language Arts/Literacy'
                then 'English Language Arts'
                else subject
            end as subject,
        from {{ ref("int_pearson__all_assessments") }}
        where cast(academic_year as int) >= {{ var("current_academic_year") }} - 2
    ),

    assessments_fl as (
        select
            cast(academic_year as int) as academic_year,
            student_id as state_id,
            'FAST' as assessment_name,
            cast(assessment_grade as string) as test_grade,
            administration_window as admin,
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
            end as subject,
            case
                when assessment_subject = 'ELAReading'
                then concat('ELA0', assessment_grade)
                else concat('MAT0', assessment_grade)
            end as test_code,
        from {{ ref("stg_fldoe__fast") }}
        where achievement_level not in ('Insufficient to score', 'Invalidated')
        union all
        select
            cast(academic_year as int) as academic_year,
            fleid as state_id,
            'FSA' as assessment_name,
            cast(test_grade as string) as test_grade,
            'Spring' as admin,
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
    ),

    nj_final as (
        select
            s._dbt_source_relation,
            cast(a.academic_year as string) as academic_year,
            s.region,
            s.schoolid,
            s.school,
            s.student_number,
            s.state_studentnumber,
            a.state_id,
            s.student_name,
            s.grade_level,
            s.enroll_status,
            s.gender,
            a.race_ethnicity,
            a.iep_status,
            a.is_504,
            s.lunch_status,
            a.lep_status,
            s.ms_attended,
            s.advisory,

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
    ),

    fl_final as (
        select
            s._dbt_source_relation,
            cast(a.academic_year as string) as academic_year,
            s.region,
            s.schoolid,
            s.school,
            s.student_number,
            s.fleid as state_studentnumber,
            a.state_id,
            s.student_name,
            s.grade_level,
            s.enroll_status,
            s.gender,
            s.race_ethnicity,
            s.iep_status,
            s.is_504,
            s.lunch_status,
            s.lep_status,
            s.advisory,

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
            a.is_proficient
        from assessments_fl as a
        inner join
            students_fl as s
            on a.academic_year = s.academic_year
            and a.state_id = s.fleid
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
    s.academic_year,
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

    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_name_current,
from nj_final as s
left join
    state_comps as c
    on cast(s.academic_year as int) = c.academic_year
    and s.assessment_name = c.test_name
    and s.test_code = c.test_code
    and s.region = c.region
left join
    goals as g
    on cast(s.academic_year as int) = g.academic_year
    and s.schoolid = g.school_id
    and s.test_code = g.state_assessment_code
left join
    schedules as m
    on s.academic_year = cast(m.cc_academic_year as string)
    and s.student_number = m.students_student_number
    and s.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
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

    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_name_current,
from fl_final as s
left join
    state_comps as c
    on cast(s.academic_year as int) = c.academic_year
    and s.assessment_name = c.test_name
    and s.test_code = c.test_code
    and s.region = c.region
left join
    goals as g
    on cast(s.academic_year as int) = g.academic_year
    and s.schoolid = g.school_id
    and s.test_code = g.state_assessment_code
left join
    schedules as m
    on s.academic_year = cast(m.cc_academic_year as string)
    and s.student_number = m.students_student_number
    and s.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m") }}
