APPLICATION_FIELDS = [
    {"name": "application_id", "type": ["null", "string"], "default": None},
    {"name": "application_state", "type": ["null", "string"], "default": None},
    {"name": "application_status", "type": ["null", "string"], "default": None},
    {"name": "candidate_id", "type": ["null", "string"], "default": None},
    {"name": "department_internal", "type": ["null", "string"], "default": None},
    {"name": "job_city", "type": ["null", "string"], "default": None},
    {"name": "job_title", "type": ["null", "string"], "default": None},
    {"name": "recruiters", "type": ["null", "string"], "default": None},
    {"name": "source_subtype", "type": ["null", "string"], "default": None},
    {"name": "source_type", "type": ["null", "string"], "default": None},
    {"name": "source", "type": ["null", "string"], "default": None},
    {
        "name": "application_reason_for_rejection",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_reason_for_withdrawal",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_status_before_rejection",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_status_before_withdrawal",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "time_in_application_state_in_review",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_state_interview",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_state_lead",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_state_new",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_state_offered",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_status_in_review_resume_review",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_status_interview_demo",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_status_interview_phone_screen_complete",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "time_in_application_status_interview_phone_screen_requested",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "application_state_new_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_hired_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_in_review_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_interview_date",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_state_lead_date",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_state_offer_date",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_state_rejected_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_transferred_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_withdrawn_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_in_review_resume_review_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_interview_demo_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_interview_phone_screen_complete_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_interview_phone_screen_requested_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_interview_performance_task_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_status_in_review_performance_task_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
]

APPLICANT_FIELDS = [
    {"name": "candidate_id", "type": ["null", "string"], "default": None},
    {"name": "application_id", "type": ["null", "string"], "default": None},
    {"name": "candidate_first_name", "type": ["null", "string"], "default": None},
    {"name": "candidate_last_name", "type": ["null", "string"], "default": None},
    {"name": "candidate_email", "type": ["null", "string"], "default": None},
    {"name": "current_employer", "type": ["null", "string"], "default": None},
    {"name": "candidate_tags_values", "type": ["null", "string"], "default": None},
    {
        "name": "application_field_school_shared_with_new_jersey",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_field_school_shared_with_miami",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_undergrad_gpa",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_grad_gpa",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_teacher_certification_question",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_out_of_state_teacher_certification_details",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_out_of_state_teacher_certification_sped_credits",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_out_of_state_sped_credits",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_miami_undergrad_gpa",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_miami_grad_gpa",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_miami_teacher_certification_question",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_miami_teacher_certification_endorsement_question",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_miami_out_of_state_teaching_certification_details",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_affiliated_orgs",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_other_orgs",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_city_of_interest",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_current_or_former_kipp_employee",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_current_or_former_kipp_nj_miami_employee",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_expected_salary",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_new_jersey_miami_how_did_you_hear_about_kipp_nj_miami",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_national_race",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_national_gender",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_national_are_you_alumnus",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "screening_question_answer_national_in_which_regions_alumnus",
        "type": ["null", "string"],
        "default": None,
    },
]

OFFERED_HIRED_FIELDS = [
    {"name": "candidate_email", "type": ["null", "string"], "default": None},
    {"name": "candidate_first_name", "type": ["null", "string"], "default": None},
    {"name": "candidate_id", "type": ["null", "string"], "default": None},
    {"name": "candidate_last_name", "type": ["null", "string"], "default": None},
    {"name": "candidate_tags_values", "type": ["null", "string"], "default": None},
    {"name": "hiring_managers", "type": ["null", "string"], "default": None},
    {"name": "job_title", "type": ["null", "string"], "default": None},
    {"name": "kf_gender", "type": ["null", "string"], "default": None},
    {"name": "race_ethnicity", "type": ["null", "string"], "default": None},
    {"name": "recruiters", "type": ["null", "string"], "default": None},
    {
        "name": "application_state_hired_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "application_state_offer_date",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "taf_current_or_former_kipp_employee",
        "type": ["null", "string"],
        "default": None,
    },
]

ASSET_FIELDS = {
    "applicants": APPLICANT_FIELDS,
    "applications": APPLICATION_FIELDS,
    "offered_hired": OFFERED_HIRED_FIELDS,
}
