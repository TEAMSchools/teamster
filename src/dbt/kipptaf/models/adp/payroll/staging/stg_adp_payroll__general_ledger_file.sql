select
    _dagster_partition_date,
    _dagster_partition_group_code,
    `state`,
    document,
    employee_name,
    gldimdonor_restriction as gl_dim_donor_restriction,
    gldimfunction as gl_dim_function,
    journal,
    memo,
    position_id,
    sourceentity as source_entity,

    cast(acct_no as int) as acct_no,
    cast(dept_id as int) as dept_id,
    cast(file_number as int) as file_number,
    cast(glentry_classid as int) as gl_entry_class_id,
    cast(glentry_projectid as int) as gl_entry_project_id,
    cast(job_title as int) as job_title,
    cast(line_no as int) as line_no,
    cast(location_id as int) as location_id,
    cast(reference_no as int) as reference_no,

    cast(credit as numeric) as credit,
    cast(debit as numeric) as debit,

    parse_date('%m/%d/%Y', `date`) as `date`,
from {{ source("adp_payroll", "src_adp_payroll__general_ledger_file") }}
