with
    worked_holiday_edit as (
        select distinct location, transaction_apply_date,
        from {{ ref("stg_adp_workforce_manager__time_details") }}
        where transaction_type = 'Worked Holiday Edit'
    ),

    missed_punches as (
        select
            worker_id,
            transaction_apply_date,

            max(missed_in_punch) as missed_in_punch,
            max(missed_in_punch) as missed_out_punch,
        from {{ ref("stg_adp_workforce_manager__time_details") }}
        where
            transaction_in_exceptions = 'Missed In Punch'
            or transaction_out_exceptions = 'Missed Out Punch'
        group by worker_id, transaction_apply_date
    ),

    snow_days as (
        select
            schoolid,
            date_value,
            regexp_extract(
                _dbt_source_relation, r'(kipp\w+)_'
            ) as dagster_code_location,
        from {{ ref("stg_powerschool__calendar_day") }}
        where type = 'WS'
    )

select
    td.worker_id as adp_associate_id,
    td.budget_location,
    td.job as job_title,
    td.academic_year,
    td.transaction_apply_date as work_date,
    td.transaction_start_date_time as transaction_start_date_time,
    td.transaction_end_date_time as transaction_end_date_time,
    td.transaction_type,
    td.transaction_apply_to,
    td.hours,

    sr.employee_number as df_employee_number,
    sr.preferred_name_lastfirst as preferred_name,
    sr.assignment_status as employee_status,
    sr.business_unit_home_name as legal_entity_current,
    sr.home_work_location_name as location_current,
    sr.home_work_location_reporting_name as site_name_clean,
    sr.home_work_location_abbreviation as site_abbreviation,
    sr.home_work_location_powerschool_school_id as ps_school_id,
    sr.worker_original_hire_date as original_hire_date,
    sr.worker_rehire_date as rehire_date,
    sr.worker_termination_date as termination_date,
    sr.sam_account_name as staff_samaccountname,
    sr.report_to_preferred_name_lastfirst as manager_name,
    sr.report_to_sam_account_name as manager_samaccountname,

    sl.sam_account_name as sl_samaccountname,

    asp.lastest_update as accrual_last_update,
    asp.taken_no_accrual as no_accrual_taken,
    asp.taken_pto as pto_taken,
    asp.taken_sick as sick_taken,
    asp.taken_unused_pto as unused_pto_taken,
    asp.taken_vacation as vacation_taken,
    asp.balance_no_accrual as no_accrual_balance,
    asp.balance_pto as pto_balance,
    asp.balance_sick as sick_balance,
    asp.balance_unused_pto as unused_pto_balance,
    asp.balance_vacation as vacation_balance,

    if(td.transaction_in_exceptions = 'Late In', 1, 0) as late_status,
    if(td.transaction_out_exceptions = 'Early Out', 1, 0) as early_out_status,

    coalesce(
        td.transaction_in_exceptions,
        if(mp.missed_in_punch, 'Missed In Punch (Corrected)', null)
    ) as transaction_in_exceptions,
    coalesce(
        td.transaction_out_exceptions,
        if(mp.missed_out_punch, 'Missed Out Punch (Corrected)', null)
    ) as transaction_out_exceptions,
    if(
        td.missed_in_punch
        or mp.missed_in_punch
        or td.missed_out_punch
        or mp.missed_out_punch,
        1,
        0
    ) as missed_punch_status,

    case
        when
            h.transaction_apply_date is not null
            and td.transaction_apply_to = 'Worked Shift Segment'
        then 1
        when h.transaction_apply_date is not null
        then 0
        when
            sd.date_value is not null
            and td.transaction_start_date_time is null
            and td.transaction_end_date_time is null
        then 0
        when
            td.transaction_apply_to
            in ('Jury Duty', 'Bereavement', 'Religious Observance')
        then 0
        else 1
    end as denominator_day,

    case
        when h.transaction_apply_date is not null
        then 1
        when
            sd.date_value is not null
            and td.transaction_start_date_time is not null
            and td.transaction_end_date_time is not null
        then 1
        when td.transaction_apply_to = 'Professional Development'
        then 1
        when td.transaction_apply_to is null
        then 1
        else 0
    end as present_status,
from {{ ref("stg_adp_workforce_manager__time_details") }} as td
left join {{ ref("base_people__staff_roster") }} as sr on td.worker_id = sr.worker_id
left join
    {{ ref("base_people__staff_roster") }} as sl
    on sr.home_work_location_name = sl.home_work_location_name
    and sl.job_title = 'School Leader'
    and sl.assignment_status != 'Terminated'
left join
    {{ ref("int_adp_workforce_manager__accrual_summary_pivot") }} as asp
    on td.worker_id = asp.worker_id
    and asp.rn_employee_code = 1
left join
    missed_punches as mp
    on td.worker_id = mp.worker_id
    and td.transaction_apply_date = mp.transaction_apply_date
left join
    worked_holiday_edit as h
    on td.location = h.location
    and td.transaction_apply_date = h.transaction_apply_date
left join
    snow_days as sd
    on sr.home_work_location_powerschool_school_id = sd.schoolid
    and sr.home_work_location_dagster_code_location = sd.dagster_code_location
    and td.transaction_apply_date = sd.date_value
where
    td.rn_worker_date = 1
    and td.transaction_type not in ('Historical Correction', 'Worked Holiday Edit')
    and (
        (
            sr.business_unit_home_name != 'KIPP Miami'
            and td.transaction_apply_date
            >= date({{ var("current_academic_year") }}, 8, 15)
        )
        or (
            sr.business_unit_home_name = 'KIPP Miami'
            and td.transaction_apply_date
            >= date({{ var("current_academic_year") }}, 10, 31)
        )
    )
