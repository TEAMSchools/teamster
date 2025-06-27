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

            period as season,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

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
                race_ethnicity
                when 'B'
                then 'African American'
                when 'A'
                then 'Asian'
                when 'I'
                then 'American Indian'
                when 'H'
                then 'Hispanic'
                when 'P'
                then 'Native Hawaiian'
                when 'T'
                then 'Other'
                when 'W'
                then 'White'
            end as race_ethnicity,

            if(lep_status, 'ML', 'Not ML') as lep_status,

            if(
                iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

        from {{ ref("int_pearson__all_assessments") }}
        where academic_year >= 2018 and testscalescore is not null and period = 'Spring'

        union all

        select
            _dbt_source_relation,
            academic_year,
            null as localstudentidentifier,
            student_id as state_id,
            assessment_name,
            discipline,
            is_proficient,
            season,
            'Actual' as results_type,
            'KTAF FL' as district_state,
            assessment_subject as `subject`,
            test_code,

            null as race_ethnicity,
            null as lep_status,
            null as iep_status,

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

            'Spring' as season,
            'Preliminary' as results_type,
            'KTAF NJ' as district_state,

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

            null as race_ethnicity,
            null as lep_status,
            null as iep_status,

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
            e.grade_level,

            a.district_state,
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

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

            a.race_ethnicity,
            a.lep_status,
            a.iep_status,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Non-Binary'
            end as gender,

        from assessment_scores as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.localstudentidentifier = e.student_number
            and a.academic_year >= {{ var("current_academic_year") - 7 }}
            and a.results_type = 'Actual'
            and e.grade_level > 2
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
    /*
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
            e.grade_level,

            a.district_state,
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

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

            case
                e.race_ethnicity
                when 'B'
                then 'African American'
                when 'A'
                then 'Asian'
                when 'I'
                then 'American Indian'
                when 'H'
                then 'Hispanic'
                when 'P'
                then 'Native Hawaiian'
                when 'T'
                then 'Other'
                when 'W'
                then 'White'
            end as race_ethnicity,


            if(e.lep_status = 'ML', 'Not ML') as lep_status,

            if(
                e.iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Non-Binary'
            end as gender,

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
            e.grade_level,

            a.district_state,
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

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

            case
                e.race_ethnicity
                when 'B'
                then 'African American'
                when 'A'
                then 'Asian'
                when 'I'
                then 'American Indian'
                when 'H'
                then 'Hispanic'
                when 'P'
                then 'Native Hawaiian'
                when 'T'
                then 'Other'
                when 'W'
                then 'White'
            end as race_ethnicity,

            if(e.lep_status = 'ML', 'Not ML') as lep_status,

            if(
                e.iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Non-Binary'
            end as gender,

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

            round(percent_proficient * total_students, 0) as total_proficient_students,

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        where comparison_demographic_subgroup != 'SE Accommodation'
    ),

    region_calcs as (
        select
            academic_year,
            district,
            district_state,
            region,
            school_level,
            assessment_band,
            grade_range_band,
            grade_level,
            assessment_name,
            discipline,
            `subject`,
            test_code,
            gender,
            lunch_status,
            race_ethnicity,
            lep_status,
            iep_status,

            avg(is_proficient_int) as percent_proficient,

            count(student_number) as total_students,

            round(
                avg(is_proficient_int) * count(student_number), 0
            ) as total_proficient_students,

        from roster
        group by
            rollup (
                academic_year,
                district,
                district_state,
                region,
                school_level,
                assessment_band,
                grade_range_band,
                grade_level,
                assessment_name,
                discipline,
                `subject`,
                test_code,
                gender,
                lunch_status,
                race_ethnicity,
                lep_status,
                iep_status
            )
    ),

    district_calcs as (
        -- Total All Students by Test Code for district_state
        select
            academic_year,
            assessment_name,
            test_code,
            region,
            district_state as comparison_entity,
            'Total' as comparison_demographic_group,
            'All Students' as comparison_demographic_subgroup,

            row_number() over (
                partition by academic_year, assessment_name, test_code, district_state
            ) as rn,

            sum(total_proficient_students) over (
                partition by academic_year, assessment_name, test_code, district_state
            ) as total_proficient_students,

            sum(total_students) over (
                partition by academic_year, assessment_name, test_code, district_state
            ) as total_students,

            safe_divide(
                sum(total_proficient_students) over (
                    partition by
                        academic_year, assessment_name, test_code, district_state
                ),
                sum(total_students) over (
                    partition by
                        academic_year, assessment_name, test_code, district_state
                )
            ) as percent_proficient,

        from region_calcs
        where
            academic_year is not null
            and district_state is not null
            and test_code is not null
            and gender is null
            and lunch_status is null
            and race_ethnicity is null
            and lep_status is null
            and iep_status is null
        qualify rn = 1

        union all

        -- Total School Level by Test Code for district_state
        select
            academic_year,
            assessment_name,
            test_code,
            region,
            district_state as comparison_entity,
            'Total' as comparison_demographic_group,
            school_level as comparison_demographic_subgroup,

            row_number() over (
                partition by
                    academic_year,
                    assessment_name,
                    school_level,
                    test_code,
                    district_state
            ) as rn,

            sum(total_proficient_students) over (
                partition by
                    academic_year,
                    assessment_name,
                    school_level,
                    test_code,
                    district_state
            ) as total_proficient_students,

            sum(total_students) over (
                partition by
                    academic_year,
                    assessment_name,
                    school_level,
                    test_code,
                    district_state
            ) as total_students,

            safe_divide(
                sum(total_proficient_students) over (
                    partition by
                        academic_year,
                        assessment_name,
                        school_level,
                        test_code,
                        district_state
                ),
                sum(total_students) over (
                    partition by
                        academic_year,
                        assessment_name,
                        school_level,
                        test_code,
                        district_state
                )
            ) as percent_proficient,

        from region_calcs
        where
            academic_year is not null
            and district_state is not null
            and test_code is not null
            and gender is null
            and lunch_status is null
            and race_ethnicity is null
            and lep_status is null
            and iep_status is null
        qualify rn = 1

        union all

        -- Total Grade Range Band by Test Code for district_state
        select
            academic_year,
            assessment_name,
            test_code,
            region,
            district_state as comparison_entity,
            'Total' as comparison_demographic_group,
            grade_range_band as comparison_demographic_subgroup,

            row_number() over (
                partition by
                    academic_year,
                    assessment_name,
                    grade_range_band,
                    test_code,
                    district_state
            ) as rn,

            sum(total_proficient_students) over (
                partition by
                    academic_year,
                    assessment_name,
                    grade_range_band,
                    test_code,
                    district_state
            ) as total_proficient_students,

            sum(total_students) over (
                partition by
                    academic_year,
                    assessment_name,
                    grade_range_band,
                    test_code,
                    district_state
            ) as total_students,

            safe_divide(
                sum(total_proficient_students) over (
                    partition by
                        academic_year,
                        assessment_name,
                        grade_range_band,
                        test_code,
                        district_state
                ),
                sum(total_students) over (
                    partition by
                        academic_year,
                        assessment_name,
                        grade_range_band,
                        test_code,
                        district_state
                )
            ) as percent_proficient,

        from region_calcs
        where
            academic_year is not null
            and district_state is not null
            and test_code is not null
            and gender is null
            and lunch_status is null
            and race_ethnicity is null
            and lep_status is null
            and iep_status is null
        qualify rn = 1
    )

select
    academic_year,
    assessment_name,
    test_code,
    region,
    comparison_entity,
    comparison_demographic_group,
    comparison_demographic_subgroup,

    total_proficient_students,
    total_students,

    percent_proficient,

from
    district_calcs
    /*
union all

select
    academic_year,
    test_name as assessment_name,
    test_code,
    region,
    comparison_entity,
    comparison_demographic_group,
    comparison_demographic_subgroup,

    total_proficient_students,
    total_students,    

    percent_proficient,

from comps
*/
    
