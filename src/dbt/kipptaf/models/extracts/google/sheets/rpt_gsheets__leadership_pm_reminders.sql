select
    l.preferred_name_lastfirst,

    sr.mail,
    sr.reports_to_formatted_name as manager,
    sr.reports_to_mail as manager_mail,

    max(l.round_completion_self) as round_completion_self,
    max(l.round_completion_manager) as round_completion_manager,
from `kipptaf_tableau.rpt_tableau__leadership_development` as l
left join
    `kipptaf_people.int_people__staff_roster` as sr
    on l.employee_number = sr.employee_number
left join
    `kipptaf_appsheet.stg_leadership_development_active_users` as a
    on l.employee_number = safe_cast(a.employee_number as int)
where
    l.academic_year = 2024
    and (l.round_completion_self = 0 or l.round_completion_manager = 0)
    and l.active_assignment
    and a.active_title
    and not a.special_case
group by
    l.preferred_name_lastfirst,
    sr.mail,
    sr.reports_to_formatted_name,
    sr.reports_to_mail
