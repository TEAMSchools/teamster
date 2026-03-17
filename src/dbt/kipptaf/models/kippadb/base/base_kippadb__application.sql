with
    app_acct as (
        select
            app.id,
            app.name,
            app.record_type_id,
            app.created_by_id,
            app.created_date,
            app.last_activity_date,
            app.last_modified_by_id,
            app.last_modified_date,
            app.last_referenced_date,
            app.last_viewed_date,
            app.system_modstamp,
            app.abc_referral,
            app.admission_term,
            app.advisor_rank,
            app.anticipated_housing_situation,
            app.applicant,
            app.application_admission_type,
            app.application_count,
            app.application_source,
            app.application_status,
            app.application_submission_status,
            app.archived_application,
            app.books_and_supplies,
            app.calculated_due_date,
            app.commitment_form_sent,
            app.css_profile_submitted_to_college,
            app.date_of_initial_interest,
            app.days_until_due_date,
            app.due_date,
            app.due_date_status,
            app.due_date_status_color,
            app.early_action_due_date,
            app.early_decision_due_date,
            app.efc_from_fafsa,
            app.english_teacher_recommendation_submitted,
            app.expected_hs_graduation_date,
            app.fafsa_submitted_to_college,
            app.financial_aid_eligibility,
            app.financial_aid_entered,
            app.financial_aid_priority_due_date,
            app.gpa,
            app.gpa_type,
            app.honors_special_program_name,
            app.honors_special_program_status,
            app.intended_degree_type,
            app.intended_major,
            app.intended_major_area,
            app.interview_date,
            app.interview_status,
            app.match_type,
            app.math_teacher_recommendation_submitted,
            app.matriculation_decision,
            app.miscellaneous_expenses,
            app.net_cost_out_of_pocket,
            app.odds_of_admission,
            app.other_intended_major,
            app.other_reason_for_not_attending,
            app.parent_section_due_date,
            app.parent_section_submitted,
            app.primary_reason_for_not_attending,
            app.principal_recommenation_submitted,
            app.priority_application_due_date,
            app.recruitment_activity_participation,
            app.regular_decision_due_date,
            app.required_forms,
            app.required_forms_completed,
            app.room_board,
            app.school,
            app.school_section_due_date,
            app.school_section_submitted,
            app.student_rank,
            app.student_section_due_date,
            app.student_section_submitted,
            app.total_aid_accepted,
            app.total_aid_available,
            app.total_cost_of_attendance,
            app.total_federal_loans,
            app.total_gift_aid,
            app.total_work_study,
            app.transfer_application,
            app.transportation,
            app.tuition_and_fees,
            app.type,
            app.type_for_roll_ups,
            app.unmet_need,
            app.waitlist_placement,
            app.year_aid_package_received,

            acc.name as account_name,
            acc.type as account_type,
            acc.adjusted_6_year_minority_graduation_rate,
            acc.competitiveness_ranking,
            acc.act25,
            acc.act75,
            acc.act_composite_25_75,
            acc.adjusted_6_year_graduation_rate,
            acc.billing_state as account_billing_state,
            acc.hbcu,

            enr.status as enrollment_status,
            enr.pursuing_degree_type as enrollment_pursuing_degree_type,
            enr.start_date as enrollment_start_date,

            coalesce(
                app.starting_application_status, app.application_status
            ) as starting_application_status,

            coalesce(n.meets_full_need, false) as meets_full_need,
            coalesce(n.is_strong_oos_option, false) as is_strong_oos_option,

            if(app.type_for_roll_ups = 'College', true, false) as is_college,
            if(app.type_for_roll_ups = 'Alternative Program', true, false) as is_cte,
            if(
                app.type_for_roll_ups
                in ('Alternative Program', 'Organization', 'Other')
                or (app.type_for_roll_ups = 'College' and acc.type = 'Private 2 yr'),
                true,
                false
            ) as is_certificate,

            if(
                app.match_type in ('Likely Plus', 'Target', 'Reach'), true, false
            ) as is_ltr,
            if(
                app.starting_application_status = 'Wishlist', true, false
            ) as is_wishlist,
            if(
                app.application_submission_status = 'Submitted', true, false
            ) as is_submitted,
            if(app.application_status = 'Accepted', true, false) as is_accepted,

            if(
                app.application_admission_type = 'Early Action', true, false
            ) as is_early_action,
            if(
                app.application_admission_type = 'Early Decision', true, false
            ) as is_early_decision,

            if(app.honors_special_program_name like '%EOF%', true, false) as is_eof,
            if(
                app.honors_special_program_name like '%EOF%'
                and app.honors_special_program_status in ('Applied', 'Accepted'),
                true,
                false
            ) as is_eof_applied,
            if(
                app.honors_special_program_name like '%EOF%'
                and app.honors_special_program_status = 'Accepted',
                true,
                false
            ) as is_eof_accepted,

            if(
                app.matriculation_decision = 'Matriculated (Intent to Enroll)'
                and not app.transfer_application,
                true,
                false
            ) as is_matriculated,

            if(
                app.type_for_roll_ups = 'College' and acc.type like '%4 yr', true, false
            ) as is_4yr_college,
            if(
                app.type_for_roll_ups = 'College' and acc.type = 'Public 2 yr',
                true,
                false
            ) as is_2yr_college,

            row_number() over (
                partition by
                    app.applicant, app.matriculation_decision, app.transfer_application
                order by enr.start_date asc
            ) as rn_app_enr,
        from {{ ref("stg_kippadb__application") }} as app
        inner join {{ ref("stg_kippadb__account") }} as acc on app.school = acc.id
        inner join
            {{ ref("base_kippadb__contact") }} as c on app.applicant = c.contact_id
        left join
            {{ ref("stg_kippadb__enrollment") }} as enr
            on app.applicant = enr.student
            and app.school = enr.school
            and c.contact_kipp_hs_class = enr.start_date_year
            and enr.rn_stu_school_start = 1
        left join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as n
            on acc.id = n.account_id
            and n.rn_account = 1
    )

