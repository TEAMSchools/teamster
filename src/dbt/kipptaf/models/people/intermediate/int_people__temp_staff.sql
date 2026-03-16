select
    ldap.physical_delivery_office_name,
    ldap.distinguished_name,
    ldap.user_principal_name,
    ldap.mail,
    ldap.sam_account_name,
    ldap.employee_number,
    ldap.uac_account_disable,
    ldap.google_email,
    ldap.company,
    ldap.department,
    ldap.display_name,
    ldap.employee_id,
    ldap.given_name,
    ldap.idauto_person_alternate_id,
    ldap.idauto_person_end_date,
    ldap.idauto_person_term_date,
    ldap.idauto_status,
    ldap.sn,
    ldap.title,

    lc.powerschool_school_id,
    lc.dagster_code_location,
from {{ ref("stg_ldap__user_person") }} as ldap
inner join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
    on ldap.physical_delivery_office_name = lc.name
where
    ldap.idauto_status = 'A'
    and ldap.uac_account_disable = 0
    and ldap.employee_id like 'TMP%'
