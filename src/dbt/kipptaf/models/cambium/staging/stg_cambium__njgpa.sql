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
    ),

    aligned as (
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
            native_hawaiian_or_other_pacific_islander
            as nativehawaiianorotherpacificislander,
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
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
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

            /* The aligned columns pearson_aligned_columns() adds in the pearson
               package, restated here for the adaptive rows. NJGPA-only branches
               collapse to constants; the race and disability mappings are the
               one deliberate duplication, because a cambium-package model
               cannot call a pearson-package macro. */
            'Actual' as results_type,
            'KTAF NJ' as district_state,
            'state_nj_njgpa' as assessment_type,
            0 as is_approaching_int,

            test_code as aligned_test_code,

            cast(null as string) as njsla_aggregated_proficiency,
            cast(null as string) as njsla_performance_band_group_label,

            coalesce(student_with_disabilities in ('504', 'B'), false) as is_504,

            if(multilingual_learner = 'Y', true, false) as lep_status,
            if(multilingual_learner = 'Y', 'ML', 'Not ML') as aligned_ml_status,

            if(
                student_with_disabilities in ('IEP', 'B'), 'Has IEP', 'No IEP'
            ) as iep_status,

            if(
                student_with_disabilities in ('IEP', 'B'),
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as aligned_iep_status,

            if(test_performance_level = 2, 1, 0) as is_proficient_int,
            /* Mirrors the ELA/Math branch of pearson_aligned_columns(), which
               flags every NJGPA level below 3 -- so both NJGPA levels read 1.
               Kept for parity with the Pearson rows; see the PR notes. */
            if(test_performance_level < 3, 1, 0) as is_below_int,

            if(upper(`period`) like 'FALL%', 'Fall', `period`) as `admin`,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as aligned_subject,

            if(
                `subject` like 'English Language Arts%', 'Text Study', `subject`
            ) as illuminate_subject,

            case
                test_performance_level when 2 then 'Lvl 4' when 1 then 'Lvl 3'
            end as aligned_performance_band_group,

            case
                when two_or_more_races = 'Y'
                then 'T'
                when hispanic_or_latino_ethnicity = 'Y'
                then 'H'
                when american_indian_or_alaska_native = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when black_or_african_american = 'Y'
                then 'B'
                when native_hawaiian_or_other_pacific_islander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,

        from union_relations
    )

select
    *,

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
        else 'Blank'
    end as aligned_aggregate_ethnicity,

from aligned
