with

    roster as (
        select
            employee_number,
            reports_to_employee_number,
            formatted_name,
            home_work_location_name as location,
            home_business_unit_name as entity,
            home_department_name as department,
            assignment_status as status,
            job_title,
            mail,
            reports_to_mail,
            google_email,
            reports_to_google_email,
        from {{ ref("int_people__staff_roster") }}
        where assignment_status in ('Active', 'Leave')
    ),

    final as (
        select
            roster.*,
            -- logic to determine if title is active in leader performance management
            -- by default, editable in app
            coalesce(
                contains_substr(roster.job_title, 'Chief')
                or contains_substr(roster.job_title, 'Director')
                or contains_substr(roster.job_title, 'Head')
                or contains_substr(roster.job_title, 'Leader')
                or contains_substr(roster.job_title, 'President')
                or job_title = 'Controller',
                false
            ) as active,

            -- logic for permissions levels in app
            case
                when department in ('Data', 'Human Resources', 'Leadership Development')
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
                    contains_substr(job_title, 'Director') and department = 'Operations'
                then 3
                else 1
            end as permission_level,
        from roster
    )

select *
from final
