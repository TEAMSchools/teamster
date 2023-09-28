{{ config(enabled=false) }}
with
    wfm_time_details_kipp as (
        select
            location,
            substring(
                location,
                10,
                len(location) - 10 - (len(location) - charindex('/', location, 10))
            ) as school_name,
        from adp.wfm_time_details
        where location like '%KIPP%'
        group by location
    ),

    school_ids as (
        select sub.location, cw.ps_school_id, cw.site_name_clean, cw.site_abbreviation,
        from wfm_time_details_kipp
        left join people.school_crosswalk as cw on sub.school_name = cw.site_name
    ),

    school_leaders as (
        select primary_site as sl_primary_site, samaccountname as sl_samaccountname,
        from people.staff_crosswalk_static
        where primary_job = 'School Leader' and status != 'Terminated'
    ),

    holidays as (
        select location, transaction_apply_date, transaction_type as holiday_status,
        from adp.wfm_time_details
        where transaction_type = 'Worked Holiday Edit'
        group by location, transaction_apply_date, transaction_type
    ),

    snow_days as (
        select
            cal.`db_name`, cal.schoolid, cal.date_value, cal.type, sch.name as school,
        from powerschool.calendar_day as cal
        left join
            powerschool.schools as sch
            on cal.schoolid = sch.school_number
            and cal.`db_name` = sch.`db_name`
        where cal.type = 'WS'
    ),

    wfm_accrual_reporting_period_summary as (
        select
            _modified as last_updated,
            employee_name_id_,
            accrual_code,
            accrual_taken_to_date_hours_,
            accrual_available_balance_hours_,
            max(_modified) over (
                partition by employee_name_id_, accrual_code
            ) as max_last_updated
        from adp.wfm_accrual_reporting_period_summary
    ),

    last_accrual_day as (
        select
            last_updated,
            employee_name_id_,
            accrual_code,
            accrual_code + '_2' as accrual_code_2,
            accrual_taken_to_date_hours_,
            accrual_available_balance_hours_,
        from wfm_accrual_reporting_period_summary
        where last_updated = max_last_updated
    ),

    accruals_taken as (
        select
            last_updated,
            employee_name_id_,
            vacation_taken,
            pto_taken,
            no_accrual_taken,
            unused_pto_taken,
            sick_taken,
        from
            last_accrual_day pivot (
                max(accrual_taken_to_date_hours_) for accrual_code in (
                    'vacation' as vacation_taken,
                    'pto' as pto_taken,
                    'no accrual' as no_accrual_taken,
                    'unused pto' as unused_pto_taken,
                    'sick' as sick_taken
                )
            )
    ),

    accruals_balance as (
        select
            last_updated,
            employee_name_id_,
            vacation_balance,
            pto_balance,
            no_accrual_balance,
            unused_pto_balance,
            sick_balance,
        from
            last_accrual_day pivot (
                max(accrual_available_balance_hours_) for accrual_code in (
                    'vacation' as vacation_balance,
                    'pto' as pto_balance,
                    'no accrual' as no_accrual_balance,
                    'unused pto' as unused_pto_balance,
                    'sick' as sick_balance
                )
            )
    ),

    missed_punches as (
        select
            employee_name,
            transaction_apply_date,
            max(
                case
                    when transaction_in_exceptions = 'Missed In Punch'
                    then transaction_in_exceptions
                end
            ) as transaction_in_exceptions,
            max(
                case
                    when transaction_out_exceptions = 'Missed Out Punch'
                    then transaction_out_exceptions
                end
            ) as transaction_out_exceptions,
        from adp.wfm_time_details
        where
            (
                transaction_in_exceptions = 'Missed In Punch'
                or transaction_out_exceptions = 'Missed Out Punch'
            )
        group by employee_name, transaction_apply_date
    ),

    wfm_time_details as (
        select
            _modified,
            employee_name,
            job,
            location,
            transaction_apply_to,
            transaction_type,
            transaction_in_exceptions,
            transaction_out_exceptions,
            hours,
            `money`,
            `days`,
            employee_payrule,
            cast(transaction_apply_date as date) as transaction_apply_date,
            cast(
                transaction_start_date_time as datetime2
            ) as transaction_start_date_time,
            cast(transaction_end_date_time as datetime2) as transaction_end_date_time,
            row_number() over (
                partition by employee_name, transaction_apply_date
                order by _modified desc
            ) as rn_adj,
        from adp.wfm_time_details
        where transaction_type != 'Historical Correction'
    ),

    time_details_clean as (
        select
            sub._modified,
            sub.employee_name,
            sub.job,
            sub.location,
            sub.transaction_apply_date,
            sub.transaction_apply_to,
            sub.transaction_type,
            sub.hours,
            sub.`money`,
            sub.`days`,
            sub.transaction_start_date_time,
            sub.transaction_end_date_time,
            sub.employee_payrule,
            sub.rn_adj,
            coalesce(
                sub.transaction_in_exceptions,
                mp.transaction_in_exceptions + ' (Corrected)'
            ) as transaction_in_exceptions,
            coalesce(
                sub.transaction_out_exceptions,
                mp.transaction_out_exceptions + ' (Corrected)'
            ) as transaction_out_exceptions,
        from wfm_time_details as sub
        left join
            missed_punches as mp
            on sub.employee_name = mp.employee_name
            and sub.transaction_apply_date = mp.transaction_apply_date
        where sub.rn_adj = 1
    )

