from pydantic import BaseModel


class Application(BaseModel):
    application_field_application_review_score: float | None = None
    application_field_job_title: str | None = None
    application_field_phone_interview_score: float | None = None
    application_id: str | None = None
    application_reason_for_rejection: str | None = None
    application_reason_for_withdrawal: str | None = None
    application_state_hired_date: str | None = None
    application_state_in_review_date: str | None = None
    application_state_interview_date: str | None = None
    application_state_lead_date: str | None = None
    application_state_new_date: str | None = None
    application_state_offer_date: str | None = None
    application_state_rejected_date: str | None = None
    application_state_transferred_date: str | None = None
    application_state_withdrawn_date: str | None = None
    application_state: str | None = None
    application_status_before_rejection: str | None = None
    application_status_before_withdrawal: str | None = None
    application_status_in_review_performance_task_date: str | None = None
    application_status_in_review_resume_review_date: str | None = None
    application_status_interview_demo_date: str | None = None
    application_status_interview_performance_task_date: str | None = None
    application_status_interview_phone_screen_complete_date: str | None = None
    application_status_interview_phone_screen_requested_date: str | None = None
    application_status: str | None = None
    candidate_email: str | None = None
    candidate_first_name: str | None = None
    candidate_id: str | None = None
    candidate_last_name: str | None = None
    candidate_source_subtype: str | None = None
    candidate_source_type: str | None = None
    candidate_source: str | None = None
    department_internal: str | None = None
    job_city: str | None = None
    job_title: str | None = None
    recruiters: str | None = None
    source_subtype: str | None = None
    source_type: str | None = None
    source: str | None = None
    time_in_application_state_in_review: float | None = None
    time_in_application_state_interview: float | None = None
    time_in_application_state_lead: float | None = None
    time_in_application_state_new: float | None = None
    time_in_application_state_offered: float | None = None
    time_in_application_status_in_review_resume_review: float | None = None
    time_in_application_status_interview_demo: float | None = None
    time_in_application_status_interview_phone_screen_complete: float | None = None
    time_in_application_status_interview_phone_screen_requested: float | None = None


class Applicant(BaseModel):
    candidate_id: str | None = None
    application_id: str | None = None
    candidate_first_name: str | None = None
    candidate_last_name: str | None = None
    candidate_email: str | None = None
    current_employer: str | None = None
    candidate_tags_values: str | None = None
    application_field_school_shared_with_new_jersey: str | None = None
    application_field_school_shared_with_miami: str | None = None
    screening_question_answer_new_jersey_undergrad_gpa: str | None = None
    screening_question_answer_new_jersey_grad_gpa: str | None = None
    screening_question_answer_new_jersey_teacher_certification_question: str | None = (
        None
    )
    screening_question_answer_new_jersey_out_of_state_teacher_certification_details: (
        str | None
    ) = None
    screening_question_answer_new_jersey_out_of_state_teacher_certification_sped_credits: (
        str | None
    ) = None
    screening_question_answer_new_jersey_out_of_state_sped_credits: str | None = None
    screening_question_answer_miami_undergrad_gpa: str | None = None
    screening_question_answer_miami_grad_gpa: str | None = None
    screening_question_answer_miami_teacher_certification_question: str | None = None
    screening_question_answer_miami_teacher_certification_endorsement_question: (
        str | None
    ) = None
    screening_question_answer_miami_out_of_state_teaching_certification_details: (
        str | None
    ) = None
    screening_question_answer_new_jersey_miami_affiliated_orgs: str | None = None
    screening_question_answer_new_jersey_miami_other_orgs: str | None = None
    screening_question_answer_new_jersey_miami_city_of_interest: str | None = None
    screening_question_answer_new_jersey_miami_current_or_former_kipp_employee: (
        str | None
    ) = None
    screening_question_answer_new_jersey_miami_current_or_former_kipp_nj_miami_employee: (
        str | None
    ) = None
    screening_question_answer_new_jersey_miami_expected_salary: str | None = None
    screening_question_answer_new_jersey_miami_how_did_you_hear_about_kipp_nj_miami: (
        str | None
    ) = None
    screening_question_answer_national_race: str | None = None
    screening_question_answer_national_gender: str | None = None
    screening_question_answer_national_are_you_alumnus: str | None = None
    screening_question_answer_national_in_which_regions_alumnus: str | None = None


class Rating(BaseModel):
    application_id: str | None = None
    candidate_id: str | None = None
    criteria_name: str | None = None
    criteria_rating: int | None = None


class OfferedHired(BaseModel):
    application_state_hired_date: str | None = None
    application_state_offer_date: str | None = None
    candidate_email: str | None = None
    candidate_first_name: str | None = None
    candidate_id: str | None = None
    candidate_last_name: str | None = None
    candidate_tags_values: str | None = None
    hiring_managers: str | None = None
    job_title: str | None = None
    kf_gender: str | None = None
    race_ethnicity: str | None = None
    recruiters: str | None = None
    taf_current_or_former_kipp_employee: str | None = None
