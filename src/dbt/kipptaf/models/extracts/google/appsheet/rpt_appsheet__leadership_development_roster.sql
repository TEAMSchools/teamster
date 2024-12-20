select
    employee_number,
    preferred_name_lastfirst,
    home_work_location_name as location,
    home_business_unit_name as entity,
    home_department_name as department,
    assignment_status as status,
    job_title,
    google_email,
    reports_to_google_email,
    case
        when
            home_department_name
            in ('Data', 'Human Resources', 'Leadership Development')
        then 6
        when contains_substr(job_title, 'Chief')
        then 6
        when contains_substr(job_title, 'President')
        then 6
        when
            job_title in (
                'Managing Director Operations',
                'Managing Director of Operations',
                'Managing Director School Operations',
                'Head of Schools',
                'Head of Schools in Residence'
            )
        then 5
        when
            job_title in (
                'School Leader',
                'School Leader in Residence'
                'Director School Operations',
                'Director Campus Operations'
            )
        then 4
        when contains_substr(job_title, 'Assistant School Leader')
        then 3
        when
            contains_substr(job_title, 'Director')
            and home_department_name = 'Operations'
        then 3
        else 1
    end as permission_level,
from {{ ref("int_people__staff_roster") }} as sr
where sr.assignment_status in ('Active', 'Leave')
