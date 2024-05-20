from pydantic import BaseModel


class PersonData(BaseModel):
    eligibility_benefit_type: str | None = None
    eligibility_end_date: str | None = None
    eligibility_start_date: str | None = None
    is_directly_certified: bool | None = None
    person_identifier: int | None = None
    application_academic_school_year: str | None = None
    application_approved_benefit_type: str | None = None
    eligibility_determination_reason: str | None = None

    eligibility: int | str | None = None
    total_balance: str | float | None = None
    total_positive_balance: str | float | None = None
    total_negative_balance: str | float | None = None


class IncomeFormData(BaseModel):
    student_identifier: int | None = None
    academic_year: str | None = None
    reference_code: str | None = None
    date_signed: str | None = None

    eligibility_result: int | str | None = None
