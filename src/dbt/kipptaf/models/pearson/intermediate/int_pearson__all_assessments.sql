with
    pearson as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    source("kippnewark_pearson", "int_pearson__all_assessments"),
                    source("kippcamden_pearson", "int_pearson__all_assessments"),
                    source("kipppaterson_pearson", "int_pearson__all_assessments"),
                ],
                include=[
                    "_dbt_source_relation",
                    "academic_year",
                    "admin",
                    "administration_period",
                    "aligned_aggregate_ethnicity",
                    "aligned_iep_status",
                    "aligned_ml_status",
                    "aligned_performance_band_group",
                    "aligned_subject",
                    "aligned_test_code",
                    "americanindianoralaskanative",
                    "asian",
                    "assessment_name",
                    "assessment_type",
                    "assessment_version",
                    "assessmentgrade",
                    "assessmentyear",
                    "blackorafricanamerican",
                    "discipline",
                    "district_state",
                    "englishlearnerel",
                    "firstname",
                    "gradelevelwhenassessed",
                    "hispanicorlatinoethnicity",
                    "iep_status",
                    "is_504",
                    "is_approaching_int",
                    "is_below_int",
                    "is_bl_fb",
                    "is_proficient",
                    "is_proficient_int",
                    "lastorsurname",
                    "lep_status",
                    "localstudentidentifier",
                    "module_code",
                    "nativehawaiianorotherpacificislander",
                    "njsla_aggregated_proficiency",
                    "njsla_performance_band_group_label",
                    "period",
                    "race_ethnicity",
                    "results_type",
                    "statestudentidentifier",
                    "studenttestuuid",
                    "studentwithdisabilities",
                    "subject",
                    "subject_area",
                    "test_date",
                    "test_grade",
                    "testcode",
                    "testperformancelevel",
                    "testperformancelevel_text",
                    "testscalescore",
                    "testscorecomplete",
                    "twoormoreraces",
                    "white",
                ],
            )
        }}
    ),

    cambium_njsla as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[ref("stg_cambium__njsla"), ref("stg_cambium__eoc")],
                exclude=["_dbt_source_project"],
            )
        }}
    ),

    cambium_njsla_leveled as (
        select
            *,

            if(
                `subject` in ('Algebra I', 'Algebra II', 'Geometry'),
                null,
                assessment_grade
            ) as assessmentgrade,

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

            /* Science tops out at level 4 where ELA and Math reach 5. */
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
        from cambium_njsla
    ),

    cambium_njsla_aligned as (
        select
            _dbt_source_relation,
            asian,
            white,
            academic_year,
            test_date,
            `period`,
            `subject`,
            assessmentgrade,
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
            test_scale_score as testscalescore,
            two_or_more_races as twoormoreraces,

            /* INT64 on the Pearson side; the union would widen it to NUMERIC. */
            cast(test_performance_level as int) as testperformancelevel,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            if(
                `subject` = 'Science', 'state_nj_njsla_science', 'state_nj_njsla'
            ) as assessment_type,

            /* NULL for Science, matching stg_pearson__njsla_science, which
               omits the column. */
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
        from cambium_njsla_leveled
    ),

    cambium_njgpa_aligned as (
        select
            _dbt_source_relation,
            asian,
            white,
            academic_year,
            test_date,
            `period`,
            `subject`,
            test_code as testcode,
            test_code as module_code,
            test_code as aligned_test_code,
            test_score_complete as testscorecomplete,
            assessment_grade as assessmentgrade,
            grade_level_when_assessed as gradelevelwhenassessed,
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
            test_scale_score as testscalescore,
            two_or_more_races as twoormoreraces,

            /* INT64 on the Pearson side; the union would widen it to NUMERIC. */
            cast(test_performance_level as int) as testperformancelevel,

            'NJGPA' as assessment_name,
            'NJGPA-A' as assessment_version,
            'state_nj_njgpa' as assessment_type,
            0 as is_approaching_int,

            cast(null as string) as njsla_aggregated_proficiency,
            cast(null as string) as njsla_performance_band_group_label,
            cast(null as boolean) as is_bl_fb,

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

            if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,
            if(upper(`period`) like 'FALL%', 'Fall', `period`) as `admin`,

            if(test_performance_level = 2, true, false) as is_proficient,

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
        from {{ ref("stg_cambium__njgpa") }}
    ),

    cambium_aligned as (
        select
            _dbt_source_relation,
            academic_year,
            `admin`,
            administration_period,
            aligned_performance_band_group,
            aligned_subject,
            aligned_test_code,
            americanindianoralaskanative,
            asian,
            assessment_name,
            assessment_type,
            assessment_version,
            assessmentgrade,
            assessmentyear,
            blackorafricanamerican,
            discipline,
            englishlearnerel,
            firstname,
            gradelevelwhenassessed,
            hispanicorlatinoethnicity,
            is_approaching_int,
            is_below_int,
            is_bl_fb,
            is_proficient,
            lastorsurname,
            localstudentidentifier,
            module_code,
            nativehawaiianorotherpacificislander,
            njsla_aggregated_proficiency,
            njsla_performance_band_group_label,
            `period`,
            statestudentidentifier,
            studenttestuuid,
            studentwithdisabilities,
            `subject`,
            subject_area,
            test_date,
            test_grade,
            testcode,
            testperformancelevel,
            testperformancelevel_text,
            testscalescore,
            testscorecomplete,
            twoormoreraces,
            white,
        from cambium_njsla_aligned

        union all

        select
            _dbt_source_relation,
            academic_year,
            `admin`,
            administration_period,
            aligned_performance_band_group,
            aligned_subject,
            aligned_test_code,
            americanindianoralaskanative,
            asian,
            assessment_name,
            assessment_type,
            assessment_version,
            assessmentgrade,
            assessmentyear,
            blackorafricanamerican,
            discipline,
            englishlearnerel,
            firstname,
            gradelevelwhenassessed,
            hispanicorlatinoethnicity,
            is_approaching_int,
            is_below_int,
            is_bl_fb,
            is_proficient,
            lastorsurname,
            localstudentidentifier,
            module_code,
            nativehawaiianorotherpacificislander,
            njsla_aggregated_proficiency,
            njsla_performance_band_group_label,
            `period`,
            statestudentidentifier,
            studenttestuuid,
            studentwithdisabilities,
            `subject`,
            subject_area,
            test_date,
            test_grade,
            testcode,
            testperformancelevel,
            testperformancelevel_text,
            testscalescore,
            testscorecomplete,
            twoormoreraces,
            white,
        from cambium_njgpa_aligned
    ),

    /* Restates the Pearson package's demographic mappings; a kipptaf model
       cannot call into the pearson package. */
    cambium as (
        select
            *,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

            coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

            if(is_proficient, 1, 0) as is_proficient_int,

            if(englishlearnerel = 'Y', true, false) as lep_status,
            if(englishlearnerel = 'Y', 'ML', 'Not ML') as aligned_ml_status,

            if(
                studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP'
            ) as iep_status,
            if(
                studentwithdisabilities in ('IEP', 'B'),
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as aligned_iep_status,

            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,
        from cambium_aligned
    ),

    unioned as (
        select
            _dbt_source_relation,
            academic_year,
            `admin`,
            administration_period,
            aligned_iep_status,
            aligned_ml_status,
            aligned_performance_band_group,
            aligned_subject,
            aligned_test_code,
            americanindianoralaskanative,
            asian,
            assessment_name,
            assessment_type,
            assessment_version,
            assessmentgrade,
            assessmentyear,
            blackorafricanamerican,
            discipline,
            district_state,
            englishlearnerel,
            firstname,
            gradelevelwhenassessed,
            hispanicorlatinoethnicity,
            iep_status,
            is_504,
            is_approaching_int,
            is_below_int,
            is_bl_fb,
            is_proficient,
            is_proficient_int,
            lastorsurname,
            lep_status,
            localstudentidentifier,
            module_code,
            nativehawaiianorotherpacificislander,
            njsla_aggregated_proficiency,
            njsla_performance_band_group_label,
            `period`,
            race_ethnicity,
            results_type,
            statestudentidentifier,
            studenttestuuid,
            studentwithdisabilities,
            `subject`,
            subject_area,
            test_date,
            test_grade,
            testcode,
            testperformancelevel,
            testperformancelevel_text,
            testscalescore,
            testscorecomplete,
            twoormoreraces,
            white,
            aligned_aggregate_ethnicity,
        from pearson

        union all

        select
            _dbt_source_relation,
            academic_year,
            `admin`,
            administration_period,
            aligned_iep_status,
            aligned_ml_status,
            aligned_performance_band_group,
            aligned_subject,
            aligned_test_code,
            americanindianoralaskanative,
            asian,
            assessment_name,
            assessment_type,
            assessment_version,
            assessmentgrade,
            assessmentyear,
            blackorafricanamerican,
            discipline,
            district_state,
            englishlearnerel,
            firstname,
            gradelevelwhenassessed,
            hispanicorlatinoethnicity,
            iep_status,
            is_504,
            is_approaching_int,
            is_below_int,
            is_bl_fb,
            is_proficient,
            is_proficient_int,
            lastorsurname,
            lep_status,
            localstudentidentifier,
            module_code,
            nativehawaiianorotherpacificislander,
            njsla_aggregated_proficiency,
            njsla_performance_band_group_label,
            `period`,
            race_ethnicity,
            results_type,
            statestudentidentifier,
            studenttestuuid,
            studentwithdisabilities,
            `subject`,
            subject_area,
            test_date,
            test_grade,
            testcode,
            testperformancelevel,
            testperformancelevel_text,
            testscalescore,
            testscorecomplete,
            twoormoreraces,
            white,

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
        from cambium
    )

select
    u.* replace (
        cast(u.statestudentidentifier as string) as statestudentidentifier,
        coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier
    ),

    {{ extract_source_project("u") }} as _dbt_source_project,
from unioned as u
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
