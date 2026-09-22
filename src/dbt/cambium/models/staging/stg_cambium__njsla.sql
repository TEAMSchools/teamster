{#- source() in the branch is captured at parse time, so a district with
    cambium_eoc_enabled off never takes a dependency on src_cambium__eoc. -#}
{%- set relations = [source("cambium", "src_cambium__njsla")] -%}
{%- if var("cambium_eoc_enabled", true) -%}
    {%- do relations.append(source("cambium", "src_cambium__eoc")) -%}
{%- endif -%}

with
    union_relations as ({{ dbt_utils.union_relations(relations=relations) }}),

    njsla as (
        select
            american_indian_or_alaska_native,
            asian,
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

            if(
                `subject` in ('Algebra I', 'Algebra II', 'Geometry'),
                null,
                assessment_grade
            ) as assessment_grade,
        from union_relations
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

        from njsla
    ),

    dated as (
        select
            * except (earliest_test_start_timestamp, session_start_datetime),

            /* Unit start wins where present; the session fallback fills
               Mathematics, whose unit timestamps are all null. */
            coalesce(
                date(earliest_test_start_timestamp), date(session_start_datetime)
            ) as test_date,

        from earliest_test_start
    ),

    /* Cambium sends ELA, Mathematics and Science in one file, so every column
       below that differs between NJSLA and NJSLA Science branches on `subject`.
       They are derived here, not in `aligned`, because BigQuery rejects a
       SELECT-list alias referenced by another item in the same list. */
    leveled as (
        select
            *,

            if(`subject` = 'Science', 'NJSLA Science', 'NJSLA') as assessment_name,

            if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            case
                when `subject` in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'Math'
                when `subject` = 'Science'
                then 'Science'
                else 'ELA'
            end as discipline,

            case
                test_code
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else test_code
            end as module_code,

            case
                when `subject` = 'Science' and test_performance_level >= 3
                then true
                when `subject` != 'Science' and test_performance_level >= 4
                then true
                else false
            end as is_proficient,

            /* Science tops out at level 4 where ELA and Math reach 5, so the
               same numeric level means different things per subject. */
            case
                when `subject` = 'Science' and test_performance_level = 4
                then 'Exceeded Expectations'
                when `subject` = 'Science' and test_performance_level = 3
                then 'Met Expectations'
                when `subject` = 'Science' and test_performance_level = 2
                then 'Approached Expectations'
                when `subject` = 'Science' and test_performance_level = 1
                then 'Did Not Yet Meet Expectations'
                when test_performance_level = 5
                then 'Exceeded Expectations'
                when test_performance_level = 4
                then 'Met Expectations'
                when test_performance_level = 3
                then 'Approached Expectations'
                when test_performance_level = 2
                then 'Partially Met Expectations'
                when test_performance_level = 1
                then 'Did Not Yet Meet Expectations'
            end as testperformancelevel_text,

        from dated
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
            `period`,
            `subject`,
            assessment_name,
            administration_period,
            subject_area,
            discipline,
            module_code,
            is_proficient,
            testperformancelevel_text,
            assessment_name as assessment_version,
            administration_period as `admin`,
            subject_area as aligned_subject,
            module_code as aligned_test_code,
            test_code as testcode,
            test_score_complete as testscorecomplete,
            assessment_grade as assessmentgrade,
            assessment_year as assessmentyear,
            grade_level_when_assessed as gradelevelwhenassessed,
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

            'Actual' as results_type,
            'KTAF NJ' as district_state,

            cast(
                regexp_extract(assessment_grade, r'Grade\s(\d+)') as int
            ) as test_grade,

            coalesce(student_with_disabilities in ('504', 'B'), false) as is_504,

            if(is_proficient, 1, 0) as is_proficient_int,

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

            if(
                `subject` = 'Science', 'state_nj_njsla_science', 'state_nj_njsla'
            ) as assessment_type,

            /* NULL for Science, matching stg_pearson__njsla_science, which
               omits the column and lets the kipptaf union null-fill it. */
            case
                when `subject` = 'Science'
                then null
                when test_performance_level <= 2
                then true
                else false
            end as is_bl_fb,

            case
                when `subject` = 'Science' and test_performance_level = 2
                then 1
                when `subject` != 'Science' and test_performance_level = 3
                then 1
                else 0
            end as is_approaching_int,

            case
                when `subject` = 'Science' and test_performance_level < 2
                then 1
                when `subject` != 'Science' and test_performance_level < 3
                then 1
                else 0
            end as is_below_int,

            case
                when `subject` = 'Science'
                then null
                when test_performance_level <= 2
                then 'Below/Far Below'
                when test_performance_level = 3
                then 'Approaching'
                else 'At/Above'
            end as njsla_aggregated_proficiency,

            case
                when `subject` = 'Science'
                then null
                when test_performance_level <= 2
                then 'Not Proficient (1-2)'
                when test_performance_level = 3
                then 'Bubble (3)'
                else 'Proficient (4-5)'
            end as njsla_performance_band_group_label,

            case
                testperformancelevel_text
                when 'Did Not Yet Meet Expectations'
                then 'Lvl 1'
                when 'Partially Met Expectations'
                then 'Lvl 2'
                when 'Approached Expectations'
                then 'Lvl 3'
                when 'Met Expectations'
                then 'Lvl 4'
                when 'Exceeded Expectations'
                then 'Lvl 5'
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

        from leveled
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
