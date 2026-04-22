with
    locations as (
        select powerschool_school_id, dagster_code_location, location_name,
        from {{ ref("stg_people__locations") }}
    )

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

    {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }} as location_key,

    enr.entrydate as entry_date_key,
    enr.exitdate as exit_date_key,

    enr.academic_year,
    enr.grade_level,
    enr.cohort_primary as graduation_year,
    enr.enroll_status as status,
    enr.is_retained_year,

from {{ ref("base_powerschool__student_enrollments") }} as enr
left join
    locations as loc
    on enr.schoolid = loc.powerschool_school_id
    and {{ extract_code_location("enr") }} = loc.dagster_code_location