select
    td.job as job_title,
    td.location as budget_location,
    td.transaction_apply_to,
    td.transaction_type,
    td.transaction_in_exceptions,
    td.transaction_out_exceptions,
    td.hours,
    td.transaction_apply_date as work_date,
    td.transaction_start_date_time as transaction_start_date_time,
    td.transaction_end_date_time as transaction_end_date_time,
    utilities.date_to_sy(td.transaction_apply_date) as academic_year,
    substring(td.employee_name, (len(td.employee_name) - 9), 9) as adp_associate_id,
    case when td.transaction_in_exceptions = 'Late In' then 1 else 0 end as late_status,
    case
        when td.transaction_out_exceptions = 'Early Out' then 1 else 0
    end as early_out_status,
    case
        when td.transaction_in_exceptions = 'Missed In Punch'
        then 1
        when td.transaction_out_exceptions = 'Missed Out Punch'
        then 1
        when td.transaction_in_exceptions = 'Missed In Punch (Corrected)'
        then 1
        when td.transaction_out_exceptions = 'Missed Out Punch (Corrected)'
        then 1
        else 0
    end as missed_punch_status,

    id.ps_school_id,
    id.site_name_clean,
    id.site_abbreviation,

    cw.df_employee_number,
    cw.preferred_name,
    cw.manager_name,
    cw.legal_entity_name as legal_entity_current,
    cw.primary_site as location_current,
    lower(cw.samaccountname) as staff_samaccountname,
    lower(cw.manager_samaccountname) as manager_samaccountname,
    cw.status as employee_status,
    cw.original_hire_date,
    cw.rehire_date,
    cw.termination_date,

    lower(sl.sl_samaccountname) as sl_samaccountname,

    act.last_updated as accrual_last_update,
    act.no_accrual_taken,
    act.pto_taken,
    act.sick_taken,
    act.unused_pto_taken,
    act.vacation_taken,

    acb.no_accrual_balance,
    acb.pto_balance,
    acb.sick_balance,
    acb.unused_pto_balance,
    acb.vacation_balance,

    case
        when
            h.holiday_status = 'Worked Holiday Edit'
            and td.transaction_apply_to = 'Worked Shift Segment'
        then 1
        when h.holiday_status = 'Worked Holiday Edit'
        then 0
        when
            sd.type = 'WS'
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
        when h.holiday_status = 'Worked Holiday Edit'
        then 1
        when
            sd.type = 'WS'
            and td.transaction_start_date_time is not null
            and td.transaction_end_date_time is not null
        then 1
        when td.transaction_apply_to = 'Professional Development'
        then 1
        when td.transaction_apply_to is null
        then 1
        else 0
    end as present_status,
from time_details_clean as td
inner join school_ids as id on td.location = id.location
left join
    holidays as h
    on td.location = h.location
    and td.transaction_apply_date = h.transaction_apply_date
left join
    snow_days as sd
    on sd.schoolid = id.ps_school_id
    and sd.date_value = td.transaction_apply_date
left join
    people.staff_crosswalk_static as cw
    on substring(td.employee_name, len(td.employee_name) - 9, 9) = cw.adp_associate_id
left join school_leaders as sl on cw.primary_site = sl.sl_primary_site
left join accruals_taken as act on td.employee_name = act.employee_name_id_
left join accruals_balance as acb on td.employee_name = acb.employee_name_id_
where
    td.transaction_type != 'Worked Holiday Edit'
    and (
        (
            cw.legal_entity_name != 'KIPP Miami'
            and td.transaction_apply_date
            >= date(utilities.global_academic_year(), 8, 15)
        )
        or (
            cw.legal_entity_name = 'KIPP Miami'
            and td.transaction_apply_date
            >= date(utilities.global_academic_year(), 10, 31)
        )
    )
