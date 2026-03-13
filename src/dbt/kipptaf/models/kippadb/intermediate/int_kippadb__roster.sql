with
    es_grad as (
        select
            co._dbt_source_relation,
            co.student_number,

            s.abbreviation as entry_school,

            max(
                if(
                    co.grade_level = 4
                    and co.exitdate >= date(co.academic_year + 1, 6, 1),
                    true,
                    false
                )
            ) as is_es_grad,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_powerschool__schools") }} as s
            on co.entry_schoolid = s.school_number
            and {{ union_dataset_join_clause(left_alias="co", right_alias="s") }}
        where co.rn_year = 1
        group by co._dbt_source_relation, co.student_number, s.abbreviation
    ),

    dlm as (
        select _dbt_source_relation, student_number, max(pathway_option) as dlm,
        from {{ ref("int_students__graduation_path_codes") }}
        where rn_discipline_distinct = 1 and final_grad_path_code = 'M'
        group by _dbt_source_relation, student_number
    ),

    tier as (
        select
            contact,
            `subject` as tier,

            row_number() over (
                partition by contact order by `date` desc
            ) as rn_tier_recent,
        from {{ ref("stg_kippadb__contact_note") }}
        where regexp_contains(`subject`, r'Tier\s\d$')
    ),

    military as (
        select
            contact,
            `status`,
            category as job_industry,
            military_branch,
            meps_location,
            meps_start_date,
            meps_end_date,
            delayed_entry_enlistment_program_dep,
            `start_date`,
            end_date,
            ineligible_for_military_enlistment,
            discharge_type,
            discharge_date,

            row_number() over (
                partition by contact order by start_date desc
            ) as rn_enlistment,
        from {{ ref("stg_kippadb__employment") }}
        where category = 'Military Specific Occupations'
    ),

    military_testing as (
        select
            contact,
            test_type,
            date as military_test_date,
            afqt_score,
            qualified_air_force,
            qualified_army,
            qualified_coast_guard,
            qualified_marine_corps,
            qualified_navy,
            total_qualified_military_branches,
            physical_training_requirement_passed,

            row_number() over (
                partition by contact, test_type order by date desc
            ) as rn_military_testing,
        from {{ ref("int_kippadb__standardized_test") }}
        where test_type in ('ASVAB', 'Military Physical Training')
    ),

    roster as (
        select
            se._dbt_source_relation as exit_db_name,
            se.student_number,
            se.studentid,
            se.state_studentnumber,
            se.dob,
            se.enroll_status as powerschool_enroll_status,
            se.street as powerschool_street,
            se.city as powerschool_city,
            se.state as powerschool_state,
            se.zip as powerschool_zip,
            se.academic_year as exit_academic_year,
            se.region,
            se.schoolid as exit_schoolid,
            se.school_name as exit_school_name,
            se.grade_level as exit_grade_level,
            se.exitdate as exit_date,
            se.exitcode as exit_code,
            se.is_504 as powerschool_is_504,
            se.lep_status,
            se.es_graduated,

            se.contact_1_email_current as powerschool_contact_1_email_current,
            se.contact_1_name as powerschool_contact_1_name,
            se.contact_1_phone_daytime as powerschool_contact_1_phone_daytime,
            se.contact_1_phone_home as powerschool_contact_1_phone_home,
            se.contact_1_phone_mobile as powerschool_contact_1_phone_mobile,
            se.contact_1_phone_primary as powerschool_contact_1_phone_primary,
            se.contact_1_phone_work as powerschool_contact_1_phone_work,
            se.contact_1_relationship as powerschool_contact_1_relationship,
            se.contact_2_email_current as powerschool_contact_2_email_current,
            se.contact_2_name as powerschool_contact_2_name,
            se.contact_2_phone_daytime as powerschool_contact_2_phone_daytime,
            se.contact_2_phone_home as powerschool_contact_2_phone_home,
            se.contact_2_phone_mobile as powerschool_contact_2_phone_mobile,
            se.contact_2_phone_primary as powerschool_contact_2_phone_primary,
            se.contact_2_phone_work as powerschool_contact_2_phone_work,
            se.contact_2_relationship as powerschool_contact_2_relationship,
            se.emergency_1_name as powerschool_emergency_contact_1_name,
            se.emergency_1_phone_daytime
            as powerschool_emergency_contact_1_phone_daytime,
            se.emergency_1_phone_home as powerschool_emergency_contact_1_phone_home,
            se.emergency_1_phone_mobile as powerschool_emergency_contact_1_phone_mobile,
            se.emergency_1_phone_primary
            as powerschool_emergency_contact_1_phone_primary,
            se.emergency_1_relationship as powerschool_emergency_contact_1_relationship,
            se.emergency_2_name as powerschool_emergency_contact_2_name,
            se.emergency_2_phone_daytime
            as powerschool_emergency_contact_2_phone_daytime,
            se.emergency_2_phone_home as powerschool_emergency_contact_2_phone_home,
            se.emergency_2_phone_mobile as powerschool_emergency_contact_2_phone_mobile,
            se.emergency_2_phone_primary
            as powerschool_emergency_contact_2_phone_primary,
            se.emergency_2_relationship as powerschool_emergency_contact_2_relationship,
            se.emergency_3_name as powerschool_emergency_contact_3_name,
            se.emergency_3_phone_daytime
            as powerschool_emergency_contact_3_phone_daytime,
            se.emergency_3_phone_home as powerschool_emergency_contact_3_phone_home,
            se.emergency_3_phone_mobile as powerschool_emergency_contact_3_phone_mobile,
            se.emergency_3_phone_primary
            as powerschool_emergency_contact_3_phone_primary,
            se.emergency_3_relationship as powerschool_emergency_contact_3_relationship,

            c.contact_id,
            c.contact_name,
            c.contact_description,
            c.contact_account_id,
            c.contact_assistant_name,
            c.contact_assistant_phone,
            c.contact_birthdate,
            c.contact_created_by_id,
            c.contact_created_date,
            c.contact_department,
            c.contact_email,
            c.contact_email_bounced_date,
            c.contact_email_bounced_reason,
            c.contact_fax,
            c.contact_first_name,
            c.contact_has_opted_out_of_email,
            c.contact_home_phone,
            c.contact_is_email_bounced,
            c.contact_jigsaw,
            c.contact_jigsaw_contact_id,
            c.contact_last_activity_date,
            c.contact_last_cu_request_date,
            c.contact_last_cu_update_date,
            c.contact_last_modified_by_id,
            c.contact_last_modified_date,
            c.contact_last_name,
            c.contact_last_referenced_date,
            c.contact_last_viewed_date,
            c.contact_lead_source,
            c.contact_mailing_address,
            c.contact_mailing_city,
            c.contact_mailing_country,
            c.contact_mailing_geocode_accuracy,
            c.contact_mailing_latitude,
            c.contact_mailing_longitude,
            c.contact_mailing_postal_code,
            c.contact_mailing_state,
            c.contact_mailing_street,
            c.contact_master_record_id,
            c.contact_mobile_phone,
            c.contact_other_address,
            c.contact_other_city,
            c.contact_other_country,
            c.contact_other_geocode_accuracy,
            c.contact_other_latitude,
            c.contact_other_longitude,
            c.contact_other_phone,
            c.contact_other_postal_code,
            c.contact_other_state,
            c.contact_other_street,
            c.contact_owner_id,
            c.contact_phone,
            c.contact_photo_url,
            c.contact_record_type_id,
            c.contact_reports_to_id,
            c.contact_salutation,
            c.contact_system_modstamp,
            c.contact_title,
            c.contact_academic_status,
            c.contact_academics,
            c.contact_accumulated_credits_college,
            c.contact_accumulated_credits_hs,
            c.contact_actual_college_graduation_date,
            c.contact_actual_hs_graduation_date,
            c.contact_advising_provider,
            c.contact_any_college_admin,
            c.contact_any_kipp_hs_enrollment,
            c.contact_associate_degree_grad_count,
            c.contact_attending_college_enrollments,
            c.contact_attending_hs_enrollments,
            c.contact_bach_degree_admin,
            c.contact_brag_sheet_submitted,
            c.contact_campus_staff_type,
            c.contact_career_training_program_status,
            c.contact_carrier,
            c.contact_class_quartile,
            c.contact_class_rank,
            c.contact_class_rank_percentile,
            c.contact_collaborative_advising_student,
            c.contact_college_apps_accepted,
            c.contact_college_apps_in_progress_wishlist,
            c.contact_college_apps_submitted,
            c.contact_college_counselor,
            c.contact_college_credits_attempted,
            c.contact_college_cumulative_credits_attempted,
            c.contact_college_cumulative_credits_earned,
            c.contact_college_graduated_from,
            c.contact_college_level,
            c.contact_college_match_display_gpa,
            c.contact_college_recommendation_complete,
            c.contact_college_status,
            c.contact_college_cte_attending_matric_enrollments,
            c.contact_contact_count,
            c.contact_counselor_s_school_name,
            c.contact_count_active_enrollments,
            c.contact_count_hs_graduated_enrollment,
            c.contact_count_of_bach_degree,
            c.contact_credits_accumlated_hs,
            c.contact_credits_accumulated_college,
            c.contact_cumulative_gpa,
            c.contact_cumulative_gpa_lookup,
            c.contact_current_academic_status,
            c.contact_current_college_cumulative_gpa,
            c.contact_current_college_semester_gpa,
            c.contact_current_college_standing,
            c.contact_current_cumulative_gpa,
            c.contact_current_level,
            c.contact_current_transcript_date,
            c.contact_current_transcript_term,
            c.contact_currently_enrolled_school,
            c.contact_date_last_opt_in_request,
            c.contact_date_no_postsec_pathway_confirmed,
            c.contact_date_of_mass_text_opt_in,
            c.contact_date_of_out_of_country_move,
            c.contact_dep_post_hs_simple_admin,
            c.contact_df_has_fafsa,
            c.contact_df_has_fafsa4caster,
            c.contact_df_has_gpa,
            c.contact_dual_enrollment,
            c.contact_earned_to_attempted_college_credits,
            c.contact_education_level,
            c.contact_efc_from_fafsa,
            c.contact_efc_from_fafsa4caster,
            c.contact_enlisted_in_military,
            c.contact_enrolled_at_ambassador_college,
            c.contact_enrolled_at_partner_college,
            c.contact_enrolled_in_kipp_hs_at_least_1_year,
            c.contact_ethnicity,
            c.contact_expected_college_graduation,
            c.contact_expected_hs_graduation,
            c.contact_external_student,
            c.contact_external_student_affiliation,
            c.contact_family_income_bracket,
            c.contact_financial,
            c.contact_financial_status,
            c.contact_first_generation_college_student,
            c.contact_flag_for_benchmark_follow_up,
            c.contact_frpl_eligible,
            c.contact_full_name,
            c.contact_full_time_employed,
            c.contact_gender,
            c.contact_gpa_in_major,
            c.contact_grad_school_attended,
            c.contact_grade_level,
            c.contact_has_active_collaborative_consent_form,
            c.contact_has_any_college_admin,
            c.contact_has_app_in_progress_wishlist,
            c.contact_has_applied_to_a_college,
            c.contact_has_been_accepted_to_college,
            c.contact_has_high_school_enrollment,
            c.contact_has_hs_graduated_enrollment,
            c.contact_has_linked_in_profile,
            c.contact_has_matric_college_enrollment,
            c.contact_has_taken_placement_test,
            c.contact_high_school_apps_accepted,
            c.contact_high_school_apps_in_progress_wishlist,
            c.contact_high_school_apps_submitted,
            c.contact_high_school_enrollments_count,
            c.contact_high_school_graduated_from,
            c.contact_high_school_status,
            c.contact_highest_act_diagnostic_score,
            c.contact_highest_act_score,
            c.contact_highest_psat_score,
            c.contact_highest_sat_score,
            c.contact_highest_sat_score_before_march_2016,
            c.contact_hs_recommendation_complete,
            c.contact_informed_consent,
            c.contact_intent_to_enlist,
            c.contact_kca_kipp_id,
            c.contact_kipp_college_class,
            c.contact_kipp_foundation_id,
            c.contact_kipp_hs_graduate,
            c.contact_kipp_ms_graduate,
            c.contact_kipp_region_name,
            c.contact_kipp_region_school,
            c.contact_language_spoken_at_home,
            c.contact_last_advisor_activity,
            c.contact_last_alumni_survey_completion_date,
            c.contact_last_outreach,
            c.contact_last_successful_advisor_contact,
            c.contact_last_successful_advisor_contact_range,
            c.contact_last_successful_contact,
            c.contact_last_successful_contact_range,
            c.contact_latest_fafsa_date,
            c.contact_latest_pfs_date,
            c.contact_latest_resume,
            c.contact_latest_state_financial_aid_app_date,
            c.contact_latest_transcript,
            c.contact_legal_status,
            c.contact_linked_in_profile_url,
            c.contact_maiden_name,
            c.contact_marital_status,
            c.contact_mass_text_opt_in_status,
            c.contact_matriculating_to_ambassador_college,
            c.contact_matriculating_to_partner_college,
            c.contact_media_release,
            c.contact_metro_card_sites,
            c.contact_middle_name,
            c.contact_middle_school_attended,
            c.contact_middle_skilling_trade_military_interest,
            c.contact_military_enlistments,
            c.contact_military_status,
            c.contact_most_advanced_app_status,
            c.contact_most_advanced_hsp,
            c.contact_most_recent,
            c.contact_most_recent_benchmark_status,
            c.contact_most_recent_college_application,
            c.contact_most_recent_college_benchmark,
            c.contact_most_recent_college_city,
            c.contact_most_recent_college_competitiveness,
            c.contact_most_recent_college_degree_type,
            c.contact_most_recent_college_enrollment,
            c.contact_most_recent_college_enrollment_id,
            c.contact_most_recent_college_enrollment_name,
            c.contact_most_recent_college_enrollment_status,
            c.contact_most_recent_college_gpa,
            c.contact_most_recent_college_graduation_rate,
            c.contact_most_recent_college_housing_from_app,
            c.contact_most_recent_college_is_hbcu,
            c.contact_most_recent_college_is_hsi,
            c.contact_most_recent_college_state,
            c.contact_most_recent_college_type,
            c.contact_most_recent_college_unmet_need_from_app,
            c.contact_most_recent_iep_date,
            c.contact_ms_gpa,
            c.contact_ms_teacher_recommendation,
            c.contact_nera_participant,
            c.contact_non_cognitive,
            c.contact_non_cognitive_status,
            c.contact_non_custodial_parent_letter_submitted,
            c.contact_not_pursuing_higher_ed_at_this_time,
            c.contact_nudge_texting_region,
            c.contact_number_in_household,
            c.contact_number_of_current_kipp_enrollments,
            c.contact_old_system_id,
            c.contact_opt_in_source,
            c.contact_opt_out_college_connections,
            c.contact_opt_out_national_contact,
            c.contact_opt_out_regional_contact,
            c.contact_other_gender,
            c.contact_out_of_country,
            c.contact_outreach_student,
            c.contact_overall_benchmark_status,
            c.contact_overgrad_time_last_synched,
            c.contact_parent_education_level,
            c.contact_partial_hs_class,
            c.contact_passion_purpose_plan,
            c.contact_pell_eligible,
            c.contact_personal_essay_completed,
            c.contact_picture,
            c.contact_picture_id,
            c.contact_post_hs_plan,
            c.contact_post_hs_status,
            c.contact_postsec_advisor,
            c.contact_postsecondary_status,
            c.contact_prevent_overgrad_synch,
            c.contact_primary_partnership_contact,
            c.contact_profile_goals,
            c.contact_qualified_asvab,
            c.contact_qualified_physical_training,
            c.contact_reason_for_prevent_overgrad_synch,
            c.contact_salesforce_id,
            c.contact_sat_superscore,
            c.contact_school_sis_id,
            c.contact_secondary_email,
            c.contact_socio_emotional,
            c.contact_socio_emotional_status,
            c.contact_student_disengagement_status,
            c.contact_student_level,
            c.contact_student_s_school,
            c.contact_student_segment_for_career_program,
            c.contact_tax_returns_submitted,
            c.contact_transcript_release,
            c.contact_undergrad_attended,
            c.contact_working_papers,
            c.contact_x2year_college_enrollments,
            c.contact_x8th_grade_promotion_date,
            c.contact_ytd_gpa,
            c.contact_kipp_hs_class,
            c.contact_school_specific_id,
            c.contact_owner_name,
            c.contact_owner_email,
            c.contact_owner_phone,
            c.record_type_name,
            c.record_type_description,
            c.record_type_last_modified_date,
            c.record_type_is_active,
            c.record_type_business_process_id,
            c.record_type_system_modstamp,
            c.record_type_sobject_type,
            c.record_type_created_by_id,
            c.record_type_created_date,
            c.record_type_developer_name,
            c.record_type_last_modified_by_id,
            c.record_type_namespace_prefix,
            c.graduation_year,
            c.contact_postsec_advisor_name,
            c.years_out_of_hs,

            os.id as overgrad_students_id,
            os.graduation_year as overgrad_students_graduation_year,
            os.school__name as overgrad_students_school,
            os.is_ed_ea,
            os.best_guess_pathway,
            os.desired_pathway,
            os.personal_statement_status,
            os.supplemental_essay_status,
            os.recommendation_1_status,
            os.recommendation_2_status,
            os.created_fsa_id_student,
            os.created_fsa_id_parent,
            os.common_app_linked,
            os.wishlist_signed_off_by_counselor,
            os.wishlist_notes,

            e.entry_school,
            e.is_es_grad,

            t.tier,

            mil.`status` as military_status,
            mil.military_branch,
            mil.meps_location,
            mil.meps_start_date,
            mil.meps_end_date,
            mil.delayed_entry_enlistment_program_dep,
            mil.`start_date` as bmt_start_date,
            mil.end_date as bmt_end_date,
            mil.ineligible_for_military_enlistment,
            mil.discharge_type as military_discharge_type,
            mil.discharge_date as military_discharge_date,

            ms.afqt_score,
            ms.qualified_air_force,
            ms.qualified_army,
            ms.qualified_coast_guard,
            ms.qualified_marine_corps,
            ms.qualified_navy,
            ms.total_qualified_military_branches,

            mpt.physical_training_requirement_passed,

            concat(
                os.assigned_counselor__last_name,
                ', ',
                os.assigned_counselor__first_name
            ) as overgrad_students_assigned_counselor_lastfirst,

            concat(
                se.street, ' ', se.city, ', ', se.state, ' ', se.zip
            ) as powerschool_mailing_address,

            coalesce(
                c.contact_current_kipp_student, 'Missing from Salesforce'
            ) as contact_current_kipp_student,

            coalesce(c.contact_kipp_hs_class, se.cohort) as ktc_cohort,
            coalesce(c.contact_first_name, se.student_first_name) as first_name,
            coalesce(c.contact_last_name, se.student_last_name) as last_name,
            coalesce(c.contact_lastfirst, se.student_name) as lastfirst,

            if(
                se.enroll_status = 0,
                coalesce(c.contact_email, se.student_email),
                c.contact_email
            ) as email,

            if(d.dlm is not null, true, false) as is_dlm,

            case
                when se.enroll_status = 0
                then concat(se.school_level, se.grade_level)
                when c.contact_kipp_hs_graduate
                then 'HSG'
                /* identify HS grads before SF enr update */
                when se.school_level = 'HS' and se.exitcode = 'G1'
                then 'HSG'
                when
                    c.contact_kipp_ms_graduate
                    and not c.contact_kipp_hs_graduate
                    and c.record_type_name = 'HS Student'
                then 'TAFHS'
                when c.contact_kipp_ms_graduate and not c.contact_kipp_hs_graduate
                then 'TAF'
            end as ktc_status,

            case
                when c.contact_college_match_display_gpa >= 3.50
                then '3.50+'
                when c.contact_college_match_display_gpa >= 3.00
                then '3.00-3.49'
                when c.contact_college_match_display_gpa >= 2.50
                then '2.50-2.99'
                when c.contact_college_match_display_gpa >= 2.00
                then '2.00-2.50'
                when c.contact_college_match_display_gpa < 2.00
                then '<2.00'
            end as hs_gpa_bands,

            (
                {{ var("current_academic_year") }} - se.academic_year + se.grade_level
            ) as current_grade_level_projection,
        from {{ ref("int_extracts__student_enrollments") }} as se
        left join
            {{ ref("base_kippadb__contact") }} as c
            on se.student_number = c.contact_school_specific_id
        left join
            {{ ref("int_overgrad__students") }} as os
            on se.salesforce_id = os.external_student_id
            and {{ union_dataset_join_clause(left_alias="se", right_alias="os") }}
        left join
            es_grad as e
            on se.student_number = e.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="e") }}
        left join
            dlm as d
            on se.student_number = d.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="d") }}
        left join tier as t on se.salesforce_id = t.contact and t.rn_tier_recent = 1
        left join
            military as mil on c.contact_id = mil.contact and mil.rn_enlistment = 1
        left join
            military_testing as ms
            on c.contact_id = ms.contact
            and ms.test_type = 'ASVAB'
            and ms.rn_military_testing = 1
        left join
            military_testing as mpt
            on c.contact_id = mpt.contact
            and mpt.test_type = 'Military Physical Training'
            and mpt.rn_military_testing = 1
        where se.rn_undergrad = 1 and se.grade_level between 8 and 12
    )

select *,
from roster
where ktc_status is not null
