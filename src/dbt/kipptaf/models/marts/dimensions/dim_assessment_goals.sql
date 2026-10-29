select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "g.academic_year",
                "g.school_id",
                "g.state_assessment_code",
                "g.grade_level",
                "g.illuminate_subject_area",
            ]
        )
    }} as assessment_goal_key,

    s.location_key,

    g.academic_year,
    g.state_assessment_code,
    g.illuminate_subject_area as academic_subject,
    g.grade_level,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,
    g.grade_band_goal,
    g.assessment_band_goal,
from {{ ref("stg_google_sheets__assessments__academic_goals") }} as g
inner join {{ ref("int_students__schools") }} as s on g.school_id = s.school_number
