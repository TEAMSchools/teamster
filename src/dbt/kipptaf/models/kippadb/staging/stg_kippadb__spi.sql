select
    r.contact_id,
    r.lastfirst as student_name,
    r.ktc_cohort as cohort,
    r.contact_advising_provider as advising_provider,
    r.contact_owner_name,
    r.contact_expected_hs_graduation as expected_hs_graduation,
    r.contact_college_match_display_gpa as hs_gpa,
    r.contact_highest_act_score as highest_act_score,
    e.status,
    e.pursuing_degree_type,
    e.start_date,
    e.actual_end_date,
    e.account_type,
    a.competitiveness_ranking,
    a.act25,
    a.act75,
    a.act_composite_25_75,
    a.adjusted_6_year_graduation_rate,
    a.adjusted_6_year_minority_graduation_rate,
    a.billing_state as school_state,
    a.name as school_name,
    a.hbcu,
    if(e.id = ei.ecc_enrollment_id, true, false) as is_ecc_enrollment,
    if(e.id = ei.ugrad_enrollment_id, true, false) as is_ugrad_enrollment,
    case
        when
            e.school = ei.ecc_account_id
            and e.status = 'Graduated'
            and e.actual_end_date <= date(r.ktc_cohort + 4, 08, 31)
        then 1
        when
            e.school = ei.ecc_account_id
            and e.status = 'Graduated'
            and e.actual_end_date > date(r.ktc_cohort + 4, 08, 31)
        then 0
        when
            e.school = ei.ecc_account_id
            and e.status != 'Graduated'
            and e.actual_end_date is not null
        then 0
    end as is_4yr_grad_int,
    case
        when
            e.school = ei.ecc_account_id
            and e.status = 'Graduated'
            and e.actual_end_date <= date(r.ktc_cohort + 6, 08, 31)
        then 1
        when
            e.school = ei.ecc_account_id
            and e.status = 'Graduated'
            and e.actual_end_date > date(r.ktc_cohort + 6, 08, 31)
        then 0
        when
            e.school = ei.ecc_account_id
            and e.status != 'Graduated'
            and e.actual_end_date is not null
        then 0
    end as is_6yr_grad_int,
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
    and e.pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)")
    and e.status != 'Did Not Enroll'
left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student
