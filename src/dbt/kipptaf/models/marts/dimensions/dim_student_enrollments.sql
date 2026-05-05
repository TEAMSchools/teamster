select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
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

from {{ ref("base_powerschool__student_enrollments") }} as enr
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on enr.schoolid = sch.school_number
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="sch") }}
