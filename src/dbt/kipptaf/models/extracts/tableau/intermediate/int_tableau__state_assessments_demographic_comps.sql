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
                when race_ethnicity = 'B'
                then 'African American'
                when race_ethnicity = 'A'
                then 'Asian'
                when race_ethnicity = 'I'
                then 'American Indian'
                when race_ethnicity = 'H'
                then 'Hispanic'
                when race_ethnicity = 'P'
                then 'Native Hawaiian'
                when race_ethnicity = 'T'
                then 'Other'
                when race_ethnicity = 'W'
                then 'White'
                when race_ethnicity is null
                then 'Blank'
            end as aggregate_ethnicity,

            if(lep_status, 'ML', 'Not ML') as ml_status,

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

            null as aggregate_ethnicity,
            null as ml_status,
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

            null as aggregate_ethnicity,
            null as ml_status,
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
    e.region,
    e.student_number,

    a.district_state,
    a.assessment_name,

    case
        when a.test_code = 'ALG01'
        then concat(a.test_code, '_', e.school_level)
        else a.test_code
    end as test_code,

    if(a.is_proficient, 1, 0) as is_proficient_int,

    if(
        e.lunch_status in ('F', 'R'),
        'Economically Disadvantaged',
        'Non Economically Disadvantaged'
    ) as lunch_status,

    a.aggregate_ethnicity,
    a.ml_status,
    a.iep_status,

    case
        e.gender when 'F' then 'Female' when 'M' then 'Male' when 'X' then 'Non-Binary'
    end as gender,

from assessment_scores as a
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.localstudentidentifier = e.student_number
    and a.academic_year >= {{ var("current_academic_year") - 7 }}
    and a.results_type = 'Actual'
    and e.grade_level > 2
    and e.school_level != 'OD'
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}

union all

-- FL scores
select
    e.academic_year,
    e.region,
    e.student_number,

    a.district_state,
    a.assessment_name,

    case
        when a.test_code = 'ALG01'
        then concat(a.test_code, '_', e.school_level)
        else a.test_code
    end as test_code,

    if(a.is_proficient, 1, 0) as is_proficient_int,

    if(
        e.lunch_status in ('F', 'R'),
        'Economically Disadvantaged',
        'Non Economically Disadvantaged'
    ) as lunch_status,

    case
        when e.race_ethnicity = 'B'
        then 'African American'
        when e.race_ethnicity = 'A'
        then 'Asian'
        when e.race_ethnicity = 'I'
        then 'American Indian'
        when e.race_ethnicity = 'H'
        then 'Hispanic'
        when e.race_ethnicity = 'P'
        then 'Native Hawaiian'
        when e.race_ethnicity = 'T'
        then 'Other'
        when e.race_ethnicity = 'W'
        then 'White'
        when e.race_ethnicity is null
        then 'Blank'
    end as aggregate_ethnicity,

    if(e.lep_status, 'ML', 'Not ML') as ml_status,

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
    and a.academic_year >= {{ var("current_academic_year") - 7 }}
    and a.results_type = 'Actual'
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
    and e.grade_level > 2
    and e.region = 'Miami'

union all

-- NJ prelim scores
select
    e.academic_year,
    e.region,
    e.student_number,

    a.district_state,
    a.assessment_name,

    case
        when a.test_code = 'ALG01'
        then concat(a.test_code, '_', e.school_level)
        else a.test_code
    end as test_code,

    if(a.is_proficient, 1, 0) as is_proficient_int,

    if(
        e.lunch_status in ('F', 'R'),
        'Economically Disadvantaged',
        'Non Economically Disadvantaged'
    ) as lunch_status,

    case
        when e.race_ethnicity = 'B'
        then 'African American'
        when e.race_ethnicity = 'A'
        then 'Asian'
        when e.race_ethnicity = 'I'
        then 'American Indian'
        when e.race_ethnicity = 'H'
        then 'Hispanic'
        when e.race_ethnicity = 'P'
        then 'Native Hawaiian'
        when e.race_ethnicity = 'T'
        then 'Other'
        when e.race_ethnicity = 'W'
        then 'White'
        when e.race_ethnicity is null
        then 'Blank'
    end as aggregate_ethnicity,

    if(e.lep_status, 'ML', 'Not ML') as ml_status,

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
    and a.academic_year = {{ var("current_academic_year") }}
    and a.results_type = 'Preliminary'
    and e.grade_level > 2
    and e.school_level != 'OD'
    and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
