with
    -- Amplify dropped the id-column suffixes from the SY2026-2027 headers;
    -- fold the new names back into the contracted old ones.
    renamed_ids as (
        select
            * except (
                student_primary_id,
                student_primary_id_studentnumber,
                enrollment_teacher_staff_id,
                enrollment_teacher_staff_id_teachernumber,
                assessing_teacher_staff_id,
                assessing_teacher_staff_id_teachernumber,
                secondary_student_id,
                secondary_student_id_stateid,
                additional_student_id,
                additional_student_id_sisid
            ),

            coalesce(
                student_primary_id_studentnumber, student_primary_id
            ) as student_primary_id_studentnumber,
            coalesce(
                enrollment_teacher_staff_id_teachernumber, enrollment_teacher_staff_id
            ) as enrollment_teacher_staff_id_teachernumber,
            coalesce(
                assessing_teacher_staff_id_teachernumber, assessing_teacher_staff_id
            ) as assessing_teacher_staff_id_teachernumber,
            coalesce(
                secondary_student_id_stateid, secondary_student_id
            ) as secondary_student_id_stateid,
            coalesce(
                additional_student_id_sisid, additional_student_id
            ) as additional_student_id_sisid,
        from {{ source("amplify_mclass_sftp", "pm_student_summary") }}
    ),

    normalized as (
        select
            * except (
                device_date,
                student_primary_id_studentnumber,
                probe_number,
                score,
                additional_student_id_primarysisid,
                sync_date,
                total_number_of_probes,
                measure
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
                when '(DEC-IW)'
                then 'Irregular Words (DEC-IW)'
                else measure
            end as measure,

        from renamed_ids
    ),

    pm_student_summary as (
        select
            -- Amplify leaves device_date blank on some rows; the sync date is
            -- the closest thing to when the probe happened.
            * except (device_date),

            coalesce(device_date, sync_date) as device_date,

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

from pm_student_summary
