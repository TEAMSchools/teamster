-- trunk-ignore(sqlfluff/ST06)
select
    gl.journal as `JOURNAL`,

    format_date('%m/%d/%Y', gl.date) as `DATE`,
    concat(
        'adp_payroll_',
        gl._dagster_partition_date,
        '_',
        gl._dagster_partition_group_code
    ) as `DESCRIPTION`,

    gl.reference_no as `REFERENCE_NO`,
    gl.state as `STATE`,
    gl.source_entity as `SOURCEENTITY`,
    gl.line_no as `LINE_NO`,
    gl.document as `DOCUMENT`,
    gl.acct_no as `ACCT_NO`,
    gl.debit as `DEBIT`,
    gl.credit as `CREDIT`,
    gl.memo as `MEMO`,
    gl.location_id as `LOCATION_ID`,
    gl.dept_id as `DEPT_ID`,
    gl.gl_entry_class_id as `GLENTRY_CLASSID`,

    coalesce(cm.project_id, gl.gl_entry_project_id) as `GLENTRY_PROJECTID`,

    gl.gl_dim_function as `GLDIMFUNCTION`,
    gl.gl_dim_donor_restriction as `GLDIMDONOR_RESTRICTION`,

    srh.employee_number as `GLENTRY_EMPLOYEEID`,
    srh.preferred_name_lastfirst as preferred_name,
    srh.legal_name_formatted_name as legal_name,
    srh.assignment_status,
    srh.home_work_location_name as home_work_location,
    srh.department_home_name as home_department,
    srh.job_title,
    srh.worker_original_hire_date as original_hire_date,
    srh.worker_termination_date as termination_date,
    srh.work_assignment_actual_start_date,

    gl._dagster_partition_group_code,
    safe_cast(gl._dagster_partition_date as string) as _dagster_partition_date,
from {{ ref("stg_adp_payroll__general_ledger_file") }} as gl
left join
    {{ ref("stg_finance__payroll_code_mapping") }} as cm
    on gl.gl_entry_project_id = cm.old_project_id_alt_nj
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on gl.position_id = srh.position_id
    and gl.date between srh.work_assignment_start_date and srh.work_assignment_end_date
    and srh.primary_indicator
order by gl.line_no
