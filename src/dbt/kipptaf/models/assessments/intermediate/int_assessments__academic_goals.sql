select
    g.academic_year,
    g.school_id,
    g.grade_level,
    g.state_assessment_code,
    g.illuminate_subject_area,
    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,
    g.grade_band_goal,
    g.assessment_band_goal,

    s.school_level,

    initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')) as region,
from {{ ref("stg_google_sheets__assessments__academic_goals") }} as g
inner join {{ ref("stg_powerschool__schools") }} as s on g.school_id = s.school_number
