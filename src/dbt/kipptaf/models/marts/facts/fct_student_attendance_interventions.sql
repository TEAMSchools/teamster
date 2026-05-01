with
    comm_log as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_deanslist__comm_log"),
                partition_by=(
                    "student_school_id, academic_year, reason,"
                    " _dbt_source_relation"
                ),
                order_by="call_date desc",
            )
        }}
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
                "initcap(regexp_extract(ai._dbt_source_relation, r'kipp(\\w+)_'))",
                "ai.commlog_reason",
            ]
        )
    }} as intervention_type_key,

    if(
        c.record_id is not null,
        {{
            dbt_utils.generate_surrogate_key(
                ["c.record_id", "c._dbt_source_relation"]
            )
        }},
        cast(null as string)
    ) as family_communication_key,

    ai.commlog_date as date_key,

    ai.academic_year,
    ai.absence_threshold,
    ai.days_absent_unexcused,

    case
        ai.intervention_status when 'Complete' then true when 'Missing' then false
    end as has_communication_log,

    ai.is_ca_exception as is_chronic_absence_exception,
from {{ ref("int_students__attendance_interventions") }} as ai
inner join
    {{ ref("base_powerschool__student_enrollments") }} as enr
    on ai.student_number = enr.student_number
    and ai.academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="ai", right_alias="enr") }}
    and enr.rn_year = 1
left join
    comm_log as c
    on ai.student_number = c.student_school_id
    and ai.academic_year = c.academic_year
    and ai.commlog_reason = c.reason
    and {{ union_dataset_join_clause(left_alias="ai", right_alias="c") }}
