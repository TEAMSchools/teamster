with
    goal_years as (
        select distinct academic_year, from {{ ref("int_google_sheets__gpa_goals") }}
    )

select gp.student_number, gp.academic_year, gp.grade_level,
from {{ ref("rpt_tableau__gpa_goal_progress") }} as gp
inner join goal_years as gy on gp.academic_year = gy.academic_year
where gp.grade_level between 9 and 12 and gp.gpa_goal_proportion_org is null
