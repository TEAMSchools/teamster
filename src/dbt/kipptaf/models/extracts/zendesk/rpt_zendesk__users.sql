with
    staff_roster as (
        select
            sr.user_principal_name as email,
            sr.personal_email,
            sr.google_email,

            {# TODO: add lookup table for these #}
            {# sr.home_business_unit_code, #}
            {# sr.home_work_location_name, #}
            u.organization_id,
            u.secondary_location,

            u.name as zendesk_name,
            u.suspended as zendesk_suspended,
            u.organization_id as zendesk_organization_id,
            u.secondary_location as zendesk_secondary_location,
            u.email as zendesk_email,

            sr.given_name || ' ' || sr.family_name_1 as `name`,

            cast(sr.employee_number as string) as external_id,

            coalesce(u.role, 'end-user') as `role`,

            if(sr.user_principal_name != sr.mail, sr.mail, null) as mail_alias,

            if(
                sr.assignment_status = 'Terminated' and u.role != 'agent', true, false
            ) as suspended,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_zendesk__users") }} as u on sr.user_principal_name = u.email
        where sr.user_principal_name is not null
    ),

    comparison as (
        select
            *,

            {{
                dbt_utils.generate_surrogate_key(
                    field_list=[
                        "name",
                        "suspended",
                        "organization_id",
                        "secondary_location",
                    ]
                )
            }} as adp_surrogate_key,

            {{
                dbt_utils.generate_surrogate_key(
                    field_list=[
                        "zendesk_name",
                        "zendesk_suspended",
                        "zendesk_organization_id",
                        "zendesk_secondary_location",
                    ]
                )
            }} as zendesk_surrogate_key,
        from staff_roster
    )

select
    email,
    external_id,
    `name`,
    suspended,
    `role`,
    organization_id,
    secondary_location,

    /* user identities */
    mail_alias,
    google_email,
    personal_email,
from comparison
where
    adp_surrogate_key != zendesk_surrogate_key
    /* TODO: remove after account cleanup */
    and `role` = 'end-user'
