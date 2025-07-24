{% set src_pss = source("amplify", "src_amplify__pm_student_summary") %}

with
    pm_data as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["student_primary_id", "school_year", "pm_period"]
                )
            }} as surrogate_key,

            {{
                dbt_utils.star(
                    from=src_pss,
                    except=[
                        "assessing_teacher_staff_id",
                        "assessment_grade",
                        "client_date",
                        "enrollment_grade",
                        "official_teacher_staff_id",
                        "primary_id_student_id_district_id",
                        "score_change",
                        "score",
                        "sync_date",
                    ],
                )
            }},

            date(client_date) as client_date,
            date(sync_date) as sync_date,

            coalesce(
                assessing_teacher_staff_id.string_value,
                cast(assessing_teacher_staff_id.double_value as string)
            ) as assessing_teacher_staff_id,

            coalesce(
                assessment_grade.string_value,
                cast(assessment_grade.long_value as string)
            ) as assessment_grade,

            coalesce(
                enrollment_grade.string_value,
                cast(enrollment_grade.long_value as string)
            ) as enrollment_grade,

            coalesce(
                official_teacher_staff_id.string_value,
                cast(official_teacher_staff_id.long_value as string),
                cast(official_teacher_staff_id.double_value as string)
            ) as official_teacher_staff_id,

            coalesce(
                primary_id_student_id_district_id.long_value,
                cast(primary_id_student_id_district_id.double_value as int)
            ) as primary_id_student_id_district_id,

            coalesce(
                cast(score.double_value as numeric), cast(score.long_value as numeric)
            ) as measure_standard_score,

            coalesce(
                cast(score_change.double_value as numeric),
                cast(score_change.string_value as numeric)
            ) as measure_standard_score_change,

            cast(left(school_year, 4) as int) as academic_year,

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Reading Comprehension (Maze)'
                then 'Comprehension'
                else substr(measure, strpos(measure, '(') + 1, 3)
            end as measure_name_code,

        from {{ src_pss }}
    )

select
    p.*,

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

    if(
        p.assessment_grade = 'K', 0, safe_cast(p.assessment_grade as int)
    ) as assessment_grade_int,

    if(
        p.enrollment_grade = 'K', 0, safe_cast(p.enrollment_grade as int)
    ) as enrollment_grade_int,

    x.abbreviation as school,
    x.powerschool_school_id as schoolid,
    initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,

from pm_data as p
left join {{ ref("stg_people__location_crosswalk") }} as x on p.school_name = x.name
