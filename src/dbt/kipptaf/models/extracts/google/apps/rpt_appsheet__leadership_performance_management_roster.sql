select
    sr1.employee_number,
    sr1.preferred_name_lastfirst,
    sr1.job_title,
    sr1.business_unit_home_name as entity,
    sr1.home_work_location_name as location,
    sr1.department_home_name as department,
    sr1.google_email,
    sr1.mail as email,

    sr2.google_email as manager_google_email,
    sr2.mail as manager_email,

from {{ ref("base_people__staff_roster") }} as sr1
join
    {{ ref("base_people__staff_roster") }} as sr2
    on sr1.report_to_employee_number = sr2.employee_number
