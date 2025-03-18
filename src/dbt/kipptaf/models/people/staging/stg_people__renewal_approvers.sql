select
    academic_year,
    approver_employee_number,
    approver_name,
    approver_email,
    approval_level,
from {{ source("people", "src_people__renewal_approvers") }}
