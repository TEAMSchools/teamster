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
                total_number_of_probes
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

        from {{ source("amplify", "src_amplify__mclass__sftp__pm_student_summary") }}
    )

select
    p.*,

    x.abbreviation as school,
    x.powerschool_school_id as schoolid,

    initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,

    if(
        p.assessment_grade = 'K', 0, safe_cast(p.assessment_grade as int)
    ) as assessment_grade_int,

    if(
        p.enrollment_grade = 'K', 0, safe_cast(p.enrollment_grade as int)
    ) as enrollment_grade_int,

    case
        p.measure_name_code
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
        else p.measure_name_code
    end as measure_name,

from pm_student_summary as p
left join {{ ref("stg_people__location_crosswalk") }} as x on p.school_name = x.name
