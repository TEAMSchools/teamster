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

    lc.location_powerschool_school_id as powerschool_school_id,
    lc.location_dagster_code_location as dagster_code_location,
from {{ ref("stg_ldap__user_person") }} as ldap
inner join
    {{ ref("int_people__location_crosswalk") }} as lc
    on ldap.physical_delivery_office_name = lc.location_name
where
    ldap.idauto_status = 'A'
    and ldap.uac_account_disable = 0
    and ldap.employee_id like 'TMP%'
