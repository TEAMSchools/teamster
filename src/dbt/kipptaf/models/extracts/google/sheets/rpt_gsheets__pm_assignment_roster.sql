select
    sr.employee_number,
    sr.preferred_name_lastfirst as preferred_name,
    sr.job_title as job_title,
    sr.google_email,
    sr.user_principal_name as email,
    sr.sam_account_name as tableau_username,
    sr.home_work_location_name as primary_site,
    sr.business_unit_home_name as legal_entity,
    sr.home_work_location_region as region,
    sr.report_to_employee_number as manager_employee_number,
    sr.report_to_preferred_name_lastfirst as manager_name,

    sr2.google_email as manager_google,
    sr2.user_principal_name as manager_email,
    sr2.sam_account_name as tableau_username_manager,

    lc.tableau_username_dso,
    lc.tableau_username_hos,
    lc.tableau_username_mdso,
    lc.tableau_username_sl,

    coalesce(cc.name, sr.home_work_location_name) as site_campus,

    /* default TNTP assignments based on title/location*/
    case
        when
            sr.home_work_location_name like '%Room%'
            and sr.business_unit_home_name != 'KIPP TEAM and Family Schools Inc.'
        then 'Regional Staff'
        when sr.job_title like '%Teacher%'
        then 'Teacher'
        when sr.job_title like '%Learning%'
        then 'Teacher'
        when sr.department_home_name = 'School Leadership'
        then 'School Leadership Team'
        else 'Non-teaching school based staff'
    end as tntp_assignment,

    case
        when sr.primary_grade_level_taught = 0
        then 'Grade K'
        when sr.department_home_name = 'Elementary' and sr.primary_grade_level_taught is not null
        then concat('Grade ', sr.primary_grade_level_taught)
        else sr.department_home_name
    end as department_grade,

    /* default School Based assignments based on legal entity/location */
    case
        when
            sr.home_work_location_name not like '%Room%'
            and sr.business_unit_home_name != 'KIPP TEAM and Family Schools Inc.'
        then true
        else false
    end as school_based,

    case
        when regexp_contains(sr.job_title, r'\b(head|chief|director|leader|manager)\b')
        then 'Leadership'
        when sr.job_title = 'Teacher in Residence'
        then 'Teacher Development'
        else NULL
    end as feedback_group,
from {{ ref("base_people__staff_roster") }} as sr
/* manager information */
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on sr2.employee_number = sr.report_to_employee_number
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
left join {{ ref('int_people__leadership_crosswalk') }} as lc
on sr.home_work_location_name = lc.home_work_location_name
 
where
    sr.assignment_status != 'Terminated'
    and sr.job_title != 'Intern'
    and sr.job_title not like '%Temp%'
