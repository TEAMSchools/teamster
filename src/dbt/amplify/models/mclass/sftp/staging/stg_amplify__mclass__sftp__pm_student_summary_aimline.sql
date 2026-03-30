select
    * replace (
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

    case
        measure
        when 'Maze'
        then 'Comprehension'
        when 'NWF-WRC'
        then 'NWF'
        when 'NWF-CLS'
        then 'NWF'
        when 'ORF'
        then 'ORF'
        when 'ORF-Accu'
        then 'ORF'
        when 'WRF'
        then 'WRF'
        when 'PSF'
        then 'PSF'
        else measure
    end as measure_name_code,

    case
        measure
        when 'Maze'
        then 'Reading Comprehension'
        when 'NWF-WRC'
        then 'Nonsense Word Fluency'
        when 'NWF-CLS'
        then 'Nonsense Word Fluency'
        when 'ORF'
        then 'Oral Reading Fluency'
        when 'ORF-Accu'
        then 'Oral Reading Fluency'
        when 'WRF'
        then 'Word Reading Fluency'
        when 'PSF'
        then 'Phonological Awareness'
        else measure
    end as measure_name,

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

from
    {{
        source(
            "amplify_mclass_sftp",
            "pm_student_summary_aimline",
        )
    }}
