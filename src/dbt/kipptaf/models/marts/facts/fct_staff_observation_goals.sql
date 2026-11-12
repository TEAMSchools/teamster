select
    {{
        dbt_utils.generate_surrogate_key(
            ["teacher_employee_number", "assignment_id", "goal_tag_id"]
        )
    }} as staff_observation_goal_key,

    {{ staff_key("teacher_employee_number") }} as teacher_staff_key,

    {{ staff_key("creator_employee_number", nullable=true) }} as creator_staff_key,

    {{ staff_observation_goal_type_key("goal_tag_id", "goal_name") }}
    as staff_observation_goal_type_key,

    {{ dbt_utils.generate_surrogate_key(["assignment_id"]) }}
    as staff_observation_assignment_key,

    assignment_date,
    assignment_created_timestamp,

    {{
        date_to_fiscal_year(
            date_field="assignment_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from {{ ref("int_performance_management__observation_goals") }}
