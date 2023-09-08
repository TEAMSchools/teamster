-- IMPORT CTEs
with
    adb_official_tests as (  -- ADB table with official ACT and SAT scores
        select *
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'act_english',
                'act_science',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )
    ),

    adb_roster as (  -- ADB to student_number crosswalk
        select * from {{ ref("int_kippadb__roster") }}
    ),

    illum_assessments_list as (  -- List of Illum assessments
        select *
        from {{ ref("base_illuminate__assessments") }}
        where scope in ('ACT Prep', 'SAT')
    ),

    illum_students as (select * from {{ ref("stg_illuminate__students") }}),  -- Crosswalk for Illum student IDs and student_number

    illum_students_questions_groups as (  -- Student total answers by groups
        select * from {{ ref("stg_illuminate__agg_student_responses_group") }}
    ),

    illum_reporting_groups as (  -- Illu crossswalk of reporting group ID to its name
        select * from {{ ref("stg_illuminate__reporting_groups") }}
    ),

    rpt_terms as (select * from {{ ref("stg_reporting__terms") }}),  -- Google-Sheet with reporting terms to tag BOY

    scale_score_key as (  -- Google-Sheet with scale score conversions from raw ranges
        select * from {{ ref("stg_assessments__act_scale_score_key") }}
    ),

    student_enrollments as (
        select * from {{ ref("base_powerschool__student_enrollments") }}  -- PowerSchool enrollment table for GL and school info
    ),

    -- LOGICAL CTEs
    act_official as (  -- All types of ACT scores from ADB
        select
            ktc.student_number,
            stl.contact,  -- ID from ADB for the student
            'ACT' as test_type,
            concat(
                format_date('%b', stl.date), ' ', format_date('%g', stl.date)
            ) as administration_round,
            stl.date as test_date,
            case
                when stl.score_type = 'act_composite'
                then 'Composite'
                when stl.score_type = 'act_reading'
                then 'Reading'
                when stl.score_type = 'act_math'
                then 'Math'
                when stl.score_type = 'act_english'
                then 'English'
                when stl.score_type = 'act_science'
                then 'Science'
            end as score_type,
            stl.score as scale_score,
            row_number() over (
                partition by stl.contact, stl.score_type order by stl.score desc
            ) as rn_highest  -- Sorts the table in desc order to calculate the highest score per score_type per student
        from adb_official_tests as stl  -- ADB scores data
        inner join adb_roster as ktc on stl.contact = ktc.contact_id
        where
            stl.score_type in (
                'act_composite', 'act_reading', 'act_math', 'act_english', 'act_science'
            )
    ),

    sat_official  -- All types of SAT scores from ADB
    as (
        select
            ktc.student_number,
            stl.contact,  -- ID from ADB for the student
            'SAT' as test_type,
            concat(
                format_date('%b', stl.date), ' ', format_date('%g', stl.date)
            ) as administration_round,
            stl.date as test_date,
            case
                when stl.score_type = 'sat_total_score'  -- Need to verify all of these are accurately tagged to match NJ's grad requirements
                then 'Composite'
                when stl.score_type = 'sat_reading_test_score'
                then 'Reading Test'
                when stl.score_type = 'sat_math_test_score'
                then 'Math Test'
                when stl.score_type = 'sat_math'
                then 'Math'
                when stl.score_type = 'sat_ebrw'
                then 'EBRW'
            end as score_type,
            stl.score as scale_score,
            row_number() over (
                partition by stl.contact, stl.score_type order by stl.score desc
            ) as rn_highest  -- sorts the table in desc order to calculate the highest score per score_type per student
        from adb_official_tests as stl  -- ADB scores data
        inner join
            adb_roster as ktc  -- ADB to student_number crosswalk
            on stl.contact = ktc.contact_id
        where
            stl.score_type in (
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )
    ),

    practice_tests  -- Foundation ACT/SAT Prep Practice Test data from Illuminate
    as (
        select
            ais.academic_year_clean as academic_year,  -- Fall SY
            co.schoolid,
            asr.student_id as illuminate_student_id,
            co.student_number,
            co.grade_level,
            ais.administered_at,
            safe_cast(rt.code as string) as scope_round,  -- Creates ACT1/ACT2 etc. names
            safe_cast(rt.name as string) as administration_round,  -- Creates a MMM YY tag for assessments
            ais.assessment_id,
            safe_cast(ais.title as string) as assessment_title,
            ais.scope,  -- To differentiate between ACT/SAT preps
            safe_cast(ais.subject_area as string) as subject_area,
            asr.performance_band_level as overall_performance_band_for_group,
            asr.reporting_group_id,
            rg.label as reporting_group_label,
            asr.points,
            sum(asr.points) over (
                partition by
                    ais.assessment_id,
                    ais.scope,
                    ais.subject_area,
                    rt.code,
                    asr.student_id
            ) as overall_number_correct,  -- Calculate total raw score for all groups combined
            sum(asr.points_possible) over (
                partition by
                    ais.assessment_id,
                    ais.scope,
                    ais.subject_area,
                    rt.code,
                    asr.student_id
            ) as overall_number_possible  -- Calc max elig raw score for all groups combined
        from illum_assessments_list as ais
        inner join
            illum_students_questions_groups as asr
            on ais.assessment_id = asr.assessment_id
        inner join illum_students as s on asr.student_id = s.student_id
        inner join
            rpt_terms as rt
            on (ais.administered_at between rt.start_date and rt.end_date)
            and rt.type = ais.scope
        inner join
            student_enrollments as co
            on s.local_student_id = co.student_number
            and ais.academic_year_clean = co.academic_year
            and co.rn_year = 1
        inner join
            illum_reporting_groups as rg
            on asr.reporting_group_id = rg.reporting_group_id
    ),

    practice_tests_with_scale_score_and_composite  -- Convert the number of correct questions (raw) to the scale score for ACT/SAT Prep
    as (
        select
            l.academic_year,
            l.schoolid,
            l.illuminate_student_id,
            l.student_number,
            l.grade_level,
            l.administered_at,
            l.scope_round, 
            l.administration_round,  
            l.assessment_id,
            l.assessment_title,
            l.scope, 
            l.subject_area,
            l.overall_performance_band_for_group,
            l.reporting_group_id,
            l.reporting_group_label,
            l.points,
            l.overall_number_correct, 
            l.overall_number_possible,
            cast(ssk.scale_score as int64) as scale_score_for_subject, --Uses the approx raw score to bring a scale score from the G-Sheet
            sum(distinct ssk.scale_score) over (partition by l.student_number,l.illuminate_student_id,l.academic_year,l.schoolid,l.grade_level,l.administration_round,l.scope_round) as overall_number_correct_for_scope_round,
            --round(avg())
            
            --case when count(scale_score) = 4 
            -- then round(avg(scale_score), 0)
             --end as scale_score 
        from practice_tests as l
        left join
            scale_score_key as ssk
            on l.academic_year = ssk.academic_year
            and l.scope = ssk.test_type
            and l.grade_level = ssk.grade_level
            and l.scope_round = ssk.administration_round
            and l.subject_area = ssk.subject
            and (
                l.overall_number_correct
                between ssk.raw_score_low and ssk.raw_score_high
            )
    )

select *
from practice_tests_with_scale_score_and_composite
