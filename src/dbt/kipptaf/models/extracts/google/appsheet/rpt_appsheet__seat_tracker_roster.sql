with
    itr_response as (
        select
            employee_number,
            answer,
            academic_year,
            max(date_submitted) as last_date_submitted,

            case
                when academic_year <> {{ var("current_academic_year") }}
                then 'No Response'
                when
                    answer
                    = 'I am committed to my school community/team and, if offered a renewal contract, definitely returning; the Recruitment Team should NOT hire for my position.'
                then 'Returning'
                when
                    answer
                    = 'I am committed to KIPP NJ|Miami, but interested in an opportunity at another other school and/or in a different role. I will speak to my manager and/or School Leader about my interests.'
                then 'Interested in Transfer'
                when
                    answer
                    = 'I am not returning but want to ensure my kids have an outstanding TEAMmate next year; the Recruitment Team should definitely hire for my position.'
                then 'Not Returning'
                when
                    answer
                    = 'I am not sure if I am returning and want to follow up with my manager and/or School Leader.'
                then 'Not Sure'
                else answer
            end as answer_short,
        from {{ ref("rpt_tableau__survey_responses") }} as sr
        where survey_code = 'ITR' and question_shortname = 'itr_plans'
        group by employee_number, answer, academic_year
    ),

    pm_tier as (
        select employee_number, overall_tier, max(eval_date) as eval_date

        from {{ ref("int_performance_management__observations") }}
        where observation_type_abbreviation = 'PMS'
        group by employee_number, overall_tier

    )

select
    sr.employee_number,
    sr.assignment_status,
    sr.formatted_name as preferred_name_lastfirst,
    sr.home_work_location_name,
    sr.home_work_location_grade_band,
    sr.job_title,
    sr.mail,
    sr.google_email,
    sr.reports_to_mail as report_to_mail,
    sr.reports_to_google_email as report_to_google_email,
    sr.worker_original_hire_date,
    sr.home_business_unit_name as business_unit_home_name,
    sr.worker_termination_date,
    sr.sam_account_name as tableau_username,
    sr.reports_to_sam_account_name as tableau_manager_username,

    /* future feeds from other data sources*/
    ir.answer_short as itr_response,
    null as certification_renewal_status,
    pm.overall_tier as last_performance_management_score,
    null as smart_recruiter_id,

    coalesce(
        cast(tgl.grade_level as string), sr.home_department_name
    ) as grade_department,

    coalesce(lc.region, sr.home_business_unit_name) as location_entity,

    coalesce(lc.abbreviation, sr.home_work_location_name) as location_shortname,

    coalesce(cc.name, sr.home_work_location_name) as campus,

    case
        when
            sr.home_business_unit_name
            in ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
        then 'New Jersey'
        when sr.home_business_unit_name = 'KIPP Miami'
        then 'Miami'
        when
            sr.home_work_location_name = 'Room 11'
            and sr.job_title = 'Managing Director of Operations'
        then 'Miami'
        else 'CMO'
    end as region_state,

    case
        /* see everything, edit everything*/
        when sr.home_department_name in ('Data')
        then 7
        when
            sr.home_department_name = 'Recruitment'
            and contains_substr(sr.job_title, 'Director')
        then 7
        /* see your state/region, edit everything, (intentionally blank below)*/
        /* see everything, edit teammate and seat status fields (recruiters)*/
        when
            sr.home_department_name = 'Recruitment'
            and (
                contains_substr(sr.job_title, 'Recruiter')
                or contains_substr(sr.job_title, 'Manager')
            )
        then 5
        /* see school, edit teammate fields (name in position, gutcheck, nonrenewal)*/
        when
            sr.job_title in (
                'School Leader',
                'School Leader in Residence',
                'Director School Operations',
                'Director Campus Operations',
                'Fellow School Operations Director',
                'Associate Director of School Operations'
            )
        then 4
        /* see everything, edit nothing */
        when contains_substr(sr.job_title, 'Chief')
        then 3
        when
            contains_substr(sr.job_title, 'Director')
            and sr.home_department_name = 'Special Education'
        then 3
        when
            sr.home_department_name
            in ('Leadership Development', 'Human Resources', 'Finance and Purchasing')
        then 3
        /* see your state/region, edit nothing */
        when
            contains_substr(sr.job_title, 'Managing Director')
            and sr.home_department_name in ('Operations', 'School Support')
        then 2
        when
            contains_substr(sr.job_title, 'Director')
            and sr.home_department_name in ('Operations', 'School Support')
            and sr.home_work_location_name like '%Room%'
        then 2
        when contains_substr(sr.job_title, 'Head of Schools')
        then 2
        /* see nothing */
        else 1
    end as permission_level,
