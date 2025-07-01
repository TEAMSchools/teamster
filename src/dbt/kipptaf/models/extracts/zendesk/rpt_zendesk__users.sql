with
    staff_roster as (
        select
            sr.user_principal_name as email,
            sr.personal_email,
            sr.google_email,
            sr.home_business_unit_code as adp__home_business_unit_code,
            sr.home_work_location_name as adp__home_work_location_name,

            u.name as zendesk__name,
            u.suspended as zendesk__suspended,
            u.organization_id as zendesk__organization_id,
            u.secondary_location as zendesk__secondary_location,
            u.email as zendesk__email,
            u.external_id as zendesk__external_id,

            cast(sr.employee_number as string) as external_id,

            sr.given_name || ' ' || sr.family_name_1 as `name`,

            if(sr.user_principal_name != sr.mail, sr.mail, null) as mail_alias,
            if(sr.worker_status_code = 'Terminated', true, false) as suspended,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_zendesk__users") }} as u on sr.user_principal_name = u.email
        where
            sr.user_principal_name is not null
            and (u.role is null or u.role = 'end-user')
    ),

    with_orgs as (
        select
            sr.*,

            if(
                sr.suspended, null, zol.zendesk_secondary_location
            ) as secondary_location,

            if(sr.suspended, null, o.id) as organization_id,
        from staff_roster as sr
        left join
            {{ ref("stg_google_sheets__zendesk_org_lookup") }} as zol
            on sr.adp__home_business_unit_code = zol.adp_business_unit
            and sr.adp__home_work_location_name = zol.adp_location
        left join
            {{ ref("stg_zendesk__organizations") }} as o
            on zol.zendesk_organization = o.name
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
                        "external_id",
                    ]
                )
            }} as adp_surrogate_key,

            {{
                dbt_utils.generate_surrogate_key(
                    field_list=[
                        "zendesk__name",
                        "zendesk__suspended",
                        "zendesk__organization_id",
                        "zendesk__secondary_location",
                        "zendesk__external_id",
                    ]
                )
            }} as zendesk_surrogate_key,
        from with_orgs
    )

select
    email,
    external_id,
    `name`,
    suspended,
    organization_id,

    /* existing values */
    zendesk__external_id,
    zendesk__name,
    zendesk__suspended,
    zendesk__organization_id,
    zendesk__secondary_location,
    adp__home_business_unit_code,
    adp__home_work_location_name,

    /* user identities */
    mail_alias,
    google_email,
    personal_email,

    'end-user' as `role`,

    struct(secondary_location as secondary_location) as user_fields,
from comparison
where adp_surrogate_key != zendesk_surrogate_key