select
    id,
    `name`,
    record_type_id,
    created_by_id,
    created_date,
    last_activity_date,
    last_modified_by_id,
    last_modified_date,
    last_referenced_date,
    last_viewed_date,
    system_modstamp,
    abc_referral,
    admission_term,
    advisor_rank,
    anticipated_housing_situation,
    applicant,
    application_admission_type,
    application_count,
    application_source,
    application_status,
    application_submission_status,
    archived_application,
    books_and_supplies,
    calculated_due_date,
    commitment_form_sent,
    css_profile_submitted_to_college,
    date_of_initial_interest,
    days_until_due_date,
    due_date,
    due_date_status,
    due_date_status_color,
    early_action_due_date,
    early_decision_due_date,
    efc_from_fafsa,
    english_teacher_recommendation_submitted,
    expected_hs_graduation_date,
    fafsa_submitted_to_college,
    financial_aid_eligibility,
    financial_aid_entered,
    financial_aid_priority_due_date,
    gpa,
    gpa_type,
    honors_special_program_name,
    honors_special_program_status,
    intended_degree_type,
    intended_major,
    intended_major_area,
    interview_date,
    interview_status,
    match_type,
    math_teacher_recommendation_submitted,
    matriculation_decision,
    miscellaneous_expenses,
    net_cost_out_of_pocket,
    odds_of_admission,
    other_intended_major,
    other_reason_for_not_attending,
    parent_section_due_date,
    parent_section_submitted,
    primary_reason_for_not_attending,
    principal_recommenation_submitted,
    priority_application_due_date,
    recruitment_activity_participation,
    regular_decision_due_date,
    required_forms,
    required_forms_completed,
    room_board,
    school,
    school_section_due_date,
    school_section_submitted,
    student_rank,
    student_section_due_date,
    student_section_submitted,
    total_aid_accepted,
    total_aid_available,
    total_cost_of_attendance,
    total_federal_loans,
    total_gift_aid,
    total_work_study,
    transfer_application,
    transportation,
    tuition_and_fees,
    `type`,
    type_for_roll_ups,
    unmet_need,
    waitlist_placement,
    year_aid_package_received,
    starting_application_status,
    is_college,
    is_cte,
    is_certificate,
    is_ltr,
    is_wishlist,
    is_submitted,
    is_accepted,
    is_early_action,
    is_early_decision,
    is_eof,
    is_eof_applied,
    is_eof_accepted,
    is_matriculated,
    account_name,
    account_type,
    adjusted_6_year_minority_graduation_rate,
    competitiveness_ranking,
    act25,
    act75,
    act_composite_25_75,
    adjusted_6_year_graduation_rate,
    account_billing_state,
    hbcu,
    enrollment_status,
    enrollment_pursuing_degree_type,
    enrollment_start_date,
    is_4yr_college,
    is_2yr_college,
    rn_app_enr,
    meets_full_need,
    is_strong_oos_option,

    if(is_matriculated and is_4yr_college, true, false) as is_matriculated_ba,
    if(is_early_action or is_early_decision, true, false) as is_early_action_decision,
    if(is_submitted and is_2yr_college, true, false) as is_submitted_aa,
    if(is_submitted and is_4yr_college, true, false) as is_submitted_ba,
    if(is_submitted and is_certificate, true, false) as is_submitted_certificate,
    if(is_submitted and is_2yr_college and is_accepted, true, false) as is_accepted_aa,
    if(is_submitted and is_4yr_college and is_accepted, true, false) as is_accepted_ba,
    if(
        is_submitted and is_certificate and is_accepted, true, false
    ) as is_accepted_certificate,

    row_number() over (
        partition by applicant, school
        order by is_matriculated desc, is_accepted desc, is_submitted desc
    ) as rn_application_school,
from app_acct