from {{ ref("int_people__staff_roster") }} as sr
inner join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.name
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on sr.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
left join itr_response as ir on sr.employee_number = ir.employee_number
left join pm_tier as pm on sr.employee_number = pm.employee_number

union all

/* generic roster names used for positions that are open, closed, pre-start, or subs */
select
    999999 as employee_number,
    'Active' as assignment_status,
    'Open Seat' as preferred_name_lastfirst,
    null as home_work_location_name,
    null as home_work_location_grade_band,
    null as job_title,
    null as mail,
    null as google_email,
    null as report_to_mail,
    null as report_to_google_email,
    null as worker_original_hire_date,
    null as business_unit_home_name,
    null as worker_termination_date,
    null as tableau_username,
    null as tableau_manager_username,
    null as itr_response,
    null as certification_renewal_status,
    null as last_performance_management_score,
    null as smart_recruiter_id,
    null as grade_department,
    null as location_entity,
    null as location_shortname,
    null as campus,
    null as region_state,
    null as permission_level,

union all

select
    999998 as employee_number,
    'Pre-Start' as assignment_status,
    'New Hire' as preferred_name_lastfirst,
    null as home_work_location_name,
    null as home_work_location_grade_band,
    null as job_title,
    null as mail,
    null as google_email,
    null as report_to_mail,
    null as report_to_google_email,
    null as worker_original_hire_date,
    null as business_unit_home_name,
    null as worker_termination_date,
    null as tableau_username,
    null as tableau_manager_username,
    null as itr_response,
    null as certification_renewal_status,
    null as last_performance_management_score,
    null as smart_recruiter_id,
    null as grade_department,
    null as location_entity,
    null as location_shortname,
    null as campus,
    null as region_state,
    null as permission_level,

union all

select
    999997 as employee_number,
    'Active' as assignment_status,
    'Position Closed' as preferred_name_lastfirst,
    null as home_work_location_name,
    null as home_work_location_grade_band,
    null as job_title,
    null as mail,
    null as google_email,
    null as report_to_mail,
    null as report_to_google_email,
    null as worker_original_hire_date,
    null as business_unit_home_name,
    null as worker_termination_date,
    null as tableau_username,
    null as tableau_manager_username,
    null as itr_response,
    null as certification_renewal_status,
    null as last_performance_management_score,
    null as smart_recruiter_id,
    null as grade_department,
    null as location_entity,
    null as location_shortname,
    null as campus,
    null as region_state,
    null as permission_level,

union all

select
    999996 as employee_number,
    'Active' as assignment_status,
    'Scoot Sub' as preferred_name_lastfirst,
    null as home_work_location_name,
    null as home_work_location_grade_band,
    null as job_title,
    null as mail,
    null as google_email,
    null as report_to_mail,
    null as report_to_google_email,
    null as worker_original_hire_date,
    null as business_unit_home_name,
    null as worker_termination_date,
    null as tableau_username,
    null as tableau_manager_username,
    null as itr_response,
    null as certification_renewal_status,
    null as last_performance_management_score,
    null as smart_recruiter_id,
    null as grade_department,
    null as location_entity,
    null as location_shortname,
    null as campus,
    null as region_state,
    null as permission_level,
