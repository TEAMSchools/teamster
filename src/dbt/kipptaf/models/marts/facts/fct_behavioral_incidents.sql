with
    enrollments as (
        select
            student_number,
            academic_year,
            entrydate,
            exitdate,
            _dbt_source_relation,

            row_number() over (
                partition by student_number, academic_year, _dbt_source_relation
                order by entrydate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    staff_roster_by_email as (
        select work_email, employee_number, assignment_status, effective_date_start,
        from {{ ref("int_people__staff_roster") }}
        where work_email is not null
    ),

    staff_roster_by_email_dedup as (
        {{
            dbt_utils.deduplicate(
                relation="staff_roster_by_email",
                partition_by="work_email",
                order_by="if(assignment_status = 'Active', 0, 1), effective_date_start desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["i.incident_id", "i._dbt_source_project"]) }}
    as behavioral_incident_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "i.create_ts_academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    if(
        sr.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }},
        cast(null as string)
    ) as referring_staff_key,

    cast(i.create_ts_date as date) as creation_date_key,

    i.create_ts_academic_year as academic_year,

    i.location_key,

    i.category,
    i.category_tier,
    i.infraction as infraction_description,
    i.context,
    i.status,
    i.referral_tier as referral_category,

    i.is_referral,
    i.is_active,

    cast(i.close_ts_date as date) as close_date_key,
    cast(i.return_date_date as date) as return_date_key,
from {{ ref("int_deanslist__incidents") }} as i
inner join
    enrollments as enr
    on i.student_school_id = enr.student_number
    and i.create_ts_academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="i", right_alias="enr") }}
    and enr.rn = 1
left join {{ ref("stg_deanslist__users") }} as u on i.create_by = u.dl_user_id
left join staff_roster_by_email_dedup as sr on u.email = sr.work_email
