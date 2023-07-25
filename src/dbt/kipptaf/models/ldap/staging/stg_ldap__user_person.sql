select
    distinguishedname as `distinguished_name`,
    userprincipalname as `user_principal_name`,
    mail as `mail`,
    samaccountname as `sam_account_name`,
    physicaldeliveryofficename as `physical_delivery_office_name`,
    safe_cast(employeenumber as int) as `employee_number`,
    useraccountcontrol & 2 as `uac_account_disable`,
from {{ source("ldap", "src_ldap__user_person") }}
