select
    -- trunk-ignore-begin(sqlfluff/RF05)
    w.worker_id__id_value as `Associate ID`,
    w.given_name as `First Name`,
    w.family_name_1 as `Last Name`,
    w.job_title as `Job Title Description`,
    w.assignment_status__status_code__long_name as `Position Status`,
    w.organizational_unit__assigned__business_unit__name as `Company Code`,
    w.home_work_location_name as `Location Description`,
    w.organizational_unit__assigned__department__name as `Business Unit Description`,
    w.organizational_unit__assigned__department__name as `Home Department Description`,

    en.employee_number as `Position ID`,

    null as `Preferred Name`,

    format_date('%m/%d/%Y', w.worker_dates__rehire_date) as `Rehire Date`,
    format_date('%m/%d/%Y', w.worker_dates__termination_date) as `Termination Date`,
    format_date('%m/%d/%Y', w.person__birth_date) as `Birth Date`,

    safe_cast(enm.employee_number as string) as `Business Unit Code`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_adp_workforce_now__workers") }} as w
inner join
    {{ ref("stg_people__employee_numbers") }} as en
    on w.worker_id__id_value = en.adp_associate_id
    and en.is_active
left join
    {{ ref("stg_people__employee_numbers") }} as enm
    on rt.reports_to_worker_id__id_value = enm.adp_associate_id
    and enm.is_active
where
    w.is_current_record
    and w.primary_indicator
    and w.organizational_unit__assigned__business_unit__name is not null
    and w.organizational_unit__assigned__department__name is not null
    and date_diff(
        coalesce(w.worker_dates__rehire_date, w.worker_dates__original_hire_date),
        current_date('{{ var("local_timezone") }}'),
        day
    )
    <= 10
