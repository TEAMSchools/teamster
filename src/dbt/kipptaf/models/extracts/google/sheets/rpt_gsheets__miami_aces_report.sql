select
    job_title,
    home_work_location_name,
    assignment_status,
    legal_given_name,
    legal_family_name,
    position_id,
    home_business_unit_name,
    employee_number,
    worker_original_hire_date,
    wage_law_coverage as payclass,
    legal_address_line_one as street,
    legal_address_city_name as city,
    legal_address_country_subdivision_level_1_code as `state`,
    legal_address_postal_code as post_code,
    base_remuneration_annual_rate_amount as salary,
    worker_termination_date,
    level_of_education,
    miami_aces_number,
    birth_date,
    '2x Month' as pay_frequency,
    '' as duty_days,
    'N/A' as teacher_eval,
    'N/A' as contribution504b,
    'B' as basiclifeplan,
from {{ ref("int_people__staff_roster") }}
where
    home_business_unit_name = 'KIPP Miami'
    and (
        worker_termination_date >= date({{ var("current_academic_year") }}, 07, 01)
        or worker_termination_date is null
    )
