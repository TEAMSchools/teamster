select
    e.* except (
        lastfirst,
        last_name,
        first_name,
        middle_name,
        school_abbreviation,
        advisory_section_number,
        student_email_google,
        salesforce_contact_id,
        salesforce_contact_df_has_fafsa,
        salesforce_contact_college_match_display_gpa,
        salesforce_contact_college_match_gpa_band,
        salesforce_contact_owner_name,
        state_studentnumber,
        `state`
    ),

    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.middle_name as student_middle_name,
    e.school_abbreviation as school,
    e.advisory_section_number as team,
    e.student_email_google as student_email,
    e.salesforce_contact_id as salesforce_id,
    e.salesforce_contact_df_has_fafsa as has_fafsa,
    e.salesforce_contact_college_match_display_gpa as college_match_gpa,
    e.salesforce_contact_college_match_gpa_band as college_match_gpa_bands,
    e.salesforce_contact_owner_name as contact_owner_name,

from {{ ref("base_powerschool__student_enrollments") }} as e
