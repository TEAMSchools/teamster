{%- set surrogate_key_field_list = [
    "assignment_status",
    "base_remuneration_annual_rate_amount_amount_value",
    "business_unit_assigned_name",
    "custom_wfmgr_accrual_profile",
    "custom_wfmgr_badge_number",
    "custom_wfmgr_ee_type",
    "custom_wfmgr_pay_rule",
    "department_assigned_name",
    "home_work_location_name",
    "job_title",
    "report_to_worker_id",
    "wage_law_coverage_short_name",
] -%}

with
    staff_roster_history as (
        select
            worker_id,
            position_id,
            associate_oid,
            dbt_valid_from,
            {{ dbt_utils.generate_surrogate_key(field_list=surrogate_key_field_list) }}
            as surrogate_key,
        from {{ ref("snapshot_people__staff_roster") }}
        where
            position_id is not null
            and coalesce(worker_rehire_date, worker_original_hire_date)
            <= current_date('{{ var("local_timezone") }}')
    ),

    surrogate_key_lag as (
        select
            associate_oid,
            position_id,
            worker_id,
            dbt_valid_from,
            surrogate_key as surrogate_key_new,
            lag(surrogate_key, 1) over (
                partition by position_id order by dbt_valid_from
            ) as surrogate_key_prev,
        from staff_roster_history
    ),

    field_history as (
        select
            associate_oid,
            worker_id,
            position_id,
            dbt_valid_from,
            surrogate_key_prev,
            surrogate_key_new,
            row_number() over (
                partition by associate_oid order by dbt_valid_from desc
            ) as rn,
        from surrogate_key_lag
        where
            surrogate_key_new != surrogate_key_prev
            or surrogate_key_new is null
            or surrogate_key_prev is null
    )

select
    sr.associate_oid,
    sr.employee_number,
    sr.custom_employee_number,
    sr.custom_wfmgr_badge_number,
    sr.communication_business_email,
    sr.custom_wfmgr_trigger,

    wfm.surrogate_key_new as wfmgr_trigger,

    lower(sr.mail) as mail,
from {{ ref("base_people__staff_roster") }} as sr
left join field_history as wfm on sr.worker_id = wfm.worker_id and wfm.rn = 1
where
    sr.associate_oid is not null
    and sr.mail is not null
    and (
        sr.employee_number != sr.custom_employee_number
        or sr.employee_number != sr.custom_wfmgr_badge_number
        or lower(sr.mail) != sr.communication_business_email
        or sr.custom_employee_number is null
        or sr.custom_wfmgr_badge_number is null
        or sr.communication_business_email is null
        or sr.custom_wfmgr_trigger != wfm.surrogate_key_new
    )
