with
    elementary_grade as (
        select teachernumber, max(grade_level) as max_grade_level,
        from {{ ref("int_powerschool__teacher_grade_levels") }}
        where academic_year = {{ var("current_academic_year") }} and grade_level <= 4
        group by teachernumber
    )

/* active staff info*/
select
    mgr.employee_number as df_employee_number,
    concat(
        mgr.preferred_name_lastfirst, ' - ', mgr.home_work_location_name
    ) as preferred_name,
    mgr.job_title as job_title,
    mgr.google_email,
    mgr.user_principal_name as user_email,
    mgr.home_work_location_name as primary_site,
    mgr.business_unit_home_name as legal_entity_name,
    mgr.report_to_employee_number as manager_df_employee_number,
    mgr.report_to_preferred_name_lastfirst as manager_name,

    sub.home_work_location_region as region,

    coalesce(c.name, mgr.home_work_location_name) as site_campus,

    sub.user_principal_name as manager_email,
    sub.google_email as manager_google,
    /* default TNTP assignments based on title/location*/
    case
        when
            mgr.home_work_location_name in (
                'Room 9 - 60 Park Pl',
                'Room 10 - 121 Market St',
                'Room 11 - 1951 NW 7th Ave'
            )
        then 'Regional Staff'
        when
            mgr.job_title in (
                'Teacher',
                'Teacher in Residence',
                'Learning Specialist',
                'Learning Specialist Coordinator',
                'Teacher, ESL',
                'Teacher ESL'
            )
        then 'Teacher'
        when mgr.department_home_name = 'School Leadership'
        then 'School Leadership Team'
        else 'Non-teaching school based staff'
    end as tntp_assignment,

    /* default Engagement & Support Survey assignments based on title/location */
    case
        when mgr.job_title = 'Head of Schools'
        then 'Head of Schools'
        when mgr.job_title = 'Assistant Superintendent'
        then 'Head of Schools'
        when
            mgr.job_title in (
                'Teacher',
                'Teacher in Residence',
                'Learning Specialist',
                'Learning Specialist Coordinator',
                'Teacher, ESL',
                'Teacher ESL'
            )
        then 'Teacher'
        when mgr.job_title = 'Executive Director'
        then 'Executive Director'
        when mgr.job_title = 'Associate Director of School Operations'
        then 'ADSO'
        when mgr.job_title = 'School Operations Manager'
        then 'SOM'
        when
            mgr.job_title in (
                'Director Campus Operations',
                'Director School Operations',
                'Director of Campus Operations',
                'Fellow School Operations Director'
            )
        then 'DSO'
        when mgr.job_title = 'Managing Director of Operations'
        then 'MDO'
        when mgr.job_title = 'Managing Director of School Operations'
        then 'MDSO'
        when mgr.job_title = 'School Leader'
        then 'School Leader'
        when
            mgr.job_title in (
                'Assistant School Leader',
                'Assistant School Leader, SPED',
                'School Leader in Residence'
            )
        then 'AP'
        else 'Other'
    end as engagement_survey_assignment,

    case
        when e.max_grade_level = 0
        then 'Grade K'
        when e.max_grade_level between 1 and 4
        then concat('Grade ', e.max_grade_level)
        else mgr.department_home_name
    end as department_grade,

    /* default School Based assignments based on legal entity/location */
    case
        when
            mgr.business_unit_home_name != 'KIPP TEAM and Family Schools Inc.'
            and mgr.home_work_location_name not in (
                'Room 9 - 60 Park Pl',
                'Room 10 - 121 Market St',
                'Room 11 - 1951 NW 7th Ave'
            )
        then 'school-based'
    end as school_based,

    case
        when
            mgr.job_title in (
                'Head of Schools',
                'School Leader',
                'School Leader in Residence',
                'Assistant School Leader',
                'Assistant School Leader, SPED',
                'Managing Director of School Operations',
                'Managing Director of Operations',
                'Managing Director of Growth',
                'Director School Operations',
                'Director Campus Operations'
            )
        then 'Leadership'
        when mgr.job_title = 'Teacher in Residence'
        then 'Teacher Development'
    end as feedback_group,
from {{ ref("base_people__staff_roster") }} as sub
left join
    {{ ref("base_people__staff_roster") }} as mgr
    on sub.employee_number = mgr.report_to_employee_number
left join
    {{ source("people", "src_people__campus_crosswalk") }} as c
    on mgr.home_work_location_name = c.location_name
left join elementary_grade as e on mgr.powerschool_teacher_number = e.teachernumber
where
    mgr.assignment_status != 'Terminated'
    and mgr.job_title != 'Intern'
    and mgr.job_title not like '%Temp%'
