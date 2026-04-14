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
                "ai.student_number",
                "ai.academic_year",
                "ai.commlog_reason",
            ]
        )
    }} as student_attendance_intervention_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "ai.student_number",
                "ai._dbt_source_relation",
                "ai.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "regexp_extract(ai._dbt_source_relation, r'(kipp\\w+)_')",
                "ai.commlog_reason",
            ]
        )
    }} as intervention_type_key,

    ai.commlog_date as date_key,

    ai.student_number,
    ai.academic_year,
    ai.commlog_reason,
    ai.absence_threshold,
    ai.days_absent_unexcused,

    ai.commlog_notes,
    ai.commlog_topic,
    ai.commlog_date,
    ai.commlog_status,
    ai.commlog_type,
    ai.commlog_staff_name,

    ai.intervention_status,
    ai.intervention_status_required_int,
    ai.is_ca_exception,
from {{ ref("int_students__attendance_interventions") }} as ai
inner join
    {{ ref("base_powerschool__student_enrollments") }} as enr
    on ai.student_number = enr.student_number
    and ai.academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="ai", right_alias="enr") }}
    and enr.rn_year = 1
left join
    locations as loc
    on ai.schoolid = loc.location_powerschool_school_id
    and {{ extract_code_location("ai") }} = loc.location_dagster_code_location
