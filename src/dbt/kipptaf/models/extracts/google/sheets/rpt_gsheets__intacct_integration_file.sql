select
    gl.group_code,
    gl.journal,
    gl.reference_no,
    gl.state,
    gl.source_entity,
    gl.line_no,
    gl.document,
    gl.acct_no,
    gl.debit,
    gl.credit,
    gl.memo,
    gl.location_id,
    gl.dept_id,
    gl.gl_entry_class_id,
    gl.gl_dim_function,
    gl.gl_dim_donor_restriction,

    srh.employee_number as gl_entry_employee_id,
    srh.preferred_name_lastfirst as preferred_lastfirst,
    srh.legal_name_formatted_name as legal_lastfirst,
    srh.department_home_name as department,
    srh.home_work_location_name as `location`,
    srh.job_title,
    srh.assignment_status as `status`,
    srh.worker_original_hire_date as hire_date,
    srh.worker_termination_date as termination_date,
    srh.work_assignment_actual_start_date as effective_position_start_date,

    cast(gl._dagster_partition_date as string) as `date`,

    coalesce(cm.project_id, gl.gl_entry_project_id) as gl_entry_project_id,

    concat(
        'adp_payroll_', gl._dagster_partition_date, '_', gl.group_code
    ) as `description`,
from {{ ref("stg_adp_payroll__general_ledger_file") }} as gl
left join
    {{ ref("stg_finance__payroll_code_mapping") }} as cm
    on gl.gl_entry_project_id = cm.old_project_id_alt_nj
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on gl.position_id = srh.position_id
    and timestamp(gl.date)
    between srh.work_assignment_start_date and srh.work_assignment_end_date
    and srh.primary_indicator
