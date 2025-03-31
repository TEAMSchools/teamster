/* roster that feeds into Stipend and Bonus AppSheet*/
select
    r.employee_number,
    r.payroll_group_code,
    r.worker_id,
    r.payroll_file_number,
    r.position_id,
    r.job_title,
    r.home_work_location_name as location,
    r.home_department_name as department,
    r.formatted_name,
    r.google_email,
    r.assignment_status,
    r.home_business_unit_name as entity,
    r.home_business_unit_code as entity_short,
    coalesce(r.home_work_location_campus_name, r.home_work_location_name) as campus,
    case
        when
            r.worker_termination_date is null
            and r.assignment_status in ('Active', 'Leave')
        then 'eligible'
        when
            r.worker_termination_date is not null
            and date_trunc(r.worker_termination_date, quarter)
            = date_trunc(current_date(), quarter)
        then 'eligible'
        else 'ineligible'
    end as eligibility_status,
    case
        when r.home_business_unit_code in ('TEAM', 'KCNA')
        then 'NJ'
        when r.home_business_unit_code = 'KIPP_MIAMI'
        then 'MIA'
        when r.home_business_unit_code = 'KIPP_TAF'
        then 'CMO'
    end as state_cmo,
    case
        /* all access view */
        when
            r.home_department_name
            in ('Data', 'Human Resources', 'Leadership Development', 'Executive')
        then 3
        when
            r.home_business_unit_code = 'KIPP_TAF'
            and r.home_department_name = 'Operations'
            and contains_substr(r.home_work_location_name, 'Room')
        then 3
        /* in-region/state view */
        when
            contains_substr(r.job_title, 'Director')
            and r.home_department_name = 'Operations'
            and contains_substr(r.home_work_location_name, 'Room')
        then 2

        when
            r.job_title in (
                'Head of Schools',
                'Managing Director of Operations',
                'Managing Director of School Operations'
            )
        then 2
        /* in-region/state view: username temp permissions for RDO coverage */
        when r.sam_account_name = 'tmiddleton'
        then 2
        /* in location/campus view */
        when r.job_title in ('Director School Operations', 'Director Campus Operations')
        then 1
        else 0
    end as app_permissions,
from {{ ref("int_people__staff_roster") }} as r
