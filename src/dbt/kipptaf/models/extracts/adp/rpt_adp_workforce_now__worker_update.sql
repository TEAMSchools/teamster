select
    associate_oid,
    employee_number,
    mail,
    wf_mgr_trigger_new as wf_mgr_trigger,
    custom_field__employee_number as adp__custom_field__employee_number,
    wf_mgr_badge_number as adp__wf_mgr_badge_number,
    work_email as adp__work_email,
    wf_mgr_trigger as adp__wf_mgr_trigger,
from {{ ref("int_people__staff_roster") }}
where
    mail is not null
    and (
        wf_mgr_trigger_new != coalesce(wf_mgr_trigger, '')
        or employee_number != coalesce(custom_field__employee_number, -1)
        or employee_number != coalesce(wf_mgr_badge_number, -1)
        or mail != coalesce(work_email, '')
    )
