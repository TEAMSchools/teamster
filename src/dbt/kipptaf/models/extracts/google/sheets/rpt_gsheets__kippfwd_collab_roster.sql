with
    ccdm as (  -- noqa: ST03
        select contact, `date`,
        from {{ ref("stg_kippadb__contact_note") }}
        where `subject` = 'CCDM'
    ),

    ccdm_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="ccdm", partition_by="contact", order_by="date desc"
            )
        }}
    )

select
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
    ktc.contact_df_has_fafsa as `FAFSA Complete`,
    if(
        ktc.contact_latest_state_financial_aid_app_date is not null, 'Yes', 'No'
    ) as `HESAA Complete`,
    ktc.contact_efc_from_fafsa as `EFC Actual`,
    ktc.contact_expected_hs_graduation as expected_hs_grad_date,
    ktc.contact_college_match_display_gpa as college_match_display_gpa,
    ktc.contact_highest_act_score as highest_act_score,

    app.id as application_id,
    app.name as application_name,
    app.matriculation_decision,

    if(cn.contact is null, 'No', 'Yes') as `CCDM Complete`,

    if(ktc.contact_college_match_display_gpa >= 3.0, 1, 0) as gpa_higher_than_3,

    if(ac.x6_yr_minority_completion_rate < 50, 1, 0) as minor_grad_rate_under50,

    if(
        ktc.contact_college_match_display_gpa between 2.5 and 2.9, 1, 0
    ) as gpa_between_25_29,

    if(ac.x6_yr_minority_completion_rate < 40, 1, 0) as minor_grad_rate_under40,

    if(
        ktc.contact_college_match_display_gpa >= 3.0
        and ac.x6_yr_minority_completion_rate < 50,
        1,
        0
    ) as undermatch_3gpa,
    if(
        ktc.contact_college_match_display_gpa between 2.5 and 2.9
        and ac.x6_yr_minority_completion_rate < 40,
        1,
        0
    ) as undermatch_25_29gpa,
from {{ ref("int_kippadb__roster") }} as ktc
left join
    {{ ref("base_kippadb__application") }} as app
    on ktc.contact_id = app.applicant
    and app.matriculation_decision = 'Matriculated (Intent to Enroll)'
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as ei on ktc.contact_id = ei.student
left join {{ ref("stg_kippadb__account") }} as ac on ei.ugrad_nces_id = ac.nces_id
left join ccdm_deduplicate as cn on ktc.contact_id = cn.contact
