-- depends_on: {{ ref("stg_google_sheets__assessments__academic_goals") }}
select
    academic_year,
    school_id,
    grade_level,
    state_assessment_code,
    illuminate_subject_area,

    count(*) as n_rows,
from {{ source("google_sheets", "src_google_sheets__assessments__academic_goals") }}
group by
    academic_year,
    school_id,
    grade_level,
    state_assessment_code,
    illuminate_subject_area
having count(*) > 1
