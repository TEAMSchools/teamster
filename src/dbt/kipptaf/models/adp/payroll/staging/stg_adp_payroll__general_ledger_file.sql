select
    journal,
    reference_no,
    `state`,
    sourceentity as source_entity,
    line_no,
    document,
    debit,
    credit,
    memo,
    glentry_classid as gl_entry_class_id,
    file_number,
    gldimfunction as gl_dim_function,
    gldimdonor_restriction as gl_dim_donor_restriction,
    position_id,
    employee_name,
    job_title,
    _dagster_partition_date,
    _dagster_partition_group_code as group_code,

    parse_date('%m/%d/%Y', `date`) as `date`,

    coalesce(acct_no.long_value, safe_cast(acct_no.string_value as int)) as acct_no,
    coalesce(
        location_id.long_value,
        safe_cast(location_id.string_value as int),
        safe_cast(location_id.double_value as int)
    ) as location_id,
    coalesce(dept_id.long_value, safe_cast(dept_id.double_value as int)) as dept_id,
    coalesce(
        glentry_projectid.long_value, safe_cast(glentry_projectid.double_value as int)
    ) as gl_entry_project_id,
from {{ source("adp_payroll", "src_adp_payroll__general_ledger_file") }}
