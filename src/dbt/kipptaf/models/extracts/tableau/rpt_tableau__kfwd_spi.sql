select
    r.contact_id,
    r.lastfirst as student_name,
    r.ktc_cohort as cohort,
    r.contact_advising_provider as advising_provider,
    r.contact_owner_name,
    r.contact_current_kipp_student as current_kipp_student,
    r.contact_currently_enrolled_school as currently_enrolled_school,
    r.contact_expected_hs_graduation as expected_hs_graduation,
    r.contact_college_match_display_gpa as hs_gpa,
    r.contact_highest_act_score as highest_act_score,

    e.status,
    e.pursuing_degree_type,
    e.start_date,
    e.actual_end_date,
    e.account_type,

    ei.ugrad_status,
    ei.hs_account_name,
    ei.ecc_account_name,
    ei.ugrad_account_name,

    a.competitiveness_ranking,
    a.act25,
    a.act75,
    a.act_composite_25_75,
    a.adjusted_6_year_graduation_rate,
    a.adjusted_6_year_minority_graduation_rate,
    a.billing_state as school_state,
    a.name as school_name,
    a.hbcu,

    'Enrollments' as `data_source`,

    null as match_type,
    null as application_admission_type,
    null as application_status,
    null as application_submission_status,
    null as matriculation_decision,
    null as is_early_action_decision,
    null as is_early_action,
    null as is_early_decision,
    null as is_ed_ea,
    null as student_aid_index,
    null as best_guess_pathway,

    if(e.status = 'Graduated', true, false) as is_graduated,
    if(e.id = ei.ecc_enrollment_id, true, false) as is_ecc_enrollment,
    if(e.id = ei.ugrad_enrollment_id, true, false) as is_ugrad_enrollment,
    case
        when
            e.status in ('Attending', 'Graduated')
            and r.ktc_cohort
            between {{ var("current_academic_year") - 5 }}
            and {{ var("current_academic_year") }}
        then true
        when
            e.status not in ('Attending', 'Graduated')
            and r.ktc_cohort
            between {{ var("current_academic_year") - 5 }}
            and {{ var("current_academic_year") }}
        then false
    end as is_continuing_completing,

    if(ei.ecc_account_name = ei.ugrad_account_name, 1, 0) as is_same_school,

    case
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 4 }}
            and e.status = 'Graduated'
            and e.actual_end_date <= date(r.ktc_cohort + 4, 08, 31)
        then 1
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 4 }}
            and e.status = 'Graduated'
            and e.actual_end_date > date(r.ktc_cohort + 4, 08, 31)
        then 0
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 4 }}
            and e.status != 'Graduated'
            and e.actual_end_date is not null
        then 0
    end as is_4yr_grad_int,

    case
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 6 }}
            and e.status = 'Graduated'
            and e.actual_end_date <= date(r.ktc_cohort + 6, 08, 31)
        then 1
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 6 }}
            and e.status = 'Graduated'
            and e.actual_end_date > date(r.ktc_cohort + 6, 08, 31)
        then 0
        when
            e.school = ei.ecc_account_id
            and r.ktc_cohort <= {{ var("current_academic_year") - 6 }}
            and e.status != 'Graduated'
            and e.actual_end_date is not null
        then 0
    end as is_6yr_grad_int,

    case
        when
            r.ktc_cohort <= {{ var("current_academic_year") - 4 }}
            and e.status = 'Graduated'
        then 1
        when
            r.ktc_cohort <= {{ var("current_academic_year") - 4 }}
            and e.status != 'Graduated'
        then 0
    end as is_grad_ever_any,

    case
        when r.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when r.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when r.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when r.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when r.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,
from {{ ref("int_kippadb__roster") }} as r
inner join
    {{ ref("stg_kippadb__enrollment") }} as e
    on r.contact_id = e.student
    and e.status != 'Did Not Enroll'
left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student

union all

select
    r.contact_id,
    r.lastfirst as student_name,
    r.ktc_cohort as cohort,
    r.contact_advising_provider as advising_provider,
    r.contact_owner_name,
    r.contact_current_kipp_student as current_kipp_student,
    r.contact_currently_enrolled_school as currently_enrolled_school,
    r.contact_expected_hs_graduation as expected_hs_graduation,
    r.contact_college_match_display_gpa as hs_gpa,
    r.contact_highest_act_score as highest_act_score,

    a.application_status as `status`,
    a.intended_degree_type as pursuing_degree_type,
    safe_cast(a.created_date as date) as `start_date`,

    null as actual_end_date,

    a.account_type,

    null as ugrad_status,

    ei.hs_account_name,

    null as ecc_account_name,
    null as ugrad_account_name,

    a.competitiveness_ranking,
    a.act25,
    a.act75,
    a.act_composite_25_75,
    a.adjusted_6_year_graduation_rate,
    a.adjusted_6_year_minority_graduation_rate,
    a.account_billing_state as school_state,
    a.account_name as school_name,
    a.hbcu,

    'Applications' as `data_source`,

    a.match_type,
    a.application_admission_type,
    a.application_status,
    a.application_submission_status,
    a.matriculation_decision,
    a.is_early_action_decision,
    a.is_early_action,
    a.is_early_decision,

    r.is_ed_ea,
    r.contact_efc_from_fafsa as student_aid_index,
    r.best_guess_pathway,

    false as is_graduated,
    null as is_ecc_enrollment,
    null as is_ugrad_enrollment,
    null as is_continuing_completing,
    null as is_same_school,
    null as is_4yr_grad_int,
    null as is_6yr_grad_int,
    null as is_grad_ever_any,

    case
        when r.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when r.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when r.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when r.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when r.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,
from {{ ref("int_kippadb__roster") }} as r
left join
    {{ ref("base_kippadb__application") }} as a
    on r.contact_id = a.applicant
    and a.rn_application_school = 1
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student
