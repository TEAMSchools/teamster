select
    co.academic_year,
    co.student_number,

    app.account_billing_state as college_state,

    coalesce(app.account_name, 'NA') as college_name,

    if(co.exitcode = 'G1', 'Y', 'N') as exited_hs,

    case
        when app.enrollment_pursuing_degree_type = "Bachelor's (4-year)"
        then 'College - 4YR'
        when app.enrollment_pursuing_degree_type = "Associate's (2 year)"
        then 'College - 2YR'
        when app.enrollment_pursuing_degree_type = 'Certificate'
        then 'CTE (Certificate Program) or Diploma-Granting Program'
        when co.best_guess_pathway = 'Military'
        then 'Military'
        when co.best_guess_pathway = 'Workforce'
        then 'Straight to Work (non-certificate)'
        else 'Unknown'
    end as intended_pathway,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("int_kippadb__application") }} as app
    on co.salesforce_contact_id = app.applicant
    and app.matriculation_decision = 'Matriculated (Intent to Enroll)'
where co.rn_year = 1 and co.grade_level = 12
