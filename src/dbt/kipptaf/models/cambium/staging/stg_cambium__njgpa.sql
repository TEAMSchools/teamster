with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_cambium", model.name),
                    source("kippcamden_cambium", model.name),
                ]
            )
        }}
    )

select
    /* Only READ inside extract_source_project, so it is easy to leave out of
       this select -- which would null-fill it and break the
       _dbt_source_relation / _dbt_source_project pairing invariant. */
    _dbt_source_relation,
    asian,
    academic_year,
    test_score_complete as testscorecomplete,
    assessment_grade as assessmentgrade,
    assessment_year as assessmentyear,
    american_indian_or_alaska_native as americanindianoralaskanative,
    black_or_african_american as blackorafricanamerican,
    first_name as firstname,
    hispanic_or_latino_ethnicity as hispanicorlatinoethnicity,
    last_or_surname as lastorsurname,
    local_student_identifier as localstudentidentifier,
    multilingual_learner as englishlearnerel,
    native_hawaiian_or_other_pacific_islander as nativehawaiianorotherpacificislander,
    `period`,
    state_student_identifier as statestudentidentifier,
    student_test_uuid as studenttestuuid,
    student_with_disabilities as studentwithdisabilities,
    `subject`,
    test_code as testcode,
    test_code as module_code,
    test_date,
    test_performance_level as testperformancelevel,
    test_scale_score as testscalescore,
    two_or_more_races as twoormoreraces,
    white,

    'NJGPA' as assessment_name,
    'NJGPA-A' as assessment_version,

    case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end as test_grade,

    if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

    if(
        `subject` = 'English Language Arts/Literacy', 'English Language Arts', `subject`
    ) as subject_area,

    if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,

    if(test_performance_level = 2, true, false) as is_proficient,

    case
        test_performance_level
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,

    {{ extract_source_project("union_relations") }} as _dbt_source_project,

from union_relations
