{% set comparison_entities = [
    {"label": "City", "prefix": "city"},
    {"label": "State", "prefix": "state"},
    {"label": "Neighborhood Schools", "prefix": "neighborhood_schools"},
] %}

with
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

        from {{ ref("stg_google_sheets__state_test_comparison") }}
        group by academic_year, test_name, test_code, region
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
            test_grade,

            'Actual' as results_type,

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
            null as iep_status,
            null as race_ethnicity,
            cast(assessment_grade as int) as test_grade,
            'Actual' as results_type,
            administration_window as `admin`,
            season,
            assessment_subject as `subject`,
            test_code,

        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null

        union all

        select
            _dbt_source_relation,
            academic_year,
            null as localstudentidentifier,
            cast(state_student_identifier as string) as state_id,

            if(
                test_name
                in ('ELA Graduation Proficiency', 'Mathematics Graduation Proficiency'),
                'NJGPA',
                'NJSLA'
            ) as assessment_name,

            case
                when test_name like '%Mathematics%'
                then 'Math'
                when test_name in ('Algebra I', 'Geometry')
                then 'Math'
                else 'ELA'
            end as discipline,

            scale_score as score,

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

            if(
                performance_level
                in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
                true,
                false
            ) as is_proficient,

            performance_level as performance_band,
            null as lep_status,
            null as is_504,
            null as iep_status,
            null as race_ethnicity,
            null as test_grade,

            'Preliminary' as results_type,
            'Spring' as `admin`,
            'Spring' as season,

            case
                when test_name like '%Mathematics%'
                then 'Mathematics'
                when test_name in ('Algebra I', 'Geometry')
                then 'Mathematics'
                else 'English Language Arts'
            end as subject,

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
        where
            state_student_identifier is not null
            and administration = 'Spring'
            and academic_year = {{ var("current_academic_year") }}
    )

-- NJ scores
select
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
    e.gender,
    e.lunch_status,
    e.gifted_and_talented,
    e.ms_attended,
    e.advisory,
    e.year_in_network,

    a.race_ethnicity,
    a.lep_status,
    a.is_504,
    a.iep_status,

    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
    a.test_grade,
    a.`admin`,
    a.season,
    a.score,
    a.performance_band,
    a.performance_band_level,
    a.is_proficient,
    a.results_type,

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

    max(e.grade_level) over (partition by e.student_number) as most_recent_grade_level,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.localstudentidentifier = e.student_number
    and a.academic_year >= {{ var("current_academic_year") - 7 }}
    and a.results_type = 'Actual'
    and e.grade_level > 2
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
left join
    state_comps as c
    on a.academic_year = c.academic_year
    and a.assessment_name = c.test_name
    and a.test_code = c.test_code
    and a.season = c.season
    and e.region = c.region
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on e.academic_year = g.academic_year
    and e.schoolid = g.school_id
    and a.test_code = g.state_assessment_code
left join
    schedules as m
    on a.academic_year = m.cc_academic_year
    and a.localstudentidentifier = m.students_student_number
    and a.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="a", right_alias="m") }}
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on a.academic_year = sf.academic_year
    and a.discipline = sf.discipline
    and a.localstudentidentifier = sf.student_number
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf") }}
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf2
    on a.academic_year = sf2.academic_year - 1
    and a.discipline = sf2.discipline
    and a.localstudentidentifier = sf2.student_number
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf2") }}

union all

-- FL scores
select
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
    e.gender,
    e.lunch_status,
    e.gifted_and_talented,
    e.ms_attended,
    e.advisory,
    e.year_in_network,

    e.race_ethnicity,
    e.lep_status,
    e.is_504,
    e.iep_status,

    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
    a.test_grade,
    a.`admin`,
    a.season,
    a.score,
    a.performance_band,
    a.performance_band_level,
    a.is_proficient,
    a.results_type,

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

    max(e.grade_level) over (partition by e.student_number) as most_recent_grade_level,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.state_id = e.state_studentnumber
    and a.academic_year >= {{ var("current_academic_year") - 7 }}
    and a.results_type = 'Actual'
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
    and e.grade_level > 2
    and e.region = 'Miami'
left join
    state_comps as c
    on a.academic_year = c.academic_year
    and a.assessment_name = c.test_name
    and a.test_code = c.test_code
    and a.season = c.season
    and e.region = c.region
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on e.academic_year = g.academic_year
    and e.schoolid = g.school_id
    and a.test_code = g.state_assessment_code
left join
    schedules as m
    on a.academic_year = m.cc_academic_year
    and a.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="a", right_alias="m") }}
    and e.student_number = m.students_student_number
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on a.academic_year = sf.academic_year
    and a.discipline = sf.discipline
    and a.state_id = sf.state_studentnumber
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf") }}
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf2
    on a.academic_year = sf2.academic_year - 1
    and a.discipline = sf2.discipline
    and a.state_id = sf2.state_studentnumber
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf2") }}
    /*
union all

-- NJ prelim scores
select
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
    e.gender,
    e.lunch_status,
    e.gifted_and_talented,
    e.ms_attended,
    e.advisory,
    e.year_in_network,

    a.race_ethnicity,
    a.lep_status,
    a.is_504,
    a.iep_status,

    a.assessment_name,
    a.discipline,
    a.subject,
    a.test_code,
    a.test_grade,
    a.`admin`,
    a.season,
    a.score,
    a.performance_band,
    a.performance_band_level,
    a.is_proficient,
    a.results_type,

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

    max(e.grade_level) over (partition by e.student_number) as most_recent_grade_level,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.state_id = e.state_studentnumber
    and a.academic_year = {{ var("current_academic_year") }}
    and a.results_type = 'Preliminary'
    and e.grade_level > 2
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
left join
    state_comps as c
    on a.academic_year = c.academic_year
    and a.assessment_name = c.test_name
    and a.test_code = c.test_code
    and a.season = c.season
    and e.region = c.region
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on e.academic_year = g.academic_year
    and e.schoolid = g.school_id
    and a.test_code = g.state_assessment_code
left join
    schedules as m
    on a.academic_year = m.cc_academic_year
    and a.localstudentidentifier = m.students_student_number
    and a.discipline = m.discipline
    and {{ union_dataset_join_clause(left_alias="a", right_alias="m") }}
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf
    on a.academic_year = sf.academic_year
    and a.discipline = sf.discipline
    and a.localstudentidentifier = sf.student_number
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf") }}
left join
    {{ ref("int_extracts__student_enrollments_subjects") }} as sf2
    on a.academic_year = sf2.academic_year - 1
    and a.discipline = sf2.discipline
    and a.localstudentidentifier = sf2.student_number
    and {{ union_dataset_join_clause(left_alias="a", right_alias="sf2") }}*/
    
