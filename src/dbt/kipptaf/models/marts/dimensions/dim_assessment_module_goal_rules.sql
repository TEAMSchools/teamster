select
    {{
        assessment_module_goal_rule_key(
            "region", "module_type", "illuminate_subject_area", "grade_min"
        )
    }} as assessment_module_goal_rule_key,

    module_type,
    grade_min,
    grade_max,
    goal,
    goal_offset,

    illuminate_subject_area as academic_subject,
from {{ ref("int_assessments__module_goal_rules") }}
