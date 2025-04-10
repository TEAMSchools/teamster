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
    gldimfunction as gl_dim_function,
    gldimdonor_restriction as gl_dim_donor_restriction,
    position_id,
    employee_name,
    _dagster_partition_date,
    _dagster_partition_group_code,

    parse_date('%m/%d/%Y', `date`) as `date`,

    coalesce(acct_no.long_value, safe_cast(acct_no.string_value as int)) as acct_no,

    coalesce(dept_id.long_value, cast(dept_id.double_value as int)) as dept_id,
    coalesce(
        file_number.long_value, cast(file_number.double_value as int)
    ) as file_number,
    coalesce(
        glentry_classid.long_value, cast(glentry_classid.double_value as int)
    ) as gl_entry_class_id,
    coalesce(
        glentry_projectid.long_value, cast(glentry_projectid.double_value as int)
    ) as gl_entry_project_id,
    coalesce(job_title.long_value, cast(job_title.double_value as int)) as job_title,

    coalesce(
        location_id.long_value,
        cast(location_id.double_value as int),
        safe_cast(location_id.string_value as int)
    ) as location_id,
from {{ source("adp_payroll", "src_adp_payroll__general_ledger_file") }}
