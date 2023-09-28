select
    distinguishedname as `distinguished_name`,
    userprincipalname as `user_principal_name`,
    mail as `mail`,
    samaccountname as `sam_account_name`,
    physicaldeliveryofficename as `physical_delivery_office_name`,
    safe_cast(employeenumber as int) as `employee_number`,
    useraccountcontrol & 2 as `uac_account_disable`,
    regexp_replace(
        lower(userprincipalname),
        r'^([\w-\.]+@)[\w-]+(\.+[\w-]{2,4})$',
        if(
            regexp_contains(user_principal_name, r'@kippmiami.org'),
            r'\1kippmiami\2',
            r'\1apps.teamschools\2'
        )
    ) as google_email,
from {{ source("ldap", "src_ldap__user_person") }}
