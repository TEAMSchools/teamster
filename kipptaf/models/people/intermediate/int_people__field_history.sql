{%- set surrogate_key_field_list = [
    "base_remuneration_annual_rate_amount_amount_value",
    "business_unit_assigned",
    "custom_wfmgr_accrual_profile",
    "custom_wfmgr_badge_number",
    "custom_wfmgr_ee_type",
    "custom_wfmgr_pay_rule",
    "department_assigned",
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
            effective_datetime,
            {{ dbt_utils.generate_surrogate_key(field_list=surrogate_key_field_list) }}
            as surrogate_key,
        from {{ ref("base_people__staff_roster_history") }}
        where
            position_id is not null
            and assignment_status != 'Terminated'
            and coalesce(worker_rehire_date, worker_original_hire_date)
            <= current_date('America/New_York')
    ),

    surrogate_key_lag as (
        select
            associate_oid,
            position_id,
            worker_id,
            effective_datetime,
            surrogate_key as surrogate_key_new,
            lag(surrogate_key, 1) over (
                partition by position_id order by effective_datetime
            ) as surrogate_key_prev
        from staff_roster_history
    )

select
    associate_oid,
    worker_id,
    position_id,
    effective_datetime,
    surrogate_key_prev,
    surrogate_key_new,
from surrogate_key_lag
where
    surrogate_key_new != surrogate_key_prev
    or surrogate_key_new is null
    or surrogate_key_prev is null
