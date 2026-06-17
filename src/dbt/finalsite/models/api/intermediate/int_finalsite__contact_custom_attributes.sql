select
    c.finalsite_enrollment_id,

    max(
        if(a.field_name = 'academy_business_ss', a.value.string_value, null)
    ) as academy_business_ss,
    max(
        if(a.field_name = 'academy_commercial_ss', a.value.string_value, null)
    ) as academy_commercial_ss,
    max(
        if(a.field_name = 'academy_tech_ss', a.value.string_value, null)
    ) as academy_tech_ss,
    max(
        if(
            a.field_name = 'additional_phone_number_1_phone_number',
            a.value.string_value,
            null
        )
    ) as additional_phone_number_1_phone_number,
    max(
        if(
            a.field_name = 'additional_phone_number_1_phone_opt_in',
            a.value.boolean_value,
            null
        )
    ) as additional_phone_number_1_phone_opt_in,
    max(
        if(
            a.field_name = 'additional_phone_number_1_phone_type',
            a.value.string_value,
            null
        )
    ) as additional_phone_number_1_phone_type,
    any_value(
        if(a.field_name = 'address_verification_ms', a.value.array_string_value, null)
    ) as address_verification_ms,
    max(
        if(a.field_name = 'bsr_referral_method_ss', a.value.string_value, null)
    ) as bsr_referral_method_ss,
    max(
        if(a.field_name = 'bsr_referral_other_txt', a.value.string_value, null)
    ) as bsr_referral_other_txt,
    max(
        if(a.field_name = 'bus_interest_yn', a.value.boolean_value, null)
    ) as bus_interest_yn,
    max(
        if(a.field_name = 'categories_withdraw_reasons_ss', a.value.string_value, null)
    ) as categories_withdraw_reasons_ss,
    max(
        if(a.field_name = 'contact_attempts_ss', a.value.string_value, null)
    ) as contact_attempts_ss,
    max(
        if(a.field_name = 'current_residence_ss', a.value.string_value, null)
    ) as current_residence_ss,
    max(
        if(a.field_name = 'date_entered_us_school_date', a.value.string_value, null)
    ) as date_entered_us_school_date,
    max(
        if(a.field_name = 'decline_answer_ss', a.value.string_value, null)
    ) as decline_answer_ss,
    max(
        if(a.field_name = 'decline_reason_notes_txt', a.value.string_value, null)
    ) as decline_reason_notes_txt,
    max(
        if(a.field_name = 'decline_reasons_ss', a.value.string_value, null)
    ) as decline_reasons_ss,
    max(
        if(a.field_name = 'displacement_reason_ss', a.value.string_value, null)
    ) as displacement_reason_ss,
    max(
        if(a.field_name = 'displacement_reason_txt', a.value.string_value, null)
    ) as displacement_reason_txt,
    max(
        if(a.field_name = 'does_your_child_have_an_iep_ss', a.value.string_value, null)
    ) as does_your_child_have_an_iep_ss,
    max(
        if(
            a.field_name = 'does_your_child_receive_language_services_ss',
            a.value.string_value,
            null
        )
    ) as does_your_child_receive_language_services_ss,
    max(if(a.field_name = 'employer', a.value.string_value, null)) as employer,
    max(
        if(a.field_name = 'employment_status', a.value.string_value, null)
    ) as employment_status,
    max(if(a.field_name = 'emrg_1_email', a.value.string_value, null)) as emrg_1_email,
    max(
        if(a.field_name = 'emrg_1_name_first_name', a.value.string_value, null)
    ) as emrg_1_name_first_name,
    max(
        if(a.field_name = 'emrg_1_name_last_name', a.value.string_value, null)
    ) as emrg_1_name_last_name,
    max(
        if(a.field_name = 'emrg_1_name_middle_name', a.value.string_value, null)
    ) as emrg_1_name_middle_name,
    max(
        if(a.field_name = 'emrg_1_name_name_suffix', a.value.string_value, null)
    ) as emrg_1_name_name_suffix,
    max(
        if(a.field_name = 'emrg_1_name_name_title', a.value.string_value, null)
    ) as emrg_1_name_name_title,
    max(
        if(a.field_name = 'emrg_1_name_preferred_name', a.value.string_value, null)
    ) as emrg_1_name_preferred_name,
    max(
        if(a.field_name = 'emrg_1_phone_1_number', a.value.string_value, null)
    ) as emrg_1_phone_1_number,
    max(
        if(a.field_name = 'emrg_1_phone_1_opt_in', a.value.boolean_value, null)
    ) as emrg_1_phone_1_opt_in,
    max(
        if(a.field_name = 'emrg_1_phone_1_type', a.value.string_value, null)
    ) as emrg_1_phone_1_type,
    max(
        if(a.field_name = 'emrg_1_phone_2_number', a.value.string_value, null)
    ) as emrg_1_phone_2_number,
    max(
        if(a.field_name = 'emrg_1_phone_2_type', a.value.string_value, null)
    ) as emrg_1_phone_2_type,
    max(
        if(a.field_name = 'emrg_1_relationship_ss', a.value.string_value, null)
    ) as emrg_1_relationship_ss,
    max(
        if(a.field_name = 'emrg_1_relationship_txt', a.value.string_value, null)
    ) as emrg_1_relationship_txt,
    max(if(a.field_name = 'emrg_2_email', a.value.string_value, null)) as emrg_2_email,
    max(
        if(a.field_name = 'emrg_2_name_first_name', a.value.string_value, null)
    ) as emrg_2_name_first_name,
    max(
        if(a.field_name = 'emrg_2_name_last_name', a.value.string_value, null)
    ) as emrg_2_name_last_name,
    max(
        if(a.field_name = 'emrg_2_name_middle_name', a.value.string_value, null)
    ) as emrg_2_name_middle_name,
    max(
        if(a.field_name = 'emrg_2_name_name_suffix', a.value.string_value, null)
    ) as emrg_2_name_name_suffix,
    max(
        if(a.field_name = 'emrg_2_name_name_title', a.value.string_value, null)
    ) as emrg_2_name_name_title,
    max(
        if(a.field_name = 'emrg_2_name_preferred_name', a.value.string_value, null)
    ) as emrg_2_name_preferred_name,
    max(
        if(a.field_name = 'emrg_2_phone_1_number', a.value.string_value, null)
    ) as emrg_2_phone_1_number,
    max(
        if(a.field_name = 'emrg_2_phone_1_opt_in', a.value.boolean_value, null)
    ) as emrg_2_phone_1_opt_in,
    max(
        if(a.field_name = 'emrg_2_phone_1_type', a.value.string_value, null)
    ) as emrg_2_phone_1_type,
    max(
        if(a.field_name = 'emrg_2_phone_2_number', a.value.string_value, null)
    ) as emrg_2_phone_2_number,
    max(
        if(a.field_name = 'emrg_2_phone_2_type', a.value.string_value, null)
    ) as emrg_2_phone_2_type,
    max(
        if(a.field_name = 'emrg_2_relationship_ss', a.value.string_value, null)
    ) as emrg_2_relationship_ss,
    max(
        if(a.field_name = 'emrg_2_relationship_txt', a.value.string_value, null)
    ) as emrg_2_relationship_txt,
    max(
        if(a.field_name = 'fl_state_withdraw_codes_ss', a.value.string_value, null)
    ) as fl_state_withdraw_codes_ss,
    max(
        if(a.field_name = 'florida_residency_yn', a.value.boolean_value, null)
    ) as florida_residency_yn,
    max(
        if(a.field_name = 'import_description_txt', a.value.string_value, null)
    ) as import_description_txt,
    max(
        if(a.field_name = 'import_update_yn', a.value.boolean_value, null)
    ) as import_update_yn,
    max(
        if(a.field_name = 'intent_to_enroll_ynu_ss', a.value.string_value, null)
    ) as intent_to_enroll_ynu_ss,
    max(if(a.field_name = 'is_parent2', a.value.boolean_value, null)) as is_parent2,
    max(if(a.field_name = 'is_parent3', a.value.boolean_value, null)) as is_parent3,
    max(if(a.field_name = 'is_parent4', a.value.boolean_value, null)) as is_parent4,
    max(
        if(a.field_name = 'lang_first_nonenglish_yn', a.value.boolean_value, null)
    ) as lang_first_nonenglish_yn,
    max(
        if(a.field_name = 'lang_home_nonenglish_yn', a.value.boolean_value, null)
    ) as lang_home_nonenglish_yn,
    max(
        if(a.field_name = 'lang_parent_ss', a.value.string_value, null)
    ) as lang_parent_ss,
    max(
        if(a.field_name = 'lang_spoken_nonenglish_yn', a.value.boolean_value, null)
    ) as lang_spoken_nonenglish_yn,
    max(
        if(a.field_name = 'language_list', a.value.string_value, null)
    ) as language_list,
    max(
        if(a.field_name = 'latino_hispanic_yn', a.value.boolean_value, null)
    ) as latino_hispanic_yn,
    max(
        if(a.field_name = 'lead_source_ss', a.value.string_value, null)
    ) as lead_source_ss,
    max(
        if(a.field_name = 'lead_submit_date', a.value.string_value, null)
    ) as lead_submit_date,
    max(
        if(a.field_name = 'living_situation_ss', a.value.string_value, null)
    ) as living_situation_ss,
    max(
        if(a.field_name = 'mdcps_attendee_yn', a.value.boolean_value, null)
    ) as mdcps_attendee_yn,
    max(if(a.field_name = 'mdcps_id_txt', a.value.string_value, null)) as mdcps_id_txt,
    max(
        if(a.field_name = 'mdcps_student_1_birth_date', a.value.string_value, null)
    ) as mdcps_student_1_birth_date,
    max(
        if(a.field_name = 'mdcps_student_1_grade_ss', a.value.string_value, null)
    ) as mdcps_student_1_grade_ss,
    max(
        if(a.field_name = 'mdcps_student_1_id_txt', a.value.string_value, null)
    ) as mdcps_student_1_id_txt,
    max(
        if(a.field_name = 'mdcps_student_1_name_first_name', a.value.string_value, null)
    ) as mdcps_student_1_name_first_name,
    max(
        if(a.field_name = 'mdcps_student_1_name_last_name', a.value.string_value, null)
    ) as mdcps_student_1_name_last_name,
    max(
        if(
            a.field_name = 'mdcps_student_1_name_middle_name',
            a.value.string_value,
            null
        )
    ) as mdcps_student_1_name_middle_name,
    max(
        if(a.field_name = 'mdcps_student_1_name_name_title', a.value.string_value, null)
    ) as mdcps_student_1_name_name_title,
    max(
        if(a.field_name = 'mdcps_student_1_school_txt', a.value.string_value, null)
    ) as mdcps_student_1_school_txt,
    max(
        if(a.field_name = 'mdcps_student_1_yn', a.value.boolean_value, null)
    ) as mdcps_student_1_yn,
    max(
        if(a.field_name = 'mdcps_student_2_birth_date', a.value.string_value, null)
    ) as mdcps_student_2_birth_date,
    max(
        if(a.field_name = 'mdcps_student_2_grade_ss', a.value.string_value, null)
    ) as mdcps_student_2_grade_ss,
    max(
        if(a.field_name = 'mdcps_student_2_id_txt', a.value.string_value, null)
    ) as mdcps_student_2_id_txt,
    max(
        if(a.field_name = 'mdcps_student_2_name_first_name', a.value.string_value, null)
    ) as mdcps_student_2_name_first_name,
    max(
        if(a.field_name = 'mdcps_student_2_name_last_name', a.value.string_value, null)
    ) as mdcps_student_2_name_last_name,
    max(
        if(
            a.field_name = 'mdcps_student_2_name_middle_name',
            a.value.string_value,
            null
        )
    ) as mdcps_student_2_name_middle_name,
    max(
        if(a.field_name = 'mdcps_student_2_name_name_title', a.value.string_value, null)
    ) as mdcps_student_2_name_name_title,
    max(
        if(a.field_name = 'mdcps_student_2_school_txt', a.value.string_value, null)
    ) as mdcps_student_2_school_txt,
    max(
        if(a.field_name = 'mdcps_student_2_yn', a.value.boolean_value, null)
    ) as mdcps_student_2_yn,
    max(
        if(a.field_name = 'mdcps_student_3_yn', a.value.boolean_value, null)
    ) as mdcps_student_3_yn,
    max(
        if(a.field_name = 'med_considerations_txt', a.value.string_value, null)
    ) as med_considerations_txt,
    max(
        if(a.field_name = 'med_considerations_yn', a.value.boolean_value, null)
    ) as med_considerations_yn,
    max(
        if(a.field_name = 'med_doctor_phone_number', a.value.string_value, null)
    ) as med_doctor_phone_number,
    max(
        if(a.field_name = 'med_doctor_txt', a.value.string_value, null)
    ) as med_doctor_txt,
    max(
        if(a.field_name = 'med_emrg_info_txt', a.value.string_value, null)
    ) as med_emrg_info_txt,
    max(
        if(a.field_name = 'med_hospital_phone_number', a.value.string_value, null)
    ) as med_hospital_phone_number,
    max(
        if(a.field_name = 'med_hospital_txt', a.value.string_value, null)
    ) as med_hospital_txt,
    max(
        if(a.field_name = 'media_release_yn', a.value.boolean_value, null)
    ) as media_release_yn,
    max(
        if(a.field_name = 'mental_health_referrals_txt', a.value.string_value, null)
    ) as mental_health_referrals_txt,
    max(
        if(a.field_name = 'mental_health_referrals_yn', a.value.boolean_value, null)
    ) as mental_health_referrals_yn,
    max(
        if(a.field_name = 'military_parent_branch_txt', a.value.string_value, null)
    ) as military_parent_branch_txt,
    max(
        if(a.field_name = 'military_parent_yn', a.value.boolean_value, null)
    ) as military_parent_yn,
    max(
        if(a.field_name = 'nonpickup_1_name_first_name', a.value.string_value, null)
    ) as nonpickup_1_name_first_name,
    max(
        if(a.field_name = 'nonpickup_1_name_last_name', a.value.string_value, null)
    ) as nonpickup_1_name_last_name,
    max(
        if(a.field_name = 'nonpickup_1_name_middle_name', a.value.string_value, null)
    ) as nonpickup_1_name_middle_name,
    max(
        if(a.field_name = 'nonpickup_1_name_name_suffix', a.value.string_value, null)
    ) as nonpickup_1_name_name_suffix,
    max(
        if(a.field_name = 'nonpickup_1_name_name_title', a.value.string_value, null)
    ) as nonpickup_1_name_name_title,
    max(
        if(a.field_name = 'nonpickup_1_name_preferred_name', a.value.string_value, null)
    ) as nonpickup_1_name_preferred_name,
    max(
        if(a.field_name = 'nonpickup_1_yn', a.value.boolean_value, null)
    ) as nonpickup_1_yn,
    max(
        if(a.field_name = 'nonpickup_2_name_first_name', a.value.string_value, null)
    ) as nonpickup_2_name_first_name,
    max(
        if(a.field_name = 'nonpickup_2_name_last_name', a.value.string_value, null)
    ) as nonpickup_2_name_last_name,
    max(
        if(a.field_name = 'nonpickup_2_name_middle_name', a.value.string_value, null)
    ) as nonpickup_2_name_middle_name,
    max(
        if(a.field_name = 'nonpickup_2_name_name_title', a.value.string_value, null)
    ) as nonpickup_2_name_name_title,
    max(
        if(a.field_name = 'nonpickup_2_name_preferred_name', a.value.string_value, null)
    ) as nonpickup_2_name_preferred_name,
    max(
        if(a.field_name = 'nonpickup_2_yn', a.value.boolean_value, null)
    ) as nonpickup_2_yn,
    max(
        if(a.field_name = 'nonpickup_3_name_first_name', a.value.string_value, null)
    ) as nonpickup_3_name_first_name,
    max(
        if(a.field_name = 'nonpickup_3_name_last_name', a.value.string_value, null)
    ) as nonpickup_3_name_last_name,
    max(
        if(a.field_name = 'nonpickup_3_name_middle_name', a.value.string_value, null)
    ) as nonpickup_3_name_middle_name,
    max(
        if(a.field_name = 'nonpickup_3_name_name_title', a.value.string_value, null)
    ) as nonpickup_3_name_name_title,
    max(
        if(a.field_name = 'nonpickup_3_name_preferred_name', a.value.string_value, null)
    ) as nonpickup_3_name_preferred_name,
    max(
        if(a.field_name = 'nonpickup_3_yn', a.value.boolean_value, null)
    ) as nonpickup_3_yn,
    max(
        if(a.field_name = 'pickup_1_name_first_name', a.value.string_value, null)
    ) as pickup_1_name_first_name,
    max(
        if(a.field_name = 'pickup_1_name_last_name', a.value.string_value, null)
    ) as pickup_1_name_last_name,
    max(
        if(a.field_name = 'pickup_1_name_middle_name', a.value.string_value, null)
    ) as pickup_1_name_middle_name,
    max(
        if(a.field_name = 'pickup_1_name_name_suffix', a.value.string_value, null)
    ) as pickup_1_name_name_suffix,
    max(
        if(a.field_name = 'pickup_1_name_name_title', a.value.string_value, null)
    ) as pickup_1_name_name_title,
    max(
        if(a.field_name = 'pickup_1_name_preferred_name', a.value.string_value, null)
    ) as pickup_1_name_preferred_name,
    max(
        if(a.field_name = 'pickup_2_name_first_name', a.value.string_value, null)
    ) as pickup_2_name_first_name,
    max(
        if(a.field_name = 'pickup_2_name_last_name', a.value.string_value, null)
    ) as pickup_2_name_last_name,
    max(
        if(a.field_name = 'pickup_2_name_middle_name', a.value.string_value, null)
    ) as pickup_2_name_middle_name,
    max(
        if(a.field_name = 'pickup_2_name_name_suffix', a.value.string_value, null)
    ) as pickup_2_name_name_suffix,
    max(
        if(a.field_name = 'pickup_2_name_name_title', a.value.string_value, null)
    ) as pickup_2_name_name_title,
    max(
        if(a.field_name = 'pickup_2_name_preferred_name', a.value.string_value, null)
    ) as pickup_2_name_preferred_name,
    max(
        if(a.field_name = 'pickup_3_name_first_name', a.value.string_value, null)
    ) as pickup_3_name_first_name,
    max(
        if(a.field_name = 'pickup_3_name_last_name', a.value.string_value, null)
    ) as pickup_3_name_last_name,
    max(
        if(a.field_name = 'pickup_3_name_middle_name', a.value.string_value, null)
    ) as pickup_3_name_middle_name,
    max(
        if(a.field_name = 'pickup_3_name_name_suffix', a.value.string_value, null)
    ) as pickup_3_name_name_suffix,
    max(
        if(a.field_name = 'pickup_3_name_name_title', a.value.string_value, null)
    ) as pickup_3_name_name_title,
    max(
        if(a.field_name = 'pickup_3_name_preferred_name', a.value.string_value, null)
    ) as pickup_3_name_preferred_name,
    max(
        if(a.field_name = 'preschool_parent_paid_yn', a.value.boolean_value, null)
    ) as preschool_parent_paid_yn,
    max(
        if(a.field_name = 'preschool_type_ss', a.value.string_value, null)
    ) as preschool_type_ss,
    max(if(a.field_name = 'preschool_yn', a.value.boolean_value, null)) as preschool_yn,
    max(
        if(a.field_name = 'prev_arrested_txt', a.value.string_value, null)
    ) as prev_arrested_txt,
    max(
        if(a.field_name = 'prev_arrested_yn', a.value.boolean_value, null)
    ) as prev_arrested_yn,
    max(
        if(a.field_name = 'prev_expelled_txt', a.value.string_value, null)
    ) as prev_expelled_txt,
    max(
        if(a.field_name = 'prev_expelled_yn', a.value.boolean_value, null)
    ) as prev_expelled_yn,
    max(
        if(a.field_name = 'prev_juvenile_party_txt', a.value.string_value, null)
    ) as prev_juvenile_party_txt,
    max(
        if(a.field_name = 'prev_juvenile_party_yn', a.value.boolean_value, null)
    ) as prev_juvenile_party_yn,
    any_value(
        if(a.field_name = 'race_ms', a.value.array_string_value, null)
    ) as race_ms,
    max(if(a.field_name = 'school_1_ss', a.value.string_value, null)) as school_1_ss,
    max(
        if(a.field_name = 'school_1_status_ss', a.value.string_value, null)
    ) as school_1_status_ss,
    max(if(a.field_name = 'school_1_txt', a.value.string_value, null)) as school_1_txt,
    max(
        if(a.field_name = 'school_ops_caller_ss', a.value.string_value, null)
    ) as school_ops_caller_ss,
    max(
        if(a.field_name = 'self_contained_yn', a.value.boolean_value, null)
    ) as self_contained_yn,
    max(
        if(a.field_name = 'shirt_size_ss', a.value.string_value, null)
    ) as shirt_size_ss,
    max(if(a.field_name = 'sib_count_ss', a.value.string_value, null)) as sib_count_ss,
    max(
        if(a.field_name = 'sib_enrolled_yn', a.value.boolean_value, null)
    ) as sib_enrolled_yn,
    max(if(a.field_name = 'sib_grade_ss', a.value.string_value, null)) as sib_grade_ss,
    max(
        if(a.field_name = 'signature_date', a.value.string_value, null)
    ) as signature_date,
    max(
        if(a.field_name = 'sped_received_txt', a.value.string_value, null)
    ) as sped_received_txt,
    max(
        if(a.field_name = 'sped_received_yn', a.value.boolean_value, null)
    ) as sped_received_yn,
    max(
        if(a.field_name = 'staff_transport_yn', a.value.boolean_value, null)
    ) as staff_transport_yn,
    max(
        if(a.field_name = 'transfer_desired_campus_ss', a.value.string_value, null)
    ) as transfer_desired_campus_ss,
    max(
        if(a.field_name = 'transfer_reason_txt', a.value.string_value, null)
    ) as transfer_reason_txt,
    max(
        if(a.field_name = 'transfer_request_date', a.value.string_value, null)
    ) as transfer_request_date,
    max(
        if(a.field_name = 'unaccompanied_youth_yn', a.value.boolean_value, null)
    ) as unaccompanied_youth_yn,
    max(
        if(a.field_name = 'what_is_s_he_interested_in_txt', a.value.string_value, null)
    ) as what_is_s_he_interested_in_txt,
    max(
        if(
            a.field_name = 'what_is_your_child_excited_about_txt',
            a.value.string_value,
            null
        )
    ) as what_is_your_child_excited_about_txt,
    max(
        if(a.field_name = 'withdraw_reason_notes_txt', a.value.string_value, null)
    ) as withdraw_reason_notes_txt,
    max(
        if(a.field_name = 'withdrawal_last_attended_date', a.value.string_value, null)
    ) as withdrawal_last_attended_date,
    max(
        if(a.field_name = 'withdrawal_reason_ss', a.value.string_value, null)
    ) as withdrawal_reason_ss,
    max(
        if(a.field_name = 'withdrawal_school_address_city', a.value.string_value, null)
    ) as withdrawal_school_address_city,
    max(
        if(
            a.field_name = 'withdrawal_school_address_country',
            a.value.string_value,
            null
        )
    ) as withdrawal_school_address_country,
    max(
        if(a.field_name = 'withdrawal_school_address_state', a.value.string_value, null)
    ) as withdrawal_school_address_state,
    max(
        if(a.field_name = 'withdrawal_school_txt', a.value.string_value, null)
    ) as withdrawal_school_txt,
    max(
        if(a.field_name = 'withdrawal_transfer_type_ss', a.value.string_value, null)
    ) as withdrawal_transfer_type_ss,
from {{ ref("stg_finalsite__contacts") }} as c
cross join unnest(c.custom_attributes) as a
group by c.finalsite_enrollment_id
