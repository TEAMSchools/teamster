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
            period as season,

            'Actual' as results_type,

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
            and period = 'Spring'

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
            season,
            'Actual' as results_type,
            assessment_subject as `subject`,
            test_code,

        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null and season = 'Spring'

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

            'Spring' as season,
            'Preliminary' as results_type,

            case
                when test_name like '%Mathematics%'
                then 'Mathematics'
                when test_name in ('Algebra I', 'Geometry')
                then 'Mathematics'
                else 'English Language Arts'
            end as `subject`,

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
            e.gender,
            e.lunch_status,

            a.race_ethnicity,
            a.lep_status,
            a.is_504,
            a.iep_status,

            a.assessment_name,
            a.discipline,
            a.`subject`,
            a.test_code,
            a.season,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as assessment_band,

            if(e.grade_level >= 9, 'HS', '3-8') as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.localstudentidentifier = e.student_number
            and a.academic_year >= {{ var("current_academic_year") - 7 }}
            and a.results_type = 'Actual'
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
            e.gender,
            e.lunch_status,

            e.race_ethnicity,
            e.lep_status,
            e.is_504,
            e.iep_status,

            a.assessment_name,
            a.discipline,
            a.`subject`,
            a.test_code,
            a.season,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as assessment_band,

            if(e.grade_level >= 9, 'HS', '3-8') as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

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
    /*
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
            e.gender,
            e.lunch_status,

            e.race_ethnicity,
            e.lep_status,
            e.is_504,
            e.iep_status,

            a.assessment_name,
            a.discipline,
            a.`subject`,
            a.test_code,
            a.season,

            'KTAF' as district,

            case
                when e.grade_level >= 9
                then 'HS'
                when e.grade_level >= 5
                then '5-8'
                when e.grade_level >= 3
                then '3-4'
            end as assessment_band,

            if(e.grade_level >= 9, 'HS', '3-8') as grade_range_band,

            if(a.is_proficient, 1, 0) as is_proficient_int,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.state_id = e.state_studentnumber
            and a.academic_year = {{ var("current_academic_year") }}
            and a.results_type = 'Preliminary'
            and e.grade_level > 2
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}*/
    ),

    comps as (
        select
            *,

            case
                left(test_code, 3)
                when 'SCI'
                then 'Science'
                when 'ELA'
                then 'ELA'
                when 'SOC'
                then 'Civics'
                else 'Math'
            end as discipline,

            case
                when left(test_code, 3) = 'SCI'
                then 'Science'
                when left(test_code, 3) = 'English Language Arts'
                then 'ELA'
                when left(test_code, 3) = 'SOC'
                then 'Civics'
                when test_code = 'GEO01'
                then 'Geometry'
                when test_code = 'ALG01'
                then 'Algebra I'
                when test_code = 'ALG02'
                then 'Algebra II'
                else 'Mathematics'
            end as `subject`,

            case
                when
                    test_code in (
                        'ELAGP',
                        'MATGP',
                        'GEO01',
                        'ALG02',
                        'ALG01',
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'SCI11'
                    )
                then 'HS'
                when cast(right(test_code, 2) as numeric) >= 5
                then 'MS'
                when cast(right(test_code, 2) as numeric) >= 3
                then 'ES'
            end as school_level,

            case
                when
                    test_code in (
                        'ELAGP',
                        'MATGP',
                        'GEO01',
                        'ALG02',
                        'ALG01',
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'SCI11'
                    )
                then 'HS'
                when cast(right(test_code, 2) as numeric) >= 5
                then '5-8'
                when cast(right(test_code, 2) as numeric) >= 3
                then '3-4'
            end as assessment_band,

            case
                when
                    test_code in (
                        'ELAGP',
                        'MATGP',
                        'GEO01',
                        'ALG02',
                        'ALG01',
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'SCI11'
                    )
                then 'HS'
                when cast(right(test_code, 2) as numeric) >= 3
                then '3-8'
            end as grade_range_band,

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        where
            comparison_demographic_subgroup
            not in ('Grade - 08', 'Grade - 09', 'Grade - 10', 'SE Accommodation')
    ),

    region_calcs as (
        select
            academic_year,
            assessment_name,
            discipline,
            `subject`,
            test_code,
            region,
            school_level,
            assessment_band,
            grade_range_band,

            'Region' as comparison_entity,

            -- region all rollups
            avg(is_proficient_int) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__total__all__students__percent_proficient,

            count(student_number) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__total__all__students__total_students,

            -- region school level / discipline rollups
            avg(is_proficient_int) over (
                partition by
                    academic_year, region, assessment_name, school_level, discipline
            ) as region__total__school_level_discipline__percent_proficient,

            count(student_number) over (
                partition by
                    academic_year, region, assessment_name, school_level, discipline
            ) as region__total__school_level_discipline__total_students,

            -- region grade range band / discipline rollups
            avg(is_proficient_int) over (
                partition by
                    academic_year, region, assessment_name, grade_range_band, discipline
            ) as region__total__grade_range_band_discipline__percent_proficient,

            count(student_number) over (
                partition by
                    academic_year, region, assessment_name, grade_range_band, discipline
            ) as region__total__grade_range_band_discipline__total_students,

            -- region assessment band / discipline rollups
            avg(is_proficient_int) over (
                partition by
                    academic_year, region, assessment_name, assessment_band, discipline
            ) as region__total__assessment_band_discipline__percent_proficient,

            count(student_number) over (
                partition by
                    academic_year, region, assessment_name, assessment_band, discipline
            ) as region__total__assessment_band_discipline__total_students,

            -- region aggregate ethnicity
            avg(if(race_ethnicity = 'B', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__african_american__percent_proficient,

            count(if(race_ethnicity = 'B', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__african_american__total_students,

            avg(if(race_ethnicity = 'A', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__asian__percent_proficient,

            count(if(race_ethnicity = 'A', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__asian__total_students,

            avg(if(race_ethnicity = 'I', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__american_indian__percent_proficient,

            count(if(race_ethnicity = 'I', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__american_indian__total_students,

            avg(if(race_ethnicity = 'H', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__hispanic__percent_proficient,

            count(if(race_ethnicity = 'H', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__hispanic__total_students,

            avg(if(race_ethnicity = 'P', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__native_hawaiian__percent_proficient,

            count(if(race_ethnicity = 'P', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__native_hawaiian__total_students,

            avg(if(race_ethnicity = 'W', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__white__percent_proficient,

            count(if(race_ethnicity = 'W', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__white__total_students,

            avg(if(race_ethnicity = 'T', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__other__percent_proficient,

            count(if(race_ethnicity = 'T', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__aggregate_ethnicity__other__total_students,

            -- region gender
            avg(if(gender = 'M', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__gender__male__percent_proficient,

            count(if(gender = 'M', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__gender__male__total_students,

            avg(if(gender = 'F', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__gender__female__percent_proficient,

            count(if(gender = 'F', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__gender__female__total_students,

            -- region iep
            avg(if(iep_status = 'Has IEP', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__students_with_disabilities__percent_proficient,

            count(if(iep_status = 'Has IEP', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__students_with_disabilities__total_students,

            -- region lunch status
            avg(if(lunch_status in ('F', 'R'), is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__economically_disadvantaged__percent_proficient,

            count(if(lunch_status in ('F', 'R'), student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__economically_disadvantaged__total_students,

            avg(if(lunch_status = 'P', is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__non_economically_disadvantaged__percent_proficient,

            count(if(lunch_status = 'P', student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__non_economically_disadvantaged__total_students,

            -- region ml
            avg(if(lep_status, is_proficient_int, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__ml_percent_proficient,

            count(if(lep_status, student_number, null)) over (
                partition by academic_year, region, assessment_name, test_code
            ) as region__subgroup__ml__total_students,

            row_number() over (
                partition by academic_year, region, assessment_name, test_code
            ) as rn,

        from roster
        qualify rn = 1
    )

select
    academic_year,
    assessment_name,
    discipline,
    `subject`,
    test_code,
    region,
    school_level,
    assessment_band,
    grade_range_band,
    comparison_entity,

    /* unpivot cols */
    replace(
        regexp_extract(attribute, r'^(.*?)__'), '_', ' '
    ) as comparison_demographic_group,
    replace(
        regexp_extract(attribute, r'__(.*)$'), '_', ' '
    ) as comparison_demographic_subgroup,
    percent_proficient,
    total_students,

from
    region_calcs unpivot (
        (percent_proficient, total_students) for attribute in (
            (
                region__total__all__students__percent_proficient,
                region__total__all__students__total_students
            ) as 'Total__All_Students',
            (
                region__total__school_level_discipline__percent_proficient,
                region__total__school_level_discipline__total_students
            ) as 'Total__School_Level_Discipline',
            (
                region__total__grade_range_band_discipline__percent_proficient,
                region__total__grade_range_band_discipline__total_students
            ) as 'Total__Grade_Range_Band_Discipline',
            (
                region__total__assessment_band_discipline__percent_proficient,
                region__total__assessment_band_discipline__total_students
            ) as 'Total__Assessment_Band_Discipline',
            (
                region__aggregate_ethnicity__african_american__percent_proficient,
                region__aggregate_ethnicity__african_american__total_students
            ) as 'Total__Aggregate_Ethnicity__African_American',
            (
                region__aggregate_ethnicity__asian__percent_proficient,
                region__aggregate_ethnicity__asian__total_students
            ) as 'Aggregate_Ethnicity__Asian',
            (
                region__aggregate_ethnicity__american_indian__percent_proficient,
                region__aggregate_ethnicity__american_indian__total_students
            ) as 'Aggregate_Ethnicity__American_Indian',
            (
                region__aggregate_ethnicity__hispanic__percent_proficient,
                region__aggregate_ethnicity__hispanic__total_students
            ) as 'Aggregate_Ethnicity__Hispanic',
            (
                region__aggregate_ethnicity__native_hawaiian__percent_proficient,
                region__aggregate_ethnicity__native_hawaiian__total_students
            ) as 'Aggregate_Ethnicity__Native_Hawaiian',
            (
                region__aggregate_ethnicity__white__percent_proficient,
                region__aggregate_ethnicity__white__total_students
            ) as 'Aggregate_Ethnicity__White',
            (
                region__aggregate_ethnicity__other__percent_proficient,
                region__aggregate_ethnicity__other__total_students
            ) as 'Aggregate_Ethnicity__Other',
            (
                region__gender__male__percent_proficient,
                region__gender__male__total_students
            ) as 'Gender__Male',
            (
                region__gender__female__percent_proficient,
                region__gender__female__total_students
            ) as 'Gender__Female',
            (
                region__subgroup__students_with_disabilities__percent_proficient,
                region__subgroup__students_with_disabilities__total_students
            ) as 'Subgroup__Students_With_Disabilities',
            (
                region__subgroup__economically_disadvantaged__percent_proficient,
                region__subgroup__economically_disadvantaged__total_students
            ) as 'Subgroup__Economically_Disadvantaged',
            (
                region__subgroup__non_economically_disadvantaged__percent_proficient,
                region__subgroup__non_economically_disadvantaged__total_students
            ) as 'Subgroup__Non_Economically_Disadvantaged',
            (
                region__subgroup__ml_percent_proficient,
                region__subgroup__ml__total_students
            ) as 'Subgroup__ML'
        )
    )

union all

select
    academic_year,
    test_name as assessment_name,
    discipline,
    `subject`,
    test_code,
    region,
    school_level,
    assessment_band,
    grade_range_band,
    comparison_entity,
    comparison_demographic_group,
    comparison_demographic_subgroup,
    percent_proficient,
    total_students

from comps
