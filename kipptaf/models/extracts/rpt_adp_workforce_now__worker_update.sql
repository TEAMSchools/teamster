{{
    config(
        materialized="view",
    )
}}

with
    wfm_updates as (
        select distinct worker_id
        from {{ ref("int_people__field_history") }}
        where
            effective_datetime between date_sub(
                current_date('America/New_York'), interval 7 day
            ) and current_date('America/New_York')
    )

select
    sr.associate_oid,
    sr.employee_number,
    sr.custom_employee_number,
    sr.custom_wfmgr_badge_number,
    lower(sr.mail) as mail,
    sr.communication_business_email,
    sr.custom_wfmgr_trigger,
    case
        when wfm.worker_id is not null
        then concat('DR', current_date('America/New_York'))
    end as wfmgr_trigger,
from {{ ref("base_people__staff_roster") }} as sr
left join wfm_updates as wfm on sr.worker_id = wfm.worker_id
where
    sr.assignment_status != 'Terminated'
    and sr.mail is not null
    and (
        sr.employee_number != sr.custom_employee_number
        or sr.employee_number != sr.custom_wfmgr_badge_number
        or lower(sr.mail) != sr.communication_business_email
        or sr.custom_employee_number is null
        or sr.custom_wfmgr_badge_number is null
        or sr.communication_business_email is null
        or wfm.worker_id is not null
    )
