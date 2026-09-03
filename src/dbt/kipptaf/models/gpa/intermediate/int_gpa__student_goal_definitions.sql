select
    e.academic_year,
    e.student_number,

    go.metric,
    go.threshold,
    go.direction,
    go.higher_is_better,
    go.goal_proportion as goal_proportion_org,

    gr.goal_proportion as goal_proportion_region,

    gs.goal_proportion as goal_proportion_school,
from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_google_sheets__gpa_goals") }} as go
    on e.academic_year = go.academic_year
    and e.grade_level between go.grade_low and go.grade_high
    and go.org_level = 'org'
left join
    {{ ref("int_google_sheets__gpa_goals") }} as gr
    on e.academic_year = gr.academic_year
    and e.region = gr.region
    and e.grade_level between gr.grade_low and gr.grade_high
    and go.metric = gr.metric
    and gr.org_level = 'region'
left join
    {{ ref("int_google_sheets__gpa_goals") }} as gs
    on e.academic_year = gs.academic_year
    and e.schoolid = gs.schoolid
    and e.grade_level between gs.grade_low and gs.grade_high
    and go.metric = gs.metric
    and gs.org_level = 'school'
where e.rn_year = 1
