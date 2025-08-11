select
    id,
    ownerid as owner_id,
    recordtypeid as record_type_id,

    `description`,
    `name`,
    birthdate,
    email,
    firstname as first_name,
    homephone as home_phone,
    lastname as last_name,
    mobilephone as mobile_phone,

    actual_college_graduation_date__c as actual_college_graduation_date,
    actual_hs_graduation_date__c as actual_hs_graduation_date,
    advising_provider__c as advising_provider,
    college_graduated_from__c as college_graduated_from,
    college_match_display_gpa__c as college_match_display_gpa,
    current_college_cumulative_gpa__c as current_college_cumulative_gpa,
    current_college_semester_gpa__c as current_college_semester_gpa,
    current_kipp_student__c as current_kipp_student,
    currently_enrolled_school__c as currently_enrolled_school,
    dep_post_hs_simple_admin__c as dep_post_hs_simple_admin,
    efc_from_fafsa__c as efc_from_fafsa,
    ethnicity__c as ethnicity,
    expected_college_graduation__c as expected_college_graduation,
    expected_hs_graduation__c as expected_hs_graduation,
    full_name__c as full_name,
    gender__c as gender,
    has_hs_graduated_enrollment__c as has_hs_graduated_enrollment,
    high_school_graduated_from__c as high_school_graduated_from,
    highest_act_score__c as highest_act_score,
    highest_sat_score__c as highest_sat_score,
    kipp_hs_graduate__c as kipp_hs_graduate,
    kipp_ms_graduate__c as kipp_ms_graduate,
    kipp_region_name__c as kipp_region_name,
    last_outreach__c as last_outreach,
    last_successful_advisor_contact__c as last_successful_advisor_contact,
    last_successful_contact__c as last_successful_contact,
    latest_fafsa_date__c as latest_fafsa_date,
    latest_resume__c as latest_resume,
    latest_state_financial_aid_app_date__c as latest_state_financial_aid_app_date,
    middle_school_attended__c as middle_school_attended,
    most_recent_iep_date__c as most_recent_iep_date,
    opt_out_national_contact__c as opt_out_national_contact,
    opt_out_regional_contact__c as opt_out_regional_contact,
    postsecondary_status__c as postsecondary_status,

    safe_cast(kipp_hs_class__c as int) as kipp_hs_class,
    safe_cast(school_specific_id__c as int) as school_specific_id,

    mailingstreet
    || ' '
    || mailingcity
    || ', '
    || mailingstate
    || ' '
    || mailingpostalcode as mailing_address,
from {{ source("kippadb", "contact") }}
where not isdeleted
