-- trunk-ignore-all(sqlfluff/ST06)
select
    gl.journal,
    gl.date,

    concat(
        'adp_payroll_',
        extract(year from gl.date),
        if(safe_cast(extract(month from gl.date) as int) < 10, '0', ''),
        extract(month from gl.date),
        if(safe_cast(extract(day from gl.date) as int) < 10, '0', ''),
        extract(day from gl.date),
        '_',
        gl.group_code
    ) as description,

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

    coalesce(cm.project_id, gl.gl_entry_project_id) as glentry_projectid,

    gl.gl_dim_function,
    gl.gl_dim_donor_restriction,

    srh.employee_number as glentry_employeeid,
    srh.assignment_status as status,
    srh.worker_original_hire_date as hire_date,
    srh.work_assignment_actual_start_date as effective_position_start_date,
    srh.worker_termination_date as termination_date,
    srh.department_home_name as department,
    srh.home_work_location_name as location,
    srh.job_title,
    srh.preferred_name_lastfirst as preferred_firstlast,
    srh.legal_name_formatted_name as legal_firstlast,
from {{ ref("stg_adp_payroll__general_ledger_file") }} as gl
left join
    {{ ref("stg_finance__payroll_code_mapping") }} as cm
    on gl.gl_entry_project_id = cm.old_project_id_alt_nj
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on gl.position_id = srh.position_id
    and srh.primary_indicator
    and safe_cast(gl.date as timestamp)
    between srh.work_assignment__fivetran_start and srh.work_assignment__fivetran_end
