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
left join
    {{ ref("int_people__field_history") }} as wfm
    on sr.worker_id = wfm.worker_id
    and wfm.rn = 1
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
