from pydantic import BaseModel


class PersonData(BaseModel):
    application_academic_school_year: str | None = None
    application_approved_benefit_type: str | None = None
    eligibility_benefit_type: str | None = None
    eligibility_determination_reason: str | None = None
    eligibility_end_date: str | None = None
    eligibility_start_date: str | None = None
    eligibility: str | None = None
    is_directly_certified: str | None = None
    person_identifier: str | None = None
    total_balance: str | None = None
    total_negative_balance: str | None = None
    total_positive_balance: str | None = None


class IncomeFormData(BaseModel):
    academic_year: str | None = None
    date_signed: str | None = None
    eligibility_result: str | None = None
    reference_code: str | None = None
    student_identifier: str | None = None
