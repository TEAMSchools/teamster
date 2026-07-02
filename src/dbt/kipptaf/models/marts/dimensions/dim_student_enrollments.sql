select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "enr.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["enr.student_number"]) }} as student_key,

    sch.location_key,

    enr.entrydate as entry_date_key,
    enr.exitdate as exit_date_key,

    enr.academic_year,
    enr.grade_level,
    enr.cohort_primary as graduation_year,
    enr.is_retained_year,
    enr.year_in_network,

from {{ ref("int_powerschool__student_enrollment_union") }} as enr
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on enr.schoolid = sch.school_number
    and enr._dbt_source_project = sch._dbt_source_project
