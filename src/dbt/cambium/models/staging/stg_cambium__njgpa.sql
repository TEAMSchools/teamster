with
    njgpa as (
        select
            american_indian_or_alaska_native,
            asian,
            assessment_grade,
            assessment_year,
            black_or_african_american,
            first_name,
            hispanic_or_latino_ethnicity,
            last_or_surname,
            multilingual_learner,
            native_hawaiian_or_other_pacific_islander,
            `period`,
            student_test_uuid,
            student_with_disabilities,
            `subject`,
            test_code,
            test_status,
            two_or_more_races,
            white,

            cast(grade_level_when_assessed as int) as grade_level_when_assessed,
            cast(local_student_identifier as int) as local_student_identifier,
            cast(state_student_identifier as int) as state_student_identifier,

            cast(test_performance_level as numeric) as test_performance_level,
            cast(test_scale_score as numeric) as test_scale_score,

            cast(test_score_complete as numeric) as test_score_complete,

            cast(left(assessment_year, 4) as int) as academic_year,

            /* MMDDYYYYHHMM. safe_cast to timestamp returns NULL on this
               format, so an explicit parse_datetime format is required. */
            safe.parse_datetime(
                '%m%d%Y%H%M', assessmentsessionactualstartdatetime
            ) as session_start_datetime,

            safe_cast(
                unit_1_online_test_start_date_time as timestamp
            ) as unit_1_start_timestamp,
            safe_cast(
                unit_2_online_test_start_date_time as timestamp
            ) as unit_2_start_timestamp,
            safe_cast(
                unit_3_online_test_start_date_time as timestamp
            ) as unit_3_start_timestamp,
            safe_cast(
                unit_4_online_test_start_date_time as timestamp
            ) as unit_4_start_timestamp,

        from {{ source("cambium", "src_cambium__njgpa") }}
        where summative_flag = 'Y' and test_attemptedness_flag = 'Y'
    ),

    earliest_test_start as (
        select
            * except (
                unit_1_start_timestamp,
                unit_2_start_timestamp,
                unit_3_start_timestamp,
                unit_4_start_timestamp
            ),

            (
                select min(s),
                from
                    unnest(
                        [
                            unit_1_start_timestamp,
                            unit_2_start_timestamp,
                            unit_3_start_timestamp,
                            unit_4_start_timestamp
                        ]
                    ) as s
            ) as earliest_test_start_timestamp,

        from njgpa
    ),

    dated as (
        select
            * except (earliest_test_start_timestamp, session_start_datetime),

            /* Unit start wins where present, preserving ELA behavior; the
               session fallback fills Mathematics, whose unit timestamps are all
               null. */
            coalesce(
                date(earliest_test_start_timestamp), date(session_start_datetime)
            ) as test_date,

        from earliest_test_start
    ),

    /* Everything below maps Cambium's vocabulary onto the shared NJ-assessment
       shape int_pearson__all_assessments produces for the Pearson relations, so
       kipptaf can union the two vendors as passthroughs. The race, IEP and ML
       mappings restate the Pearson ones on purpose: a cambium-package model
       cannot call into the pearson package. */
    aligned as (
        select
            asian,
            white,
            academic_year,
            test_date,
            test_status,
            grade_level_when_assessed,
            `period`,
            `subject`,
            test_code as testcode,
            test_code as module_code,
            test_code as aligned_test_code,
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
            state_student_identifier as statestudentidentifier,
            student_test_uuid as studenttestuuid,
            student_with_disabilities as studentwithdisabilities,
            test_performance_level as testperformancelevel,
            test_scale_score as testscalescore,
            two_or_more_races as twoormoreraces,

            'NJGPA' as assessment_name,
            'NJGPA-A' as assessment_version,
            'Actual' as results_type,
            'KTAF NJ' as district_state,
            'state_nj_njgpa' as assessment_type,
            0 as is_approaching_int,

            cast(null as string) as njsla_aggregated_proficiency,
            cast(null as string) as njsla_performance_band_group_label,

            case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end as test_grade,

            if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,
            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as aligned_subject,

            if(
                `subject` like 'English Language Arts%', 'Text Study', `subject`
            ) as illuminate_subject,

            if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,
            if(upper(`period`) like 'FALL%', 'Fall', `period`) as `admin`,

            if(test_performance_level = 2, true, false) as is_proficient,
            if(test_performance_level = 2, 1, 0) as is_proficient_int,

            /* Mirrors the ELA/Math branch of the Pearson model, which flags
               every NJGPA level below 3, so both NJGPA levels read 1. */
            if(test_performance_level < 3, 1, 0) as is_below_int,

            case
                test_performance_level
                when 2
                then 'Graduation Ready'
                when 1
                then 'Not Yet Graduation Ready'
            end as testperformancelevel_text,

            case
                test_performance_level when 2 then 'Lvl 4' when 1 then 'Lvl 3'
            end as aligned_performance_band_group,

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

        from dated
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
