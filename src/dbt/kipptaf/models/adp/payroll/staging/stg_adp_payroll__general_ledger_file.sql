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

    cast(line_no as int) as line_no,
    cast(reference_no as int) as reference_no,

    cast(credit as numeric) as credit,
    cast(debit as numeric) as debit,

    cast(cast(dept_id as numeric) as int) as dept_id,
    cast(cast(file_number as numeric) as int) as file_number,
    cast(cast(glentry_classid as numeric) as int) as gl_entry_class_id,
    cast(cast(glentry_projectid as numeric) as int) as gl_entry_project_id,
    cast(cast(job_title as numeric) as int) as job_title,

    cast(
        cast(
            if(regexp_contains(acct_no, r'[A-Za-z\s]'), null, acct_no) as numeric
        ) as int
    ) as acct_no,
    cast(
        cast(
            if(
                regexp_contains(location_id, r'[A-Za-z\s]'), null, location_id
            ) as numeric
        ) as int
    ) as location_id,

    parse_date('%m/%d/%Y', `date`) as `date`,
from {{ source("adp_payroll", "src_adp_payroll__general_ledger_file") }}
