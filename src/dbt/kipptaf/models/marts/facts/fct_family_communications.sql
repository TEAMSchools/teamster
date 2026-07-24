with
    enrollments as (
        select
            student_number,
            academic_year,
            entrydate,
            _dbt_source_relation,
            _dbt_source_project,

            row_number() over (
                partition by student_number, academic_year, _dbt_source_relation
                order by entrydate desc
            ) as rn,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["c.record_id", "c._dbt_source_project"]) }}
    as family_communication_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "c.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    if(
        sr.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }},
        cast(null as string)
    ) as communicator_staff_key,

    c.call_date as date_key,

    c.academic_year,

    c.call_type as method,
    c.topic,
    c.reason,
    c.call_status as outcome,
    c.response as notes,

    c.is_attendance_call,
    c.is_truancy_call,

    cast(c.call_date_time as timestamp) as `timestamp`,
from {{ ref("int_deanslist__comm_log") }} as c
inner join
    enrollments as enr
    on c.student_school_id = enr.student_number
    and c.academic_year = enr.academic_year
    and c._dbt_source_project = enr._dbt_source_project
    and enr.rn = 1
left join {{ ref("stg_deanslist__users") }} as u on c.user_id_str = u.dl_user_id
left join {{ ref("int_people__staff_roster") }} as sr on u.email = sr.work_email
