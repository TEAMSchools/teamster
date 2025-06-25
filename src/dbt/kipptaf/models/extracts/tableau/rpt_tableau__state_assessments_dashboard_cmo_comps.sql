with
    assessment_scores as (
        select
            _dbt_source_relation,
            academic_year,
            localstudentidentifier,
            statestudentidentifier as state_id,
            assessment_name,
            discipline,
            is_proficient,
            lep_status,
            is_504,
            iep_status,
            race_ethnicity,

            'Actual' as results_type,

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
            is_proficient,
            null as lep_status,
            null as is_504,
            null as iep_status,
            null as race_ethnicity,
            'Actual' as results_type,
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

            if(
                performance_level
                in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
                true,
                false
            ) as is_proficient,

            null as lep_status,
            null as is_504,
            null as iep_status,
            null as race_ethnicity,

            'Preliminary' as results_type,
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
    ),

    roster as (
        -- NJ scores
        select
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.school_level,
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
            a.season,
            a.results_type,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.localstudentidentifier = e.student_number
            and a.academic_year >= {{ var("current_academic_year") - 7 }}
            and a.results_type = 'Actual'
            and a.season = 'Spring'
            and e.grade_level > 2
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}

        union all

        -- FL scores
        select
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.school_level,
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
            a.season,
            a.results_type,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.state_id = e.state_studentnumber
            and a.academic_year >= {{ var("current_academic_year") - 7 }}
            and a.results_type = 'Actual'
            and a.season = 'Spring'
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
            and e.grade_level > 2
            and e.region = 'Miami'

        union all

        -- NJ prelim scores
        select
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.school_level,
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
            a.season,
            a.results_type,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.state_id = e.state_studentnumber
            and a.academic_year = {{ var("current_academic_year") }}
            and a.results_type = 'Preliminary'
            and a.season = 'Spring'
            and e.grade_level > 2
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
    )

select
    academic_year,
    assessment_name,
    test_code,
    region,
    results_type,

    avg(is_proficient_int) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__total__all__students__percent_proficient,

    count(student_number) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__total__all__students__total_students,

    avg(if(race_ethnicity = 'B', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__african_american__percent_proficient,

    count(if(race_ethnicity = 'B', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__african_american__total_students,

    avg(if(race_ethnicity = 'A', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__asian__percent_proficient,

    count(if(race_ethnicity = 'A', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__asian__total_students,

    avg(if(race_ethnicity = 'I', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__american_indian__percent_proficient,

    count(if(race_ethnicity = 'I', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__american_indian__total_students,

    avg(if(race_ethnicity = 'H', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__hispanic__percent_proficient,

    count(if(race_ethnicity = 'H', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__hispanic__total_students,

    avg(if(race_ethnicity = 'W', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__white__percent_proficient,

    avg(if(race_ethnicity = 'P', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__native_hawaiian__percent_proficient,

    count(if(race_ethnicity = 'P', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__native_hawaiian__total_students,

    count(if(race_ethnicity = 'W', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__aggregate_ethnicity__white__total_students,

    avg(if(gender = 'M', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__gender__male__percent_proficient,

    count(if(gender = 'M', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__gender__male__total_students,

    avg(if(gender = 'F', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__gender__female__percent_proficient,

    count(if(gender = 'F', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__gender__female__total_students,

    avg(if(iep_status = 'Has IEP', is_proficient_int, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__subgroup__students_with_disabilities__percent_proficient,

    count(if(iep_status = 'Has IEP', student_number, null)) over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as region__subgroup__students_with_disabilities__total_students,

    row_number() over (
        partition by academic_year, assessment_name, test_code, region, results_type
    ) as rn,

from roster
qualify rn = 1
