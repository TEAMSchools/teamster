select
    co.academic_year,
    co.student_number,

    app.account_billing_state as college_state,

    if(co.exitcode = 'G1', 'Y', 'N') as exited_hs,
    case
        when app.enrollment_pursuing_degree_type = "Bachelor's (4-year)"
        then 'College - 4YR'
        when app.enrollment_pursuing_degree_type = "Associate's (2 year)"
        then 'College - 2YR'
        when app.enrollment_pursuing_degree_type = 'Certificate'
        then 'CTE (Certificate Program) or Diploma-Granting Program'
        when r.best_guess_pathway = 'Military'
        then 'Military'
        when r.best_guess_pathway = 'Workforce'
        then 'Straight to Work (non-certificate)'
        else 'Unknown'
    end as intended_pathway,
    coalesce(app.account_name, 'NA') as college_name,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("base_kippadb__application") }} as app
    on co.salesforce_id = app.applicant
    and app.matriculation_decision = 'Matriculated (Intent to Enroll)'
left join {{ ref("int_kippadb__roster") }} as r on co.salesforce_id = r.contact_id
where co.rn_year = 1 and co.grade_level = 12
