with
    normalized as (
        select
            * except (score) replace (
                cast(probe_number as int) as probe_number,
                cast(additional_student_id as int) as additional_student_id,
                cast(total_number_of_probes as int) as total_number_of_probes,
                cast(device_date as date) as device_date,
                cast(sync_date as date) as sync_date,
                cast(school_primary_id as int) as school_primary_id,
                cast(aimline_value_by_date as numeric) as aimline_value_by_date,
                cast(goal as numeric) as goal,
                cast(cast(student_primary_id as numeric) as int) as student_primary_id,

                case
                    measure
                    when 'Maze'
                    then 'Reading Comprehension (Maze)'
                    when 'NWF-WRC'
                    then 'Decoding (NWF-WRC)'
                    when 'NWF-CLS'
                    then 'Letter Sounds (NWF-CLS)'
                    when 'ORF'
                    then 'Reading Fluency (ORF)'
                    when 'ORF-Accu'
                    then 'Reading Accuracy (ORF-Accu)'
                    when 'WRF'
                    then 'Word Reading (WRF)'
                    when 'PSF'
                    then 'Phonemic Awareness (PSF)'
                    when '(DEC-IW)'
                    then 'Irregular Words (DEC-IW)'
                    else measure
                end as measure
            ),

            cast(score as numeric) as measure_standard_score,

            cast(left(school_year, 4) as int) as academic_year,

            if(
                assessment_grade = 'K', 0, cast(assessment_grade as int)
            ) as assessment_grade_int,

            if(
                enrollment_grade = 'K', 0, cast(enrollment_grade as int)
            ) as enrollment_grade_int,

        from
            {{
                source(
                    "amplify_mclass_sftp",
                    "pm_student_summary_aimline",
                )
            }}
    ),

    pm_student_summary_aimline as (
        select
            *,

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Decoding (NWF-WRC)'
                then 'NWF'
                when 'Irregular Words (DEC-IW)'
                then 'DEC'
                when 'Letter Names (LNF)'
                then 'LNF'
                when 'Letter Sounds (NWF-CLS)'
                then 'NWF'
                when 'Phonemic Awareness (PSF)'
                then 'PSF'
                when 'Reading Accuracy (ORF-Accu)'
                then 'ORF'
                when 'Reading Comprehension (Maze)'
                then 'Comprehension'
                when 'Reading Fluency (ORF)'
                then 'ORF'
                when 'Word Reading (WRF)'
                then 'WRF'
            end as measure_name_code,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "student_primary_id",
                        "school_year",
                        "pm_period",
                        "measure",
                        "probe_number",
                    ]
                )
            }} as surrogate_key,

        from normalized
    )

select
    *,

    case
        measure_name_code
        when 'Comprehension'
        then 'Comprehension'
        when 'DEC'
        then 'Irregular Words'
        when 'LNF'
        then 'Letter Names'
        when 'NWF'
        then 'Nonsense Word Fluency'
        when 'ORF'
        then 'Oral Reading Fluency'
        when 'PSF'
        then 'Phonological Awareness'
        when 'WRF'
        then 'Word Reading Fluency'
        else measure_name_code
    end as measure_name,

from pm_student_summary_aimline
