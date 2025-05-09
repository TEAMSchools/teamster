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
    user.employee_number as user_employee_number,

    timestamp(enrollment_date) as enrollment_date,
    timestamp(`start_date`) as `start_date`,
    timestamp(completion_date) as completion_date,
from {{ source("knowbe4", "src_knowbe4__training_enrollments") }}
