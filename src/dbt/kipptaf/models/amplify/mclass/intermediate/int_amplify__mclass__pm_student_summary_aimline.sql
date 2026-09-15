with
    base as (
        select
            student_primary_id_studentnumber as student_primary_id,
            school_year,
            school_name,
            academic_year,
            pm_period,
            device_date,
            sync_date,
            measure,
            measure_name_code,
            measure_name,
            probe_number,
            total_number_of_probes,
            measure_standard_score,
            assessment_grade,
            assessment_grade_int,
            enrollment_grade,
            enrollment_grade_int,
            enrollment_teacher_name,
            enrollment_teacher_staff_id_teachernumber as enrollment_teacher_staff_id,
            assessing_teacher_name,
            assessing_teacher_staff_id_teachernumber as assessing_teacher_staff_id,
            special_education,
            disability,
            iep_status,
            section_504,
            _dagster_partition_key,
            source_file_name,
            aimline_status,
            cast(aimline_value_by_date as numeric) as aimline_value_by_date,
        from {{ ref("stg_amplify__mclass__sftp__pm_student_summary") }}
    ),

    aimline as (
        select
            student_primary_id,
            school_year,
            pm_period,
            measure,
            probe_number,
            device_date,
            assessment_grade,
            aimline_status,
            aimline_value_by_date,
            goal,
        from {{ ref("stg_amplify__mclass__sftp__pm_student_summary_aimline") }}
    ),

    combined as (
        select
            b.student_primary_id,
            b.school_year,
            b.school_name,
            b.academic_year,
            b.pm_period,
            b.device_date,
            b.sync_date,
            b.measure,
            b.measure_name_code,
            b.measure_name,
            b.probe_number,
            b.total_number_of_probes,
            b.measure_standard_score,
            b.assessment_grade,
            b.assessment_grade_int,
            b.enrollment_grade,
            b.enrollment_grade_int,
            b.enrollment_teacher_name,
            b.enrollment_teacher_staff_id,
            b.assessing_teacher_name,
            b.assessing_teacher_staff_id,
            b.special_education,
            b.disability,
            b.iep_status,
            b.section_504,
            b._dagster_partition_key,
            b.source_file_name,

            a.goal,

            -- Amplify has moved aimline_status/aimline_value_by_date between
            -- this file and the base PM file mid-year without notice before,
            -- and gave no timeline for doing so again. Coalescing both
            -- directions means neither a reversion nor a future switch breaks
            -- this model.
            coalesce(a.aimline_status, b.aimline_status) as aimline_status,
            coalesce(
                a.aimline_value_by_date, b.aimline_value_by_date
            ) as aimline_value_by_date,
        from base as b
        left join
            aimline as a
            on b.student_primary_id = a.student_primary_id
            and b.school_year = a.school_year
            and b.pm_period = a.pm_period
            and b.measure = a.measure
            and b.probe_number = a.probe_number
            and b.device_date = a.device_date
            and b.assessment_grade = a.assessment_grade
    ),

    enriched as (
        select
            c.* except (student_primary_id),

            lc.location_abbreviation as school,
            lc.location_powerschool_school_id as schoolid,
            lc.location_dagster_code_location as _dbt_source_project,

            -- Miami's Focus migration offset, applied here rather than in the
            -- combined CTE above so the join still matches the two SFTP files
            -- on their shared raw id. Without it every Miami PM row
            -- misses int_amplify__benchmark_student_summary, which keys on the
            -- network number, and the aimline method reports zero for Miami.
            {{
                focus_student_number(
                    "c.student_primary_id",
                    "c.academic_year",
                    "lc.location_dagster_code_location",
                )
            }} as student_primary_id,

            -- the city form, matching int_amplify__mclass__pm_student_summary and
            -- the expectation gates. location_region is the long-form entity name
            -- (TEAM Academy Charter School), which joins to nothing downstream.
            initcap(
                regexp_extract(lc.location_dagster_code_location, r'kipp(\w+)')
            ) as region,

        from combined as c
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on c.school_name = lc.location_name
    )

select *,
from enriched
