select
            home_work_location_name,
            business_unit_home_name,
            department_home_name,
            preferred_name_lastfirst as first_approver,
            user_principal_name as first_approver_email,
            google_email as first_approver_google,
            report_to_preferred_name_lastfirst as second_approver,
            report_to_mail as second_approver_email,
            case
            when business_unit_home_name not like '%Miami%' 
            then concat(report_to_sam_account_name,'@apps.teamschools.org') 
            when business_unit_home_name like '%Miami%' 
            then concat(report_to_sam_account_name,'@kippmiami.org') 
            end as second_approver_google,
            employee_number as director_employee_number,
            report_to_employee_number as managing_director_employee_number,
            case
            when department_home_name = 'Operations' then 'operations'
            when department_home_name = 'School Leadership' then 'instructional'
            when business_unit_home_name like '%Family%' then 'cmo'
            else 'regional'
            end as route
        from {{ ref('base_people__staff_roster') }}
        where
            job_title
            in ('Director School Operations', 'Director Campus Operations', 'Director','School Leader','School Leader in Residence')
            and assignment_status != 'Terminated'

