with
    roster as (
        select
            employee_number,
            formatted_name as preferred_name_lastfirst,
            job_title,
            home_department_name as department,
            home_business_unit_name as business_unit,
            home_work_location_name as `location`,
            mail,
            reports_to_employee_number as report_to_employee_number,
            reports_to_formatted_name as report_to_preferred_name_lastfirst,
            reports_to_mail as report_to_mail,

            -- no 3-week new-hire wait, unlike most staff surveys
            assignment_status = 'Active' and primary_indicator as is_survey_eligible,

            -- recruitment's leader lists for the round, from the setup page
            job_title in (
                'Achievement Director',
                'Assistant School Leader',
                'Assistant School Leader, SPED',
                'Assistant School Leader, School Culture',
                'Associate Director',
                'Associate Director of Academic Operations',
                'Associate Director of School Operations',
                'Dean of Students',
                'Deputy Chief',
                'Deputy Head of Schools',
                'Director',
                'Director Campus Operations',
                'Director Math Achievement',
                'Director of Social Work',
                'Director School Operations',
                'Head of Schools',
                'Managing Director',
                'Managing Director of Operations',
                'Managing Director of School Operations',
                'Managing Director of Teaching & Learning',
                'School Leader',
                'School Leader in Residence'
            )
            and home_department_name in (
                'KIPP Forward',
                'Marketing, Comms, and Enrollment',
                'Operations',
                'School Leadership',
                'School Support',
                'Special Education',
                'Student Support',
                'Teaching and Learning'
            )
            and home_business_unit_name in (
                'TEAM Academy Charter School',
                'KIPP Cooper Norcross Academy',
                'KIPP Miami',
                'KIPP Paterson',
                'KIPP TEAM and Family Schools Inc.'
            ) as is_leader_role,
        from {{ ref("int_people__staff_roster") }}
    )

select
    r.employee_number,

    rt.academic_year,
    rt.code as survey_round,
    rt.is_current,

    r.preferred_name_lastfirst,
    r.job_title,
    r.department,
    r.business_unit,
    r.location,
    r.mail,
    r.report_to_employee_number,
    r.report_to_preferred_name_lastfirst,
    r.report_to_mail,
from roster as r
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on rt.name = 'Leader Intent to Return Survey'
    and rt.type = 'SURVEY'
where r.is_survey_eligible and r.is_leader_role
