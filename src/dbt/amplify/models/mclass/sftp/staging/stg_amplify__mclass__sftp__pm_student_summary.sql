with
    pm_student_summary as (
        select
            * except (
                device_date,
                student_primary_id_studentnumber,
                probe_number,
                score,
                additional_student_id_primarysisid,
                sync_date,
                total_number_of_probes,
                measure,
                school_primary_id
            ),

            cast(probe_number as int) as probe_number,
            cast(
                additional_student_id_primarysisid as int
            ) as additional_student_id_primarysisid,
            cast(total_number_of_probes as int) as total_number_of_probes,

            cast(score as numeric) as measure_standard_score,

            cast(device_date as date) as device_date,
            cast(sync_date as date) as sync_date,

            cast(
                cast(student_primary_id_studentnumber as numeric) as int
            ) as student_primary_id_studentnumber,

            cast(school_primary_id as int) as school_primary_id,

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
            end as measure,

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Maze'
                then 'Comprehension'
                else substr(measure, strpos(measure, '(') + 1, 3)
            end as measure_name_code,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "student_primary_id_studentnumber",
                        "school_year",
                        "pm_period",
                        "measure",
                    ]
                )
            }} as surrogate_key,

        from {{ source("amplify_mclass_sftp", "pm_student_summary") }}
    )

select
    *,

    case
        measure_name_code
        when 'LNF'
        then 'Letter Names'
        when 'PSF'
        then 'Phonological Awareness'
        when 'NWF'
        then 'Nonsense Word Fluency'
        when 'WRF'
        then 'Word Reading Fluency'
        when 'ORF'
        then 'Oral Reading Fluency'
        else measure_name_code
    end as measure_name,

from pm_student_summary
