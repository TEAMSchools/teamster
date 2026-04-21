with
    enrollments as (
        select
            student_number,
            academic_year,
            entrydate,
            _dbt_source_relation,

            row_number() over (
                partition by student_number, academic_year, _dbt_source_relation
                order by entrydate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["c.record_id", "c._dbt_source_relation"]) }}
    as family_communication_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "c.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    if(
        sr.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }},
        cast(null as string)
    ) as staff_key,

    c.call_date as date_key,

    c.academic_year,

    c.call_type as communication_method,
    c.topic,
    c.reason,
    c.call_status as communication_outcome,
    c.response as notes,

    c.call_date as communication_date,

    c.is_attendance_call,
    c.is_truancy_call,

    cast(c.call_date_time as timestamp) as communication_timestamp,
from {{ ref("int_deanslist__comm_log") }} as c
inner join
    enrollments as enr
    on c.student_school_id = enr.student_number
    and c.academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="c", right_alias="enr") }}
    and enr.rn = 1
left join {{ ref("stg_deanslist__users") }} as u on c.user_id_str = u.dl_user_id
left join {{ ref("int_people__staff_roster") }} as sr on u.email = sr.work_email
