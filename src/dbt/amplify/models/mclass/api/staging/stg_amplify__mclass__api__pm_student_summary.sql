with
    pm_student_summary as (
        select
            * except (
                client_date,
                primary_id_student_id_district_id,
                primary_id_student_number,
                probe_number,
                score_change,
                score,
                student_id_district_id,
                student_primary_id,
                sync_date,
                total_number_of_probes
            ),

            cast(
                primary_id_student_id_district_id as int
            ) as primary_id_student_id_district_id,
            cast(probe_number as int) as probe_number,
            cast(student_primary_id as int) as student_primary_id,
            cast(total_number_of_probes as int) as total_number_of_probes,

            cast(score as numeric) as measure_standard_score,
            cast(score_change as numeric) as measure_standard_score_change,

            cast(client_date as date) as client_date,
            cast(sync_date as date) as sync_date,

            cast(
                cast(primary_id_student_number as numeric) as int
            ) as primary_id_student_number,
            cast(
                cast(student_id_district_id as numeric) as int
            ) as student_id_district_id,

            cast(left(school_year, 4) as int) as academic_year,

            if(
                assessment_grade = 'K', 0, cast(assessment_grade as int)
            ) as assessment_grade_int,

            if(
                enrollment_grade = 'K', 0, cast(enrollment_grade as int)
            ) as enrollment_grade_int,

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Reading Comprehension (Maze)'
                then 'Comprehension'
                else substr(measure, strpos(measure, '(') + 1, 3)
            end as measure_name_code,

            {{
                dbt_utils.generate_surrogate_key(
                    ["student_primary_id", "school_year", "pm_period", "measure"]
                )
            }} as surrogate_key,

        from {{ source("amplify_mclass_api", "pm_student_summary") }}
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
