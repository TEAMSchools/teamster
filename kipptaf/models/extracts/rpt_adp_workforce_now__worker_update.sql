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
    sr.employee_number,
    sr.associate_oid,
    lower(sr.mail) as mail,

    case
        when wfm.worker_id is not null
        then concat('DR', current_date('America/New_York'))
    end as wfm_trigger
from {{ ref("base_people__staff_roster") }} as sr
left join wfm_updates as wfm on sr.worker_id = wfm.worker_id
where sr.assignment_status != 'Terminated' and sr.mail is not null
