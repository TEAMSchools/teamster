{%- macro tableau_access_columns(roster_alias, crosswalk_alias) -%}
    {{ crosswalk_alias }}.location_clean_name as location_name,
    {{ crosswalk_alias }}.campus_name,

    {{ roster_alias }}.home_business_unit_name as entity,
    {{ roster_alias }}.home_department_name as department_name,
    {{ roster_alias }}.job_function,
    {{ roster_alias }}.job_title,

    {{ roster_alias }}.mail as email,
    {{ roster_alias }}.user_principal_name,
    {{ roster_alias }}.sam_account_name,

    {{ roster_alias }}.reports_to_mail as report_to_email,
    {{ roster_alias }}.reports_to_sam_account_name as report_to_sam_account_name,
{%- endmacro -%}
