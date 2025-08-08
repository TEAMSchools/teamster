select
    l.preferred_name_lastfirst,
    l.term,

    sr.mail,
    sr.reports_to_formatted_name as manager,
    sr.reports_to_mail as manager_mail,
    sr.home_work_location_name as `location`,
    sr.home_business_unit_code as entity,

    max(l.round_completion_self) as round_completion_self,
    max(l.round_completion_manager) as round_completion_manager,
from {{ ref("rpt_tableau__leadership_development") }} as l
left join
    {{ ref("int_people__staff_roster") }} as sr
    on l.employee_number = sr.employee_number
left join
    {{ ref("stg_leadership_development__active_users") }} as a
    on l.employee_number = safe_cast(a.employee_number as int)
where
    l.academic_year = {{ var("current_academic_year") }}
    and (l.round_completion_self = 0 or l.round_completion_manager = 0)
    and l.active_assignment
    and a.app_selection_active
    and sr.assignment_status in ('Active', 'Leave')
group by
    l.preferred_name_lastfirst,
    l.term,
    sr.mail,
    sr.reports_to_formatted_name,
    sr.reports_to_mail,
    sr.home_work_location_name,
    sr.home_business_unit_code
