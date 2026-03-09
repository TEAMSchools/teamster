from pydantic import BaseModel


class StatusReport(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    finalsite_enrollment_id: str | None = None
    active_school_year: str | None = None
    self_contained: str | None = None
    assigned_school: str | None = None
    powerschool_student_number: str | None = None
    application_grade: str | None = None
    enrollment_type: str | None = None
    birthdate: str | None = None
    gender: str | None = None
    inquiry_date: str | None = None
    inquiry_completed_date: str | None = None
    inactive_inquiry_date: str | None = None
    applicant_date: str | None = None
    application_withdrawn_date: str | None = None
    deferred_date: str | None = None
    application_complete_date: str | None = None
    review_in_progress_date: str | None = None
    waitlisted_date: str | None = None
    denied_date: str | None = None
    ready_for_lottery_date: str | None = None
    accepted_date: str | None = None
    did_not_enroll_date: str | None = None
    assigned_school_date: str | None = None
    campus_transfer_requested_date: str | None = None
    parent_declined_date: str | None = None
    enrollment_in_progress_date: str | None = None
    academic_hold_date: str | None = None
    financial_hold_date: str | None = None
    not_enrolling_date: str | None = None
    enrolled_date: str | None = None
    mid_year_withdrawal_date: str | None = None
    never_attended_date: str | None = None
    retained_date: str | None = None
    summer_withdraw_date: str | None = None
    source_file_name: str | None = None
