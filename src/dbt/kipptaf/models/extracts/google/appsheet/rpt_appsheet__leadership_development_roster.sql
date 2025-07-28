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

    managers as (select distinct reports_to_employee_number, from roster),

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
                or roster.job_title = 'Controller',
                false
            ) as active,

            -- logic for permissions levels in app
            case
                -- 7: All access
                when roster.department in ('Data', 'Leadership Development')
                then 7
                when roster.job_title = 'Chief Executive Officer'
                then 7
                when contains_substr(roster.job_title, 'President')
                then 7
                -- 6: All entities, below own permission level
                when contains_substr(roster.job_title, 'Chief')
                then 6
                -- 5: Own entity, below own permission level
                when
                    contains_substr(roster.job_title, 'Managing Director')
                    and roster.department = 'School Support'
                then 5
                when
                    roster.job_title in (
                        'Managing Director Operations',
                        'Managing Director of Operations',
                        'Managing Director School Operations',
                        'Head of Schools',
                        'Head of Schools in Residence'
                    )
                then 5
                -- Own location, below own permission level
                when roster.job_title in ('School Leader', 'School Leader in Residence')
                then 4
                -- Own location, below own permission level
                when
                    contains_substr(roster.job_title, 'Managing Director')
                    and roster.entity = 'KIPP TEAM and Family Schools Inc'
                then 3
                -- Only their own direct reports
                when managers.reports_to_employee_number is not null
                then 2
                -- Only their own data
                else 1
            end as permission_level,
        from roster
        left join
            managers on roster.employee_number = managers.reports_to_employee_number
    )

select *,
from final
