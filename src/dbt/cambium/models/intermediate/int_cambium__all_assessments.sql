{#- ref() inside the loop is captured at parse time, so only the relations a
    district names in the var enter its graph. -#}
{% set cambium_relations = var("cambium_state_assessment_relations") %}
{% set njsla_relations = [] %}
{% for m in cambium_relations if m != "stg_cambium__njgpa" %}
    {% do njsla_relations.append(ref(m)) %}
{% endfor %}

with
    njsla as ({{ dbt_utils.union_relations(relations=njsla_relations) }}),

    njsla_leveled as (
        select
            * except (assessment_grade),

            if(
                `subject` in ('Algebra I', 'Algebra II', 'Geometry'),
                null,
                assessment_grade
            ) as assessment_grade,

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
            end as performance_level_label,
        from njsla
    ),

    njsla_aligned as (
        select
            _dbt_source_relation,
            asian,
            white,
            academic_year,
            test_date,
            `period`,
            assessment_grade,
            assessment_name,
            administration_period,
            subject_area,
            discipline,
            module_code,
            is_proficient,
            performance_level_label,
            test_code,
            test_score_complete,
            assessment_year,
            grade_level_when_assessed,
            american_indian_or_alaska_native,
            black_or_african_american,
            first_name,
            hispanic_or_latino_ethnicity,
            last_or_surname,
            multilingual_learner,
            native_hawaiian_or_other_pacific_islander,
            student_test_uuid,
            student_with_disabilities,
            two_or_more_races,
            `subject` as raw_subject,
            assessment_name as assessment_version,
            administration_period as administration_round,
            subject_area as aligned_subject,
            module_code as aligned_test_code,
            local_student_identifier as student_number,
            state_student_identifier as state_student_id,
            test_scale_score as scale_score,

            /* INT64 on the Pearson side; the union would widen it to NUMERIC. */
            cast(test_performance_level as int) as performance_level,

            cast(
                regexp_extract(assessment_grade, r'Grade\s(\d+)') as int
            ) as test_grade,

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
            end as aggregated_proficiency,

            case
                when `subject` = 'Science'
                then null
                when test_performance_level <= 2
                then 'Not Proficient (1-2)'
                when test_performance_level = 3
                then 'Bubble (3)'
                else 'Proficient (4-5)'
            end as performance_band_group_label,

            case
                performance_level_label
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
        from njsla_leveled
        /* An incomplete attempt arrives as its own scored row; see yml. */
        where test_status = 'completed'
    ),

    {% if "stg_cambium__njgpa" in cambium_relations %}
        /* Adds _dbt_source_relation, matching the NJSLA branch. */
        njgpa as (
            {{ dbt_utils.union_relations(relations=[ref("stg_cambium__njgpa")]) }}
        ),

        njgpa_aligned as (
            select
                _dbt_source_relation,
                asian,
                white,
                academic_year,
                test_date,
                `period`,
                test_code,
                test_score_complete,
                assessment_grade,
                grade_level_when_assessed,
                assessment_year,
                american_indian_or_alaska_native,
                black_or_african_american,
                first_name,
                hispanic_or_latino_ethnicity,
                last_or_surname,
                multilingual_learner,
                native_hawaiian_or_other_pacific_islander,
                student_test_uuid,
                student_with_disabilities,
                two_or_more_races,
                `subject` as raw_subject,
                test_code as module_code,
                test_code as aligned_test_code,
                local_student_identifier as student_number,
                state_student_identifier as state_student_id,
                test_scale_score as scale_score,

                /* INT64 on the Pearson side; the union would widen it to NUMERIC. */
                cast(test_performance_level as int) as performance_level,

                'NJGPA' as assessment_name,
                'NJGPA-A' as assessment_version,
                'state_nj_njgpa' as assessment_type,
                0 as is_approaching_int,

                cast(null as string) as aggregated_proficiency,
                cast(null as string) as performance_band_group_label,
                cast(null as boolean) as is_bl_fb,

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
                    upper(`period`) like 'FALL%', 'Fall', `period`
                ) as administration_period,
                if(
                    upper(`period`) like 'FALL%', 'Fall', `period`
                ) as administration_round,

                /* Mirrors the ELA/Math branch of the Pearson model, which flags
                   every NJGPA level below 3, so both NJGPA levels read 1. */
                if(test_performance_level < 3, 1, 0) as is_below_int,

                if(test_performance_level = 2, true, false) as is_proficient,

                case
                    test_code when 'ELAGP' then 11 when 'MATGP' then 11
                end as test_grade,

                case
                    test_performance_level
                    when 2
                    then 'Graduation Ready'
                    when 1
                    then 'Not Yet Graduation Ready'
                end as performance_level_label,

                case
                    test_performance_level when 2 then 'Lvl 4' when 1 then 'Lvl 3'
                end as aligned_performance_band_group,
            from njgpa
            /* An incomplete attempt arrives as its own scored row; see yml. */
            where test_status = 'completed'
        ),
    {% endif %}

    aligned as (
        {% set aligned_ctes = ["njsla_aligned"] %}
        {% if "stg_cambium__njgpa" in cambium_relations %}
            {% do aligned_ctes.append("njgpa_aligned") %}
        {% endif %}
        {% for cte in aligned_ctes %}
            select
                _dbt_source_relation,
                academic_year,
                administration_round,
                administration_period,
                aligned_performance_band_group,
                aligned_subject,
                aligned_test_code,
                american_indian_or_alaska_native,
                asian,
                assessment_name,
                assessment_type,
                assessment_version,
                assessment_grade,
                assessment_year,
                black_or_african_american,
                discipline,
                multilingual_learner,
                first_name,
                grade_level_when_assessed,
                hispanic_or_latino_ethnicity,
                is_approaching_int,
                is_below_int,
                is_bl_fb,
                is_proficient,
                last_or_surname,
                student_number,
                module_code,
                native_hawaiian_or_other_pacific_islander,
                aggregated_proficiency,
                performance_band_group_label,
                `period`,
                state_student_id,
                student_test_uuid,
                student_with_disabilities,
                raw_subject,
                subject_area,
                test_date,
                test_grade,
                test_code,
                performance_level,
                performance_level_label,
                scale_score,
                test_score_complete,
                two_or_more_races,
                white,
            from {{ cte }}
            {% if not loop.last %}
                union all
            {% endif %}
        {% endfor %}
    ),

    demographics as (
        select
            *,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

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
        from aligned
    )

select
    _dbt_source_relation,
    academic_year,
    administration_round,
    administration_period,
    aligned_iep_status,
    aligned_ml_status,
    aligned_performance_band_group,
    aligned_subject,
    aligned_test_code,
    american_indian_or_alaska_native,
    asian,
    assessment_name,
    assessment_type,
    assessment_version,
    assessment_grade,
    assessment_year,
    black_or_african_american,
    discipline,
    district_state,
    multilingual_learner,
    first_name,
    grade_level_when_assessed,
    hispanic_or_latino_ethnicity,
    iep_status,
    is_504,
    is_approaching_int,
    is_below_int,
    is_bl_fb,
    is_proficient,
    is_proficient_int,
    last_or_surname,
    lep_status,
    student_number,
    module_code,
    native_hawaiian_or_other_pacific_islander,
    aggregated_proficiency,
    performance_band_group_label,
    `period`,
    race_ethnicity,
    results_type,
    state_student_id,
    student_test_uuid,
    student_with_disabilities,
    raw_subject,
    subject_area,
    test_date,
    test_grade,
    test_code,
    performance_level,
    performance_level_label,
    scale_score,
    test_score_complete,
    two_or_more_races,
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
from demographics
