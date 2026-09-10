-- Temporary wrapper. Passes rpt_tableau__gpa_cumulative_year through unchanged
-- and adds the four gpa_goal_* columns. A column added to that model does NOT
-- arrive here on its own -- add it to the select list below AND to this model's
-- contract yml, or it silently never reaches the Cumulative GPA Monitor.
-- Folding this into the extract is planned; see
-- docs/superpowers/specs/2026-09-01-student-goal-definitions-design.md
select
    cy._dbt_source_relation,
    cy._dbt_source_project,
    cy.studentid,
    cy.academic_year,
    cy.schoolid,
    cy.grade_level,
    cy.is_projected,
    cy.earned_credits_cum,
    cy.potential_gpa_credits_cum,
    cy.cumulative_y1_gpa,
    cy.cumulative_y1_gpa_unweighted,
    cy.student_number,
    cy.student_name,
    cy.academic_year_display,
    cy.region,
    cy.school_level,
    cy.school,
    cy.enroll_status,
    cy.cohort,
    cy.graduation_year,
    cy.gender,
    cy.ethnicity,
    cy.advisory,
    cy.year_in_school,
    cy.year_in_network,
    cy.rn_undergrad,
    cy.is_pathways,
    cy.is_retained_year,
    cy.is_retained_ever,
    cy.student_slideback,
    cy.lunch_status,
    cy.lep_status,
    cy.gifted_and_talented,
    cy.iep_status,
    cy.is_504,
    cy.salesforce_id,
    cy.ktc_cohort,
    cy.is_counseling_services,
    cy.is_student_athlete,
    cy.ada,
    cy.ada_above_or_at_80,
    cy.hos,
    cy.school_leader,
    cy.school_leader_tableau_username,
    cy.cumulative_y1_gpa_unweighted_as_of_today,
    cy.gpa_needed_for_cumulative_3_0,
    cy.is_cumulative_3_0_attainable,
    cy.potential_gpa_credits_current_year,
    cy.is_latest_graded_year,
    cy.is_on_cusp_3_0,
    cy.gpa_band_label,
    cy.gpa_band_as_of_today_label,

    gd.threshold as gpa_goal_threshold,
    gd.goal_proportion_org as gpa_goal_proportion_org,
    gd.goal_proportion_region as gpa_goal_proportion_region,
    gd.goal_proportion_school as gpa_goal_proportion_school,

from {{ ref("rpt_tableau__gpa_cumulative_year") }} as cy
left join
    {{ ref("int_gpa__student_goal_definitions") }} as gd
    on cy.student_number = gd.student_number
    and cy.academic_year = gd.academic_year
    and gd.metric = 'cumulative_gpa_unweighted'
