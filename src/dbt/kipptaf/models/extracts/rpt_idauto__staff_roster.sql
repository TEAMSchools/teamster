-- trunk-ignore-all(sqlfluff/RF05)
select
    w.worker_id__id_value as `Associate ID`,

    wa.job_title as `Job Title Description`,

    en.employee_number as `Position ID`,

    ou.name_business_unit as `Company Code`,
    ou.name_department as `Business Unit Description`,
    ou.name_department as `Home Department Description`,

    null as `Preferred Name`,

    wa.assignment_status__effective_date,
    wa.assignment_status__status_code__long_name,
    rt.reports_to_associate_oid,

    format_date('%m/%d/%Y', w.worker_dates__rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', w.worker_dates__termination_date) as `Termination Date`,

    format_date('%m/%d/%Y', p.birth_date) as `Birth Date`,
    coalesce(p.preferred_name__given_name, p.legal_name__given_name) as `First Name`,
    coalesce(
        p.preferred_name__family_name_1, p.legal_name__family_name_1
    ) as `Last Name`,

    coalesce(
        wa.home_work_location__name_code__long_name,
        wa.home_work_location__name_code__short_name
    ) as `Location Description`,

{#
    safe_cast(report_to_employee_number as string) as `Business Unit Code`,

    if(is_prestart, 'Active', assignment_status) as `Position Status`,
 #}
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
inner join
    {{ ref("stg_people__employee_numbers") }} as en
    on w.worker_id__id_value = en.adp_associate_id
    and en.is_active
inner join
    {{
        ref(
            "int_adp_workforce_now__workers__work_assignments__organizational_units__pivot"
        )
    }}
    as ou
    on wa.associate_oid = ou.associate_oid
    and wa.item_id = ou.item_id
    and ou.is_current_record
left join
    {{ ref("stg_adp_workforce_now__workers__work_assignments__reports_to") }} as rt
    on wa.associate_oid = rt.associate_oid
    and wa.item_id = rt.item_id
    and rt.is_current_record
where
    w.is_current_record
    and coalesce(w.worker_dates__rehire_date, w.worker_dates__original_hire_date)
    <= date_add(current_date('{{ var("local_timezone") }}'), interval 10 day)
