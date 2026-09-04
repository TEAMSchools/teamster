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
            school_name,
            academic_year,
            pm_period,
            device_date,
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
            enrollment_teacher_staff_id,
            assessing_teacher_name,
            assessing_teacher_staff_id,
            special_education,
            disability,
            iep_status,
            section_504,
            _dagster_partition_key,
            source_file_name,
            aimline_status,
            aimline_value_by_date,
            goal,
        from {{ ref("stg_amplify__mclass__sftp__pm_student_summary_aimline") }}
    ),

    combined as (
        select
            a.goal,
            -- only the base PM model carries a separate sync_date; the
            -- aimline model already collapses it into device_date upstream
            b.sync_date,

            coalesce(a.student_primary_id, b.student_primary_id) as student_primary_id,
            coalesce(a.school_year, b.school_year) as school_year,
            coalesce(a.school_name, b.school_name) as school_name,
            coalesce(a.academic_year, b.academic_year) as academic_year,
            coalesce(a.pm_period, b.pm_period) as pm_period,
            coalesce(a.device_date, b.device_date) as device_date,
            coalesce(a.measure, b.measure) as measure,
            coalesce(a.measure_name_code, b.measure_name_code) as measure_name_code,
            coalesce(a.measure_name, b.measure_name) as measure_name,
            coalesce(a.probe_number, b.probe_number) as probe_number,
            coalesce(
                a.total_number_of_probes, b.total_number_of_probes
            ) as total_number_of_probes,
            coalesce(
                a.measure_standard_score, b.measure_standard_score
            ) as measure_standard_score,
            coalesce(a.assessment_grade, b.assessment_grade) as assessment_grade,
            coalesce(
                a.assessment_grade_int, b.assessment_grade_int
            ) as assessment_grade_int,
            coalesce(a.enrollment_grade, b.enrollment_grade) as enrollment_grade,
            coalesce(
                a.enrollment_grade_int, b.enrollment_grade_int
            ) as enrollment_grade_int,
            coalesce(
                a.enrollment_teacher_name, b.enrollment_teacher_name
            ) as enrollment_teacher_name,
            coalesce(
                a.enrollment_teacher_staff_id, b.enrollment_teacher_staff_id
            ) as enrollment_teacher_staff_id,
            coalesce(
                a.assessing_teacher_name, b.assessing_teacher_name
            ) as assessing_teacher_name,
            coalesce(
                a.assessing_teacher_staff_id, b.assessing_teacher_staff_id
            ) as assessing_teacher_staff_id,
            coalesce(a.special_education, b.special_education) as special_education,
            coalesce(a.disability, b.disability) as disability,
            coalesce(a.iep_status, b.iep_status) as iep_status,
            coalesce(a.section_504, b.section_504) as section_504,
            coalesce(
                a._dagster_partition_key, b._dagster_partition_key
            ) as _dagster_partition_key,
            coalesce(a.source_file_name, b.source_file_name) as source_file_name,

            -- Amplify has moved aimline_status/aimline_value_by_date between
            -- this file and the base PM file mid-year without notice before,
            -- and gave no timeline for doing so again. Coalescing both
            -- directions means neither a reversion nor a future switch breaks
            -- this model.
            coalesce(a.aimline_status, b.aimline_status) as aimline_status,
            coalesce(
                a.aimline_value_by_date, b.aimline_value_by_date
            ) as aimline_value_by_date,
        from aimline as a
        full outer join
            base as b
            on a.student_primary_id = b.student_primary_id
            and a.school_year = b.school_year
            and a.pm_period = b.pm_period
            and a.measure = b.measure
            and a.probe_number = b.probe_number
            and a.device_date = b.device_date
            and a.assessment_grade = b.assessment_grade
    ),

    enriched as (
        select
            c.*,

            lc.location_region as region,
            lc.location_abbreviation as school,
            lc.location_powerschool_school_id as schoolid,
            lc.location_dagster_code_location as _dbt_source_project,

        from combined as c
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on c.school_name = lc.location_name
    )

select
    *,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_primary_id",
                "school_year",
                "pm_period",
                "measure",
                "probe_number",
                "device_date",
                "assessment_grade",
            ]
        )
    }} as surrogate_key,

from enriched
where assessment_grade_int >= 3
