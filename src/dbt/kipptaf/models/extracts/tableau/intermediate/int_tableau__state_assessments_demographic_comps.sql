with
    assessment_scores as (
        select
            _dbt_source_relation,
            academic_year,
            localstudentidentifier,
            statestudentidentifier as state_id,
            assessment_name,
            is_proficient,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

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
            is_proficient,

            'Actual' as results_type,
            'KTAF FL' as district_state,

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

            test_type as assessment_name,

            if(
                performance_level
                in ('Met Expectations', 'Exceeded Expectations', 'Graduation Ready'),
                true,
                false
            ) as is_proficient,

            'Preliminary' as results_type,
            'KTAF NJ' as district_state,

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
            and test_type = 'NJSLA'
            and academic_year = {{ var("current_academic_year") }}
    )

-- NJ scores
select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.school_level,
    e.student_number,

    'KTAF' as district,

    a.district_state,
    a.assessment_name,
    a.test_code,

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
        e.gender when 'F' then 'Female' when 'M' then 'Male' when 'X' then 'Non-Binary'
    end as gender,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.localstudentidentifier = e.student_number
    and a.race_ethnicity is not null
    or a.gender is not null
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
    e.school_level,
    e.student_number,

    'KTAF' as district,

    a.district_state,
    a.assessment_name,
    a.test_code,

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

    if(e.lep_status, 'ML', 'Not ML') as lep_status,

    if(
        e.iep_status = 'Has IEP',
        'Students With Disabilities',
        'Students Without Disabilities'
    ) as iep_status,

    case
        e.gender when 'F' then 'Female' when 'M' then 'Male' when 'X' then 'Non-Binary'
    end as gender,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.state_id = e.state_studentnumber
    and e.race_ethnicity is not null
    or e.gender is not null
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
    e.school_level,
    e.student_number,

    'KTAF' as district,

    a.district_state,
    a.assessment_name,
    a.test_code,

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

    if(e.lep_status, 'ML', 'Not ML') as lep_status,

    if(
        e.iep_status = 'Has IEP',
        'Students With Disabilities',
        'Students Without Disabilities'
    ) as iep_status,

    case
        e.gender when 'F' then 'Female' when 'M' then 'Male' when 'X' then 'Non-Binary'
    end as gender,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.state_id = e.state_studentnumber
    and e.race_ethnicity is not null
    or e.gender is not null
    and a.academic_year = {{ var("current_academic_year") }}
    and a.results_type = 'Preliminary'
    and e.grade_level > 2
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
