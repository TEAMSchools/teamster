with
    matriculated_application as (
        select
            applicant,
            id as application_id,
            name as application_name,
            matriculation_decision,
            type as application_type,
            intended_degree_type,
            account_name as application_account_name,
            adjusted_6_year_minority_graduation_rate,

            row_number() over (partition by applicant order by id asc) as rn_applicant,
        from {{ ref("base_kippadb__application") }}
        where matriculation_decision = 'Matriculated (Intent to Enroll)'
    ),

    financial_aid_recent as (
        select
            enrollment,
            unmet_need,
            pell_grant,
            tap as tag,
            parent_plus_loan,
            stafford_loan_subsidized,
            stafford_loan_unsubsidized,
            other_private_loan,

            coalesce(parent_plus_loan, 0)
            + coalesce(stafford_loan_subsidized, 0)
            + coalesce(stafford_loan_unsubsidized, 0)
            + coalesce(other_private_loan, 0) as total_loan_amount,

            row_number() over (partition by enrollment order by name desc) as rn_award,
        from {{ ref("stg_kippadb__subsequent_financial_aid_award") }}
    )

select  -- noqa: disable=ST06
    -- noqa: disable=RF05
    ktc.contact_id as `Salesforce ID`,
    ktc.contact_school_specific_id as `SIS ID`,
    ktc.contact_owner_name as `College Counselor`,
    ktc.first_name as `First Name`,
    ktc.last_name as `Last Name`,
    ktc.contact_currently_enrolled_school as `Current Enrolled High School`,
    ktc.contact_mobile_phone as `Student Cell Phone`,
    ktc.email as `Personal Email Address`,
    if(
        ktc.ktc_status like 'TAF%', null, ktc.powerschool_contact_1_name
    ) as `Primary Parent Name`,
    if(
        ktc.ktc_status like 'TAF%',
        ktc.contact_home_phone,
        ktc.powerschool_contact_1_phone_mobile
    ) as `Primary Parent Cell Phone`,
    if(
        ktc.ktc_status like 'TAF%',
        ktc.contact_secondary_email,
        ktc.powerschool_contact_1_email_current
    ) as `Primary Parent Email`,
    if(
        ktc.ktc_status like 'TAF%',
        ktc.contact_mailing_address,
        ktc.powerschool_mailing_address
    ) as `Mailing Address`,
    if(ktc.contact_most_recent_iep_date is not null, true, false) as `IEP`,
    ktc.powerschool_is_504 as `504 Plan`,
    if(ktc.contact_latest_fafsa_date >= '2023-11-01', 'Yes', 'No') as `FAFSA Complete`,
    if(
        ktc.contact_latest_state_financial_aid_app_date is not null, 'Yes', 'No'
    ) as `HESAA Complete`,
    ktc.contact_efc_from_fafsa as `EFC Actual`,
    ktc.contact_expected_hs_graduation as expected_hs_grad_date,
    ktc.contact_college_match_display_gpa as college_match_display_gpa,
    ktc.contact_highest_act_score as highest_act_score,

    app.application_id,
    app.application_name,
    app.matriculation_decision,

    coalesce(cn.ccdm, 0) as `CCDM Complete`,

    app.application_account_name,
    app.application_type,
    app.intended_degree_type,

    fa.unmet_need,
    fa.pell_grant,
    fa.tag,
    fa.parent_plus_loan,
    fa.stafford_loan_subsidized,
    fa.stafford_loan_unsubsidized,
    fa.other_private_loan,
    fa.total_loan_amount,

    case
        when ktc.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when ktc.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when ktc.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when ktc.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when ktc.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,
    case
        when
            ktc.contact_college_match_display_gpa >= 3.50
            and round(app.adjusted_6_year_minority_graduation_rate, 0) < 68
        then true
        when
            ktc.contact_college_match_display_gpa >= 3.00
            and round(app.adjusted_6_year_minority_graduation_rate, 0) < 60
        then true
        when
            ktc.contact_college_match_display_gpa >= 2.50
            and round(app.adjusted_6_year_minority_graduation_rate, 0) < 55
        then true
        when
            ktc.contact_college_match_display_gpa < 2.50
            or ktc.contact_college_match_display_gpa is null
            or app.adjusted_6_year_minority_graduation_rate is null
        then null
        else false
    end as is_undermatch,
from {{ ref("int_kippadb__roster") }} as ktc
left join
    matriculated_application as app
    on ktc.contact_id = app.applicant
    and app.rn_applicant = 1
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as ei on ktc.contact_id = ei.student
left join
    {{ ref("int_kippadb__contact_note_rollup") }} as cn
    on ktc.contact_id = cn.contact_id
    and cn.academic_year = {{ var("current_academic_year") }}
left join
    financial_aid_recent as fa
    on ei.ugrad_enrollment_id = fa.enrollment
    and fa.rn_award = 1
