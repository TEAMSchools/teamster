-- trunk-ignore(sqlfluff/ST06): contract column order is mandated
select
    msd.*,

    lc.location_clean_name,
    lc.campus_name,

    case
        sr.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else sr.home_business_unit_name
    end as home_business_unit_name,
    sr.home_department_name,
    sr.job_function,
    sr.job_title,

    sr.mail,
    sr.user_principal_name,
    sr.sam_account_name,

    sr.reports_to_mail,
    sr.reports_to_sam_account_name,
from {{ ref("int_surveys__manager_survey_details") }} as msd
left join
    {{ ref("int_people__staff_roster") }} as sr
    on msd.subject_df_employee_number = sr.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
