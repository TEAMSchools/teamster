with
    itr_route as (
        select distinct
            job_title,
            case
                when job_title like ('%Director%')
                then 'Leader'
                when job_title like ('%Leader%')
                then 'Leader'
                when job_title like ('%Chief%')
                then 'Leader'
                else 'Instructional'
            end as route
        from {{ ref("base_people__staff_roster") }}
    )

select
    w.employee_number,
    w.status_value,
    w.business_unit_assigned_name as business_unit,
    coalesce(w.preferred_name_given_name, w.legal_name_given_name) as first_name,
    coalesce(w.preferred_name_family_name, w.legal_name_family_name) as last_name,
    w.home_work_location_name as work_location,
    w.job_title,
    w.worker_original_hire_date as hire_date,
    w.communication_business_email as business_email,
    concat(
        coalesce(w.preferred_name_given_name, w.legal_name_given_name),
        ' ',
        coalesce(w.preferred_name_family_name, w.legal_name_family_name),
        ' - ',
        w.home_work_location_name,
        ' (',
        w.employee_number,
        ')'
    ) as respondent_response_name,
    regexp_extract(w.communication_business_email, r'^(.*?)@') as worker_username,
    concat(
        'https://docs.google.com/forms/d/e/',
        '1FAIpQLSerLfKQhyeRGIWNBRTyYHfefnuCmveUCKQ-nt3qaeJrq96w3A',
        '/viewform',
        '?usp=pp_url',
        '&entry.927104043=',
        coalesce(w.preferred_name_given_name, w.legal_name_given_name),
        ' ',
        coalesce(w.preferred_name_family_name, w.legal_name_family_name),
        ' - ',
        ifnull(w.home_work_location_name, ''),
        ' (',
        ltrim(cast(w.employee_number as string format '999999')),  -- Name + ID
        ')',
        '&entry.441236711=',
        i.route  -- Intent to Return Route
    ) as intent_to_return_personal_link
from {{ ref("base_people__staff_roster") }} as w
join itr_route as i on w.job_title = i.job_title
