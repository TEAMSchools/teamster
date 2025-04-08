select
    distinguishedname as distinguished_name,
    userprincipalname as user_principal_name,
    mail,
    samaccountname as sam_account_name,
    physicaldeliveryofficename as physical_delivery_office_name,
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
