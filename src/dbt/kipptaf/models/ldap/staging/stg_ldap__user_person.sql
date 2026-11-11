with
    user_person as (
        select
            distinguishedname as distinguished_name,
            userprincipalname as user_principal_name,
            mail,
            samaccountname as sam_account_name,
            company,
            physicaldeliveryofficename as physical_delivery_office_name,
            department,
            employeeid as employee_id,
            displayname as display_name,
            givenname as given_name,
            sn,
            title,
            idautopersonalternateid as idauto_person_alternate_id,
            idautostatus as idauto_status,
            idautopersonenddate as idauto_person_end_date,
            idautopersontermdate as idauto_person_term_date,

            safe_cast(employeenumber as int) as employee_number,

            useraccountcontrol & 2 as uac_account_disable,

            regexp_replace(
                lower(userprincipalname),
                r'^([\w-\.]+@)[\w-]+(\.+[\w-]{2,4})$',
                if(
                    regexp_contains(userprincipalname, r'@kippmiami.org'),
                    r'\1kippmiami\2',
                    r'\1apps.teamschools\2'
                )
            ) as google_email,
        from {{ source("ldap", "src_ldap__user_person") }}
    )

    -- 2 AD accounts can share an employee number: keep the enabled, active one.
    -- Accounts with no employee number each stay, keyed by distinguished name.
    {{
        dbt_utils.deduplicate(
            relation="user_person",
            partition_by="employee_number, if(employee_number is null, distinguished_name, null)",
            order_by="(uac_account_disable = 0) desc, (idauto_status = 'A') desc, distinguished_name",
        )
    }}
