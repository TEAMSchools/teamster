select
    sr.employee_number,
    sr.formatted_name as preferred_name,
    sr.job_title,
    sr.google_email,
    sr.user_principal_name as email,
    sr.sam_account_name as tableau_username,
    sr.home_work_location_name as primary_site,
    sr.home_business_unit_name as legal_entity,
    sr.home_work_location_region as region,
    sr.reports_to_employee_number as manager_employee_number,
    sr.reports_to_formatted_name as manager_name,

    sr2.google_email as manager_google,
    sr2.user_principal_name as manager_email,
    sr2.sam_account_name as manager_tableau_username,

    lc.dso_sam_account_name as dso_tableau_username,
    lc.head_of_school_sam_account_name as head_of_school_tableau_username,
    lc.mdso_sam_account_name as mdso_tableau_username,
    lc.school_leader_sam_account_name as school_leader_tableau_username,

    coalesce(cc.name, sr.home_work_location_name) as site_campus,

    /* default TNTP assignments based on title/location*/
    case
        when
            sr.home_work_location_name like '%Room%'
            and sr.home_business_unit_name != 'KIPP TEAM and Family Schools Inc.'
        then 'Regional Staff'
        when sr.job_title like '%Teacher%'
        then 'Teacher'
        when sr.job_title like '%Learning%'
        then 'Teacher'
        when sr.home_department_name = 'School Leadership'
        then 'School Leadership Team'
        else 'Non-teaching school based staff'
    end as tntp_assignment,

    case
        when tgl.grade_level = 0
        then 'Grade K'
        when sr.home_department_name = 'Elementary' and tgl.grade_level is not null
        then concat('Grade ', tgl.grade_level)
        else sr.home_department_name
    end as department_grade,

    /* default School Based assignments based on legal entity/location */
    case
        when
            sr.home_work_location_name not like '%Room%'
            and sr.home_business_unit_name != 'KIPP TEAM and Family Schools Inc.'
        then true
    end as school_based,

    case
        when regexp_contains(sr.job_title, r'\b(head|chief|director|leader|manager)\b')
        then 'Leadership'
        when sr.job_title = 'Teacher in Residence'
        then 'Teacher Development'
    end as feedback_group,
from {{ ref("int_people__staff_roster") }} as sr
/* manager information */
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on sr.reports_to_employee_number = sr2.employee_number
left join
    {{ ref("stg_google_sheets__people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on sr.home_work_location_name = lc.home_work_location_name
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on sr.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
where
    sr.assignment_status != 'Terminated'
    and sr.job_title != 'Intern'
    and sr.job_title not like '%Temp%'
