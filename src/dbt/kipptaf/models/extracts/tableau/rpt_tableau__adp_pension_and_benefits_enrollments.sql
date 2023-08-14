select
    pb.employee_number,
    pb.plan_type,
    pb.plan_name,
    pb.coverage_level,
    pb.effective_date,

    cw.preferred_name_lastfirst as preferred_name,
    cw.assignment_status as position_status,
    cw.business_unit_home_name as legal_entity_name,
    cw.home_work_location_name as primary_site,
    cw.department_home_name as primary_on_site_department,
    cw.job_title as primary_job,
    cw.race_ethnicity_reporting as primary_race_ethnicity_reporting,
    cw.gender_identity as gender,
from
    {{
        source(
            "adp_workforce_now",
            "src_adp_workforce_now__pension_and_benefits_enrollments",
        )
    }} as pb
inner join
    {{ ref("base_people__staff_roster") }} as cw
    on pb.employee_number = cw.employee_number
