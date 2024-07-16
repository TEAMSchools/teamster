select
    w.worker_id__id_value,
    w.worker_dates__original_hire_date,
    w.worker_dates__rehire_date,
    w.worker_dates__termination_date,

    p.birth_date,
    p.preferred_name__given_name,
    p.legal_name__given_name,
    p.preferred_name__family_name_1,
    p.legal_name__family_name_1,

    wa.job_title,
    wa.assignment_status__effective_date,
    wa.assignment_status__status_code__long_name,
    wa.home_work_location__name_code__long_name,
    wa.home_work_location__name_code__short_name,

    rt.reports_to_associate_oid,

    ou.name_business_unit,
    ou.name_department,

{# en.employee_number, #}
from {{ ref("stg_adp_workforce_now__workers") }} as w
inner join
    {{ ref("stg_adp_workforce_now__workers__person") }} as p
    on w.associate_oid = p.associate_oid
    and p.is_current_record
inner join
    {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
    on w.associate_oid = wa.associate_oid
    and wa.is_current_record
    and wa.primary_indicator
left join
    {{ ref("stg_adp_workforce_now__workers__work_assignments__reports_to") }} as rt
    on wa.associate_oid = rt.associate_oid
    and wa.item_id = rt.item_id
    and rt.is_current_record
left join
    {{
        ref(
            "int_adp_workforce_now__workers__work_assignments__organizational_units__pivot"
        )
    }}
    as ou
    on wa.associate_oid = ou.associate_oid
    and wa.item_id = ou.item_id
    and ou.is_current_record
where w.is_current_record
