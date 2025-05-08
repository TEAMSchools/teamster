{% set comparison_entities = [
    {"label": "City", "prefix": "city"},
    {"label": "State", "prefix": "state"},
    {"label": "Neighborhood Schools", "prefix": "neighborhood_schools"},
] %}

with
    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.state_studentnumber,
            e.student_name,
            e.grade_level,
            e.cohort,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status,
            e.gifted_and_talented,
            e.iep_status,
            e.is_504,
            e.lep_status,
            e.ms_attended,
            e.advisory,
            e.race_ethnicity,
            e.year_in_network,

            max(e.grade_level) over (
                partition by e.student_number
            ) as most_recent_grade_level,

        from {{ ref("int_extracts__student_enrollments") }} as e
        where
            e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
    ),

    assessment_scores as (
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
            lep_status,
            is_504,
            iep_status,
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
        where
            academic_year >= {{ var("current_academic_year") - 7 }}
            and testscalescore is not null

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
            null as lep_status,
            null as is_504,
            'NA' as iep_status,
            'NA' as race_ethnicity,
            assessment_grade as test_grade,
            administration_window as `admin`,
            season,
            assessment_subject as `subject`,
            test_code,

        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    final_roster as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.academic_year_display,
            s.region,
            s.schoolid,
            s.school,
            s.student_number,
            s.state_studentnumber,
            s.student_name,
            s.grade_level,
            s.most_recent_grade_level,
            s.cohort,
            s.enroll_status,
            s.gender,
            s.lunch_status,
            s.gifted_and_talented,
            s.ms_attended,
            s.advisory,
            s.year_in_network,

            a.race_ethnicity,
            a.lep_status,
            a.is_504,
            a.iep_status,
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

        from assessment_scores as a
        inner join
            students as s
            on a.academic_year = s.academic_year
            and a.localstudentidentifier = s.student_number
        where s.region != 'Miami'

        union all

        select
            s._dbt_source_relation,
            s.academic_year,
            s.academic_year_display,
            s.region,
            s.schoolid,
            s.school,
            s.student_number,
            s.state_studentnumber,
            s.student_name,
            s.grade_level,
            s.most_recent_grade_level,
            s.cohort,
            s.enroll_status,
            s.gender,
            s.lunch_status,
            s.gifted_and_talented,
            s.ms_attended,
            s.advisory,
            s.year_in_network,
            s.race_ethnicity,
            s.lep_status,
            s.is_504,
            s.iep_status,

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

        from assessment_scores as a
        inner join
            students as s
            on a.academic_year = s.academic_year
            and a.state_id = s.state_studentnumber
        where s.region = 'Miami'
    ),

    schedules_current as (
        select
            c._dbt_source_relation,
            c.cc_academic_year,
            c.students_student_number,
            c.courses_credittype,
            c.teachernumber,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,

            s.abbreviation as school,

            case
                c.courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join
            {{ ref("stg_powerschool__schools") }} as s
            on c.cc_schoolid = s.school_number
        where
            c.cc_academic_year = {{ var("current_academic_year") }}
            and c.rn_credittype_year = 1
            and not c.is_dropped_section
            and c.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    schedules as (
        select
            e._dbt_source_relation,
            e.cc_academic_year,
            e.students_student_number,
            e.teachernumber,
            e.teacher_lastfirst as teacher_name,
            e.courses_course_name as course_name,
            e.cc_course_number as course_number,

            c.school as school_current,
            c.teachernumber as teachernumber_current,
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

    state_comps as (
        select
            academic_year,
            test_name,
            test_code,
            region,
            'Spring' as season,
            {% for entity in comparison_entities %}
                avg(
                    case
                        when comparison_entity = '{{ entity.label }}'
                        then percent_proficient
                    end
                ) as {{ entity.prefix }}_percent_proficient,
                avg(
                    case
                        when comparison_entity = '{{ entity.label }}'
                        then total_students
                    end
                ) as {{ entity.prefix }}_total_students
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_assessments__state_test_comparison") }}
        group by academic_year, test_name, test_code, region
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

        from {{ ref("int_assessments__academic_goals") }}
        where state_assessment_code is not null
    )

select
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.schoolid,
    s.school,
    s.student_number,
    s.state_studentnumber,
    s.student_name,
    s.grade_level,
    s.most_recent_grade_level,
    s.cohort,
    s.enroll_status,
    s.gender,
    s.lunch_status,
    s.gifted_and_talented,
    s.race_ethnicity,
    s.lep_status,
    s.is_504,
    s.iep_status,
    s.ms_attended,
    s.advisory,
    s.year_in_network,
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

    c.city_percent_proficient as proficiency_city,
    c.state_percent_proficient as proficiency_state,
    c.neighborhood_schools_percent_proficient as proficiency_neighborhood_schools,

    c.city_total_students as total_students_city,
    c.state_total_students as total_students_state,
    c.neighborhood_schools_total_students as total_students_neighborhood_schools,

    g.grade_level as assessment_grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,

    sf.nj_student_tier,
    sf.is_tutoring as tutoring_nj,

    sf2.iready_proficiency_eoy,

    m.teachernumber,
    m.teacher_name,
    m.course_number,
    m.course_name,
    m.school_current,
    m.teachernumber_current,
    m.teacher_name_current,

    'Actual' as results_type,

from final_roster as s
left join
    state_comps as c
    on s.academic_year = c.academic_year
    and s.assessment_name = c.test_name
    and s.test_code = c.test_code
    and s.region = c.region
    and s.season = c.season
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
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on s.academic_year = sf.academic_year
    and s.discipline = sf.discipline
    and s.student_number = sf.student_number
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf2
    on s.academic_year = sf2.academic_year - 1
    and s.discipline = sf2.discipline
    and s.student_number = sf2.student_number

union all

select
    academic_year,
    academic_year_display,
    region,
    schoolid,
    school,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    null as most_recent_grade_level,
    cohort,
    enroll_status,
    gender,
    lunch_status,
    gifted_and_talented,
    race_ethnicity,
    lep_status,
    is_504,
    iep_status,
    ms_attended,
    advisory,
    year_in_network,
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
    proficiency_neighborhood_schools,

    total_students_city,
    total_students_state,
    total_students_neighborhood_schools,

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
    null as school_current,

    teacher_number_current as teachernumber_current,
    teacher_name_current,

    results_type,

from {{ ref("rpt_tableau__state_assessments_dashboard_nj_prelim") }}
