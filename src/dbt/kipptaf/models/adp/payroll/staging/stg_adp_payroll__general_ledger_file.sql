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
    glentry_projectid as gl_entry_project_id,

    cast(line_no as int) as line_no,
    cast(reference_no as int) as reference_no,

    cast(credit as numeric) as credit,
    cast(debit as numeric) as debit,

    cast(cast(dept_id as numeric) as int) as dept_id,
    cast(cast(file_number as numeric) as int) as file_number,
    cast(cast(glentry_classid as numeric) as int) as gl_entry_class_id,
    cast(cast(job_title as numeric) as int) as job_title,

    cast(
        cast(nullif(regexp_replace(acct_no, r'[^\d\.]', ''), '') as numeric) as int
    ) as acct_no,

    cast(
        cast(nullif(regexp_replace(location_id, r'[^\d\.]', ''), '') as numeric) as int
    ) as location_id,

    parse_date('%m/%d/%Y', `date`) as `date`,
from {{ source("adp_payroll", "src_adp_payroll__general_ledger_file") }}
