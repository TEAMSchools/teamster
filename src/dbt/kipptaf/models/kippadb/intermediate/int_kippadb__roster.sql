with
    roster as (
        select
            co.student_number,
            co.studentid,
            co.academic_year as exit_academic_year,
            co.schoolid as exit_schoolid,
            co.school_name as exit_school_name,
            co.grade_level as exit_grade_level,
            co.exitdate as exit_date,
            co.exitcode as exit_code,
            co._dbt_source_relation as exit_db_name,
            ({{ var("current_academic_year") }} - co.academic_year)
            + co.grade_level as current_grade_level_projection,

            c.contact_id as sf_contact_id,
            c.contact_kipp_region_name,
            c.contact_kipp_region_school,
            c.contact_kipp_ms_graduate,
            c.contact_kipp_hs_graduate,
            c.contact_informed_consent,
            c.contact_transcript_release,
            c.contact_actual_hs_graduation_date,
            c.contact_actual_college_graduation_date,
            c.contact_latest_fafsa_date,
            c.contact_latest_state_financial_aid_app_date,
            c.contact_cumulative_gpa,
            c.contact_current_college_cumulative_gpa,
            c.contact_current_college_semester_gpa,
            c.contact_college_match_display_gpa,
            c.contact_highest_act_score,
            c.contact_college_credits_attempted,
            c.contact_accumulated_credits_college,
            c.contact_mobile_phone,
            c.contact_home_phone,
            c.contact_other_phone,
            c.contact_email,
            c.contact_postsecondary_status,
            c.contact_college_status,
            c.contact_currently_enrolled_school,
            c.contact_middle_school_attended,
            c.contact_high_school_graduated_from,
            c.contact_college_graduated_from,
            c.contact_gender,
            c.contact_ethnicity,
            c.contact_most_recent_iep_date,
            c.contact_efc_from_fafsa,
            c.contact_description,
            c.contact_expected_hs_graduation,
            c.contact_expected_college_graduation,
            c.contact_latest_transcript,
            c.contact_latest_resume,
            c.contact_last_outreach,
            c.contact_last_successful_contact,
            c.contact_last_successful_advisor_contact,
            c.contact_dep_post_hs_simple_admin,
            c.contact_owner_id,
            c.contact_owner_name,
            c.contact_owner_email,
            c.contact_owner_mobile_phone,
            c.record_type_name,
            ifnull(
                c.contact_current_kipp_student, 'Missing from Salesforce'
            ) as contact_current_kipp_student,
            if(
                c.contact_advising_provider = 'KIPP NYC', 'KNYC', 'KTAF'
            ) as contact_advising_provider,
            {{ var("current_fiscal_year") }}
            - extract(year from c.contact_actual_hs_graduation_date) as years_out_of_hs,

            ifnull(safe_cast(c.contact_kipp_hs_class as int), co.cohort) as ktc_cohort,
            ifnull(c.contact_first_name, co.first_name) as first_name,
            ifnull(c.contact_last_name, co.last_name) as last_name,
            ifnull(
                c.contact_last_name || ', ' || c.contact_first_name, co.lastfirst
            ) as lastfirst,

            case
                when co.enroll_status = 0
                then concat(co.school_level, co.grade_level)
                when c.contact_kipp_hs_graduate
                then 'HSG'
                /* identify HS grads before SF enr update */
                when (co.school_level = 'HS' and co.exitcode = 'G1')
                then 'HSG'
                when
                    (
                        c.contact_kipp_ms_graduate
                        and not c.contact_kipp_hs_graduate
                        and c.record_type_name = 'HS Student'
                    )
                then 'TAFHS'
                when (c.contact_kipp_ms_graduate and not c.contact_kipp_hs_graduate)
                then 'TAF'
            end as ktc_status,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        left join
            {{ ref("base_kippadb__contact") }} as c
            on co.student_number = safe_cast(c.contact_school_specific_id as int)
        where co.rn_undergrad = 1 and co.grade_level between 8 and 12
    )

select
    student_number,
    studentid,
    lastfirst,
    first_name,
    last_name,
    exit_academic_year,
    exit_schoolid,
    exit_school_name,
    exit_grade_level,
    exit_date,
    exit_code,
    exit_db_name,
    current_grade_level_projection,
    sf_contact_id,
    ktc_cohort,

    contact_accumulated_credits_college,
    contact_actual_college_graduation_date,
    contact_actual_hs_graduation_date,
    contact_advising_provider,
    contact_college_credits_attempted,
    contact_college_graduated_from,
    contact_college_match_display_gpa,
    contact_college_status,
    contact_cumulative_gpa,
    contact_current_college_cumulative_gpa,
    contact_current_college_semester_gpa,
    contact_current_kipp_student,
    contact_currently_enrolled_school,
    contact_dep_post_hs_simple_admin,
    contact_description,
    contact_efc_from_fafsa,
    contact_email,
    contact_ethnicity,
    contact_expected_college_graduation,
    contact_expected_hs_graduation,
    contact_gender,
    contact_high_school_graduated_from,
    contact_highest_act_score,
    contact_home_phone,
    contact_informed_consent,
    contact_kipp_hs_graduate,
    contact_kipp_ms_graduate,
    contact_kipp_region_name,
    contact_kipp_region_school,
    contact_last_outreach,
    contact_last_successful_advisor_contact,
    contact_last_successful_contact,
    contact_latest_fafsa_date,
    contact_latest_resume,
    contact_latest_state_financial_aid_app_date,
    contact_latest_transcript,
    contact_middle_school_attended,
    contact_mobile_phone,
    contact_most_recent_iep_date,
    contact_other_phone,
    contact_postsecondary_status,
    contact_transcript_release,

    contact_owner_email,
    contact_owner_id,
    contact_owner_mobile_phone,
    contact_owner_name,

    record_type_name,

    years_out_of_hs,
    ktc_status,
from roster
where ktc_status is not null
