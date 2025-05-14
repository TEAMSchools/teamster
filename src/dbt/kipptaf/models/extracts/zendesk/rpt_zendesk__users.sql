select
    sr.formatted_name as `name`,
    sr.assigned_business_unit_code,
    sr.physical_delivery_office_name,
    sr.mail as email,
    sr.user_principal_name,
    sr.google_email,
    sr.personal_email,

    {# TODO: add lookup table for these #}
    null as organization_id,
    null as secondary_location,

    cast(sr.employee_number as string) as external_id,

    coalesce(u.role, 'end-user') as `role`,

    if(
        sr.assignment_status = 'Terminated' and u.role != 'agent', true, false
    ) as suspended,
from {{ ref("int_people__staff_roster") }} as sr
left join {{ ref("stg_zendesk__users") }} as u on sr.mail = u.email
where sr.mail is not null
