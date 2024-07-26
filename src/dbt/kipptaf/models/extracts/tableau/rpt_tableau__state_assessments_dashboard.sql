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
            e.cohort,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status,

            m.ms_attended,

            case
                when e.school_level in ('ES', 'MS')
                then e.advisory_name
                when e.school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            ms_grad_sub as m
            on e.student_number = m.student_number
            and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
            and m.rn = 1
        where
            e.academic_year >= {{ var("current_academic_year") - 7 }}
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
            cohort,
            enroll_status,
            is_out_of_district,
            gender,
            is_504,
            lep_status,
            lunch_status,
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
            academic_year >= {{ var("current_academic_year") - 7 }}
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
            teachernumber,
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

            c.teachernumber as teacher_id_current,
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
            e.cc_academic_year >= {{ var("current_academic_year") - 7 }}
            and e.rn_credittype_year = 1
            and not e.is_dropped_section
            and e.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    assessments_nj as (
        select
            academic_year,
            statestudentidentifier as state_id,
            assessment_name,
            discipline,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,
            testperformancelevel_text as performance_band,
            lep_status,
            iep_status,
            is_504,
            race_ethnicity,

            safe_cast(test_grade as string) as test_grade,

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
        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= {{ var("current_academic_year") - 7 }}
    ),

    assessments_fl as (
        select
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

    state_comps as (
        select academic_year, test_name, test_code, region, city, `state`,
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
    sf.tutoring_nj,

    sf2.iready_proficiency_eoy,

    m.teachernumber,
    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_id_current,
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
left join
    {{ ref("int_reporting__student_filters") }} as sf2
    on s.academic_year = sf2.academic_year - 1
    and s.discipline = sf2.discipline
    and s.student_number = sf2.student_number

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
    sf.tutoring_nj,

    sf2.iready_proficiency_eoy,

    m.teachernumber,
    m.teacher_name,
    m.course_number,
    m.course_name,
    m.teacher_id_current,
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
left join
    {{ ref("int_reporting__student_filters") }} as sf2
    on s.academic_year = sf2.academic_year - 1
    and s.discipline = sf2.discipline
    and s.student_number = sf2.student_number

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
    `subject`,
    test_code,

    cast(test_grade as string) as test_grade,

    `admin`,
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
    tutoring_nj,
    iready_proficiency_eoy,
    teachernumber,
    teacher_name,
    course_number,
    course_name,
    teacher_id_current,
    teacher_name_current,
    results_type,
from {{ ref("rpt_tableau__state_assessments_dashboard_nj_preelim") }}
