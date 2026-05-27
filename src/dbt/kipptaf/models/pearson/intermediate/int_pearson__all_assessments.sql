with
    union_relations as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    ref("stg_pearson__parcc"),
                    ref("stg_pearson__njsla"),
                    ref("stg_pearson__njsla_science"),
                    ref("stg_pearson__njgpa"),
                ],
                include=[
                    "_dbt_source_relation",
                    "_dbt_source_project",
                    "academic_year",
                    "administration_period",
                    "americanindianoralaskanative",
                    "asian",
                    "assessment_name",
                    "assessmentgrade",
                    "assessmentyear",
                    "blackorafricanamerican",
                    "discipline",
                    "englishlearnerel",
                    "hispanicorlatinoethnicity",
                    "is_proficient",
                    "is_bl_fb",
                    "module_code",
                    "nativehawaiianorotherpacificislander",
                    "period",
                    "statestudentidentifier",
                    "localstudentidentifier",
                    "firstname",
                    "lastorsurname",
                    "studentwithdisabilities",
                    "subject",
                    "subject_area",
                    "testcode",
                    "studenttestuuid",
                    "test_grade",
                    "testperformancelevel_text",
                    "testperformancelevel",
                    "testscalescore",
                    "testscorecomplete",
                    "twoormoreraces",
                    "white",
                ],
            )
        }}
    ),

    transformations as (
        select
            u._dbt_source_relation,
            u._dbt_source_project,
            u.academic_year,
            u.administration_period,
            u.americanindianoralaskanative,
            u.asian,
            u.assessment_name,
            u.assessmentgrade,
            u.assessmentyear,
            u.blackorafricanamerican,
            u.discipline,
            u.hispanicorlatinoethnicity,
            u.is_proficient,
            u.is_bl_fb,
            u.module_code,
            u.nativehawaiianorotherpacificislander,
            u.period,
            u.firstname,
            u.lastorsurname,
            u.`subject`,
            u.subject_area,
            u.testcode,
            u.studenttestuuid,
            u.test_grade,
            u.testperformancelevel_text,
            u.testperformancelevel,
            u.testscalescore,
            u.testscorecomplete,
            u.twoormoreraces,
            u.white,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

            cast(u.statestudentidentifier as string) as statestudentidentifier,

            coalesce(u.studentwithdisabilities in ('504', 'B'), false) as is_504,

            coalesce(
                x.student_number, u.localstudentidentifier
            ) as localstudentidentifier,

            case
                u.testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else u.testcode
            end as aligned_test_code,

            case
                when u.twoormoreraces = 'Y'
                then 'T'
                when u.hispanicorlatinoethnicity = 'Y'
                then 'H'
                when u.americanindianoralaskanative = 'Y'
                then 'I'
                when u.asian = 'Y'
                then 'A'
                when u.blackorafricanamerican = 'Y'
                then 'B'
                when u.nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when u.white = 'Y'
                then 'W'
            end as race_ethnicity,

            case
                when u.`subject` like 'English Language Arts%'
                then 'Text Study'
                when u.`subject` in ('Algebra I', 'Algebra II', 'Geometry')
                then 'Mathematics'
                else u.`subject`
            end as illuminate_subject,

            case
                when u.assessment_name = 'NJSLA' and u.testperformancelevel <= 2
                then 'Below/Far Below'
                when u.assessment_name = 'NJSLA' and u.testperformancelevel = 3
                then 'Approaching'
                when u.assessment_name = 'NJSLA' and u.testperformancelevel >= 4
                then 'At/Above'
            end as njsla_aggregated_proficiency,

            case
                when u.assessment_name = 'NJSLA' and u.testperformancelevel <= 2
                then 'Not Proficient (1-2)'
                when u.assessment_name = 'NJSLA' and u.testperformancelevel = 3
                then 'Bubble (3)'
                when u.assessment_name = 'NJSLA' and u.testperformancelevel >= 4
                then 'Proficient (4-5)'
            end as njsla_performance_band_group_label,

            case
                when u.testperformancelevel_text = 'Did Not Yet Meet'
                then 'Lvl 1'
                when u.testperformancelevel_text = 'Partially Met'
                then 'Lvl 2'
                when
                    u.testperformancelevel_text
                    in ('Approached', 'Not Yet Graduation Ready')
                then 'Lvl 3'
                when u.testperformancelevel_text in ('Met', 'Graduation Ready')
                then 'Lvl 4'
                when u.testperformancelevel_text = 'Exceeded'
                then 'Lvl 5'
            end as aligned_performance_band_group,

            case
                when u.assessment_name = 'NJGPA'
                then 0
                when u.assessment_name = 'NJSLA Science' and u.testperformancelevel = 2
                then 1
                when u.discipline in ('ELA', 'Math') and u.testperformancelevel = 3
                then 1
                else 0
            end as is_approaching_int,

            case
                when u.assessment_name = 'NJGPA' and u.testperformancelevel = 1
                then 1
                when u.assessment_name = 'NJSLA Science' and u.testperformancelevel < 2
                then 1
                when u.discipline in ('ELA', 'Math') and u.testperformancelevel < 3
                then 1
                else 0
            end as is_below_int,

            if(u.englishlearnerel = 'Y', true, false) as lep_status,

            if(
                u.studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP'
            ) as iep_status,

            if(u.`period` = 'FallBlock', 'Fall', u.`period`) as `admin`,

            if(
                u.`subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                u.`subject`
            ) as aligned_subject,

            if(u.is_proficient, 1, 0) as is_proficient_int,

        from union_relations as u
        left join
            {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
            on u.studenttestuuid = x.student_test_uuid
    )

select
    *,

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
    end as aligned_aggregate_ethnicity,

    if(lep_status, 'ML', 'Not ML') as aligned_ml_status,

    if(
        iep_status = 'Has IEP',
        'Students With Disabilities',
        'Students Without Disabilities'
    ) as aligned_iep_status,

    case
        assessment_name
        when 'PARCC'
        then 'state_nj_parcc'
        when 'NJSLA'
        then 'state_nj_njsla'
        when 'NJSLA Science'
        then 'state_nj_njsla_science'
        when 'NJGPA'
        then 'state_nj_njgpa'
        else 'state_nj_unknown'
    end as assessment_type,

from transformations
