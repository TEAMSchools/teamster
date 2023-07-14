{{ config(enabled=False) }}
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
            co.db_name as exit_db_name,

            c.id as sf_contact_id,
            c.kipp_region_name_c as kipp_region_name,
            c.kipp_region_school_c as kipp_region_school,
            c.kipp_ms_graduate_c as is_kipp_ms_graduate,
            c.kipp_hs_graduate_c as is_kipp_hs_graduate,
            c.informed_consent_c as is_informed_consent,
            c.transcript_release_c as is_transcript_release,
            c.expected_hs_graduation_c as expected_hs_graduation_date,
            c.actual_hs_graduation_date_c as actual_hs_graduation_date,
            c.expected_college_graduation_c as expected_college_graduation_date,
            c.actual_college_graduation_date_c as actual_college_graduation_date,
            c.latest_transcript_c as latest_transcript_date,
            c.latest_fafsa_date_c as latest_fafsa_date,
            c.latest_state_financial_aid_app_date_c
            as latest_state_financial_aid_app_date,
            c.cumulative_gpa_c as cumulative_gpa,
            c.current_college_cumulative_gpa_c as current_college_cumulative_gpa,
            c.current_college_semester_gpa_c as current_college_semester_gpa,
            c.college_match_display_gpa_c as college_match_display_gpa,
            c.highest_act_score_c as highest_act_score,
            c.college_credits_attempted_c as college_credits_attempted,
            c.accumulated_credits_college_c as accumulated_credits_college,
            c.mobile_phone as sf_mobile_phone,
            c.home_phone as sf_home_phone,
            c.other_phone as sf_other_phone,
            c.email as sf_email,
            c.post_hs_simple_admin_c as post_hs_simple_admin,
            c.postsecondary_status_c as postsecondary_status,
            c.college_status_c as college_status,
            c.currently_enrolled_school_c as currently_enrolled_school,
            c.middle_school_attended_c as middle_school_attended,
            c.high_school_graduated_from_c as high_school_graduated_from,
            c.college_graduated_from_c as college_graduated_from,
            c.gender_c as gender,
            c.ethnicity_c as ethnicity,
            c.most_recent_iep_date_c as most_recent_iep_date,
            c.latest_resume_c as latest_resume_date,
            c.last_outreach_c as last_outreach_date,
            c.last_successful_contact_c as last_successful_contact_date,
            c.last_successful_advisor_contact_c as last_successful_advisor_contact_date,
            c.efc_from_fafsa_c as efc_from_fafsa,
            c.description as contact_description,

            rt.name as record_type_name,

            u.id as counselor_sf_id,
            u.name as counselor_name,
            u.email as counselor_email,
            u.mobile_phone as counselor_phone,

            (utilities.global_academic_year() - co.academic_year)
            + co.grade_level as current_grade_level_projection,
            coalesce(
                c.current_kipp_student_c, 'Missing from Salesforce'
            ) as current_kipp_student,
            coalesce(c.kipp_hs_class_c, co.cohort) as ktc_cohort,
            (utilities.global_academic_year() + 1)
            - datepart(year, c.actual_hs_graduation_date_c) as years_out_of_hs,
            coalesce(c.first_name, co.first_name) as first_name,
            coalesce(c.last_name, co.last_name) as last_name,
            coalesce(c.last_name + ', ' + c.first_name, co.lastfirst) as lastfirst,
            case
                when co.enroll_status = 0
                then concat(co.school_level, co.grade_level)
                when c.kipp_hs_graduate_c = 1
                then 'HSG'
                /* identify HS grads before SF enr update */
                when (co.school_level = 'HS' and co.exitcode = 'G1')
                then 'HSG'
                when
                    (
                        c.kipp_ms_graduate_c = 1
                        and c.kipp_hs_graduate_c = 0
                        and rt.name = 'HS Student'
                    )
                then 'TAFHS'
                when (c.kipp_ms_graduate_c = 1 and c.kipp_hs_graduate_c = 0)
                then 'TAF'
            end as ktc_status,
            case
                when c.advising_provider_c = 'KIPP NYC' then 'KNYC' else 'KTAF'
            end as advising_provider
        from powerschool.cohort_identifiers_static as co
        left join
            alumni.contact as c
            on co.student_number = c.school_specific_id_c
            and c.is_deleted = 0
        left join alumni.record_type as rt on c.record_type_id = rt.id
        left join alumni.user as u on c.owner_id = u.id
        where co.rn_undergrad = 1 and co.grade_level between 8 and 12
    )

select
    sub.student_number,
    sub.studentid,
    sub.lastfirst,
    sub.first_name,
    sub.last_name,
    sub.exit_academic_year,
    sub.exit_schoolid,
    sub.exit_school_name,
    sub.exit_grade_level,
    sub.exit_date,
    sub.exit_code,
    sub.exit_db_name,
    sub.current_grade_level_projection,
    sub.sf_contact_id,
    sub.ktc_cohort,
    sub.kipp_region_name,
    sub.kipp_region_school,
    sub.is_kipp_ms_graduate,
    sub.is_kipp_hs_graduate,
    sub.is_informed_consent,
    sub.is_transcript_release,
    sub.expected_hs_graduation_date,
    sub.actual_hs_graduation_date,
    sub.expected_college_graduation_date,
    sub.actual_college_graduation_date,
    sub.latest_transcript_date,
    sub.latest_fafsa_date,
    sub.latest_state_financial_aid_app_date,
    sub.efc_from_fafsa,
    sub.cumulative_gpa,
    sub.current_college_cumulative_gpa,
    sub.current_college_semester_gpa,
    sub.college_match_display_gpa,
    sub.highest_act_score,
    sub.college_credits_attempted,
    sub.accumulated_credits_college,
    sub.sf_mobile_phone,
    sub.sf_home_phone,
    sub.sf_other_phone,
    sub.sf_email,
    sub.current_kipp_student,
    sub.post_hs_simple_admin,
    sub.postsecondary_status,
    sub.college_status,
    sub.currently_enrolled_school,
    sub.middle_school_attended,
    sub.high_school_graduated_from,
    sub.college_graduated_from,
    sub.gender,
    sub.ethnicity,
    sub.contact_description,
    sub.most_recent_iep_date,
    sub.latest_resume_date,
    sub.last_outreach_date,
    sub.last_successful_contact_date,
    sub.last_successful_advisor_contact_date,
    sub.years_out_of_hs,
    sub.record_type_name,
    sub.counselor_sf_id,
    sub.counselor_name,
    sub.counselor_email,
    sub.counselor_phone,
    sub.ktc_status,
    sub.advising_provider
from roster
where sub.ktc_status is not null
