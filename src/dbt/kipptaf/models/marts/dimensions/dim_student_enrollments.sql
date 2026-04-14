with
    locations as (
        -- TODO: int_people__location_crosswalk has duplicate rows (#3633)
        select distinct
            location_powerschool_school_id,
            location_dagster_code_location,
            location_clean_name,
        from {{ ref("int_people__location_crosswalk") }}
        where
            not location_is_pathways
            and location_clean_name <> 'KIPP Whittier Elementary'
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

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }} as location_key,

    enr.entrydate as entry_date_key,
    enr.exitdate as exit_date_key,

    enr.academic_year,
    enr.grade_level,
    enr.cohort_primary as graduation_year,
    enr.school_level,
    enr.enroll_status,
    enr.is_retained_year,

from {{ ref("base_powerschool__student_enrollments") }} as enr
left join
    locations as loc
    on enr.schoolid = loc.location_powerschool_school_id
    and {{ extract_code_location("enr") }} = loc.location_dagster_code_location
