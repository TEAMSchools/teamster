select
    enrollment_id,
    content_type,
    module_name,
    campaign_name,
    `status`,
    time_spent,
    policy_acknowledged,
    score,

    user.id as user_id,
    user.first_name as user_first_name,
    user.last_name as user_last_name,
    user.email as user_email,
    safe_cast(user.employee_number as int) as user_employee_number,

    timestamp(enrollment_date) as enrollment_date,
    timestamp(`start_date`) as `start_date`,
    timestamp(completion_date) as completion_date,
    extract(year from timestamp(enrollment_date)) as enrollment_year,
    extract(month from timestamp(enrollment_date)) as enrollment_month,
    row_number() over (
        partition by
            user.employee_number,
            extract(year from timestamp(enrollment_date)),
            extract(month from timestamp(enrollment_date))
        order by timestamp(enrollment_date) desc
    ) as rn_enrollment,
from {{ source("knowbe4", "src_knowbe4__training_enrollments") }}
