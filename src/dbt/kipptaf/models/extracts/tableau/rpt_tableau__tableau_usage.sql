select
    srh.employee_number,
    srh.formatted_name,
    srh.job_title,
    srh.assignment_status,
    srh.home_work_location_name as location,
    srh.home_work_location_abbreviation as location_shortname,
    srh.home_work_location_grade_band as grade_band,
    srh.home_business_unit_name as entity,
    srh.home_department_name as department,
    srh.reports_to_formatted_name as manager,

    vc.name_hist_projects as `project`,
    vc.name_hist_workbooks as workbook,
    vc.name_hist_views as `view`,
    vc.`action`,
    vc.created_at_local_ny as viewed_at,
    vc.id as view_count_id,
    vc.url,
from {{ ref("stg_tableau__view_count_per_view") }} as vc
left join
    {{ ref("int_people__staff_roster_history") }} as srh
    on vc.user_name_lower = srh.sam_account_name
    and vc.created_at
    between srh.effective_date_start_timestamp and srh.effective_date_end_timestamp
