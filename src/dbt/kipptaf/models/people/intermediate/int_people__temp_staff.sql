select ldap.*, lc.powerschool_school_id, lc.dagster_code_location,
from {{ ref("stg_ldap__user_person") }} as ldap
inner join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
    on ldap.physical_delivery_office_name = lc.name
where
    ldap.idauto_status = 'A'
    and ldap.uac_account_disable = 0
    and ldap.employee_id like 'TMP%'
