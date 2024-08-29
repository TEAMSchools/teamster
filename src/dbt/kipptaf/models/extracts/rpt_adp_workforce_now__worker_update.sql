select
    associate_oid,
    employee_number,
    mail,
    surrogate_key as wf_mgr_trigger,
    custom_field__employee_number as adp__custom_field__employee_number,
    wf_mgr_badge_number as adp__wf_mgr_badge_number,
    work_email as adp__work_email,
    wf_mgr_trigger as adp__wf_mgr_trigger,
from {{ ref("int_people__staff_roster_history") }}
where
    is_current_record
    and primary_indicator
    and mail is not null
    and worker_hire_date_recent <= current_date('{{ var("local_timezone") }}')
    and (
        surrogate_key != coalesce(wf_mgr_trigger, '')
        or employee_number != coalesce(custom_field__employee_number, -1)
        or employee_number != coalesce(wf_mgr_badge_number, -1)
        or mail != coalesce(work_email, '')
    )
