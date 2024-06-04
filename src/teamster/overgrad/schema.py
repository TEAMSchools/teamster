from pydantic import BaseModel


class StudentIDs(BaseModel):
    id: int | None = None
    external_student_id: str | None = None


class CustomFieldOption(BaseModel):
    id: int | None = None
    object: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    custom_field_id: int | None = None
    label: str | None = None


class CustomField(BaseModel):
    id: int | None = None
    object: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    name: str | None = None
    description: str | None = None
    resource_class: str | None = None
    field_type: str | None = None
    format: str | None = None
    student_can_view: bool | None = None
    student_can_edit: bool | None = None

    custom_field_options: list[CustomFieldOption | None] | None = None


class School(BaseModel):
    id: int | None = None
    object: str | None = None
    name: str | None = None


class AssignedCounselor(BaseModel):
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class Academics(BaseModel):
    unweighted_gpa: float | None = None
    weighted_gpa: float | None = None
    projected_act: int | None = None
    projected_sat: int | None = None
    act_superscore: int | None = None
    sat_superscore: int | None = None
    highest_act: int | None = None
    highest_preact: int | None = None
    highest_preact_8_9: int | None = None
    highest_aspire_10: int | None = None
    highest_aspire_9: int | None = None
    highest_sat: int | None = None
    highest_psat_nmsqt: int | None = None
    highest_psat_10: int | None = None
    highest_psat_8_9: int | None = None


class CustomFieldValue(BaseModel):
    custom_field_id: int | None = None
    number: float | None = None
    date: str | None = None
    select: int | None = None


class Student(StudentIDs):
    object: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    graduation_year: int | None = None
    telephone: str | None = None
    address: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    ethnicity: str | None = None
    family_income: str | None = None
    fafsa_completed: bool | None = None
    student_aid_index: float | None = None
    maximum_family_contribution: float | None = None
    pell_grant: float | None = None
    post_high_school_plan: str | None = None
    first_generation: bool | None = None
    fathers_education: str | None = None
    mothers_education: str | None = None
    awards: str | None = None
    extracurricular_activities: str | None = None
    interests: str | None = None
    target_grad_rate: float | None = None
    ideal_grad_rate: float | None = None

    school: School | None = None
    assigned_counselor: AssignedCounselor | None = None
    academics: Academics | None = None

    custom_field_values: list[CustomFieldValue | None] | None = None


class UniversityID(BaseModel):
    id: int | None = None
    ipeds_id: int | None = None


class University(UniversityID):
    city: str | None = None
    name: str | None = None
    object: str | None = None
    state: str | None = None
    status: str | None = None


class DueDate(BaseModel):
    date: str | None = None
    type: str | None = None


class AwardLetter(BaseModel):
    status: str | None = None
    tuition_and_fees: float | None = None
    housing_and_meals: float | None = None
    books_and_supplies: float | None = None
    transportation: float | None = None
    other_education_costs: float | None = None
    grants_and_scholarships_from_school: float | None = None
    federal_pell_grant: float | None = None
    grants_from_state: float | None = None
    other_scholarships: float | None = None
    work_study: float | None = None
    federal_perkins_loan: float | None = None
    federal_direct_subsidized_loan: float | None = None
    federal_direct_unsubsidized_loan: float | None = None
    parent_plus_loan: float | None = None
    military_benefits: float | None = None
    private_loan: float | None = None
    cost_of_attendance: float | None = None
    grants_and_scholarships: float | None = None
    net_cost: float | None = None
    loans: float | None = None
    other_options: float | None = None
    out_of_pocket: float | None = None
    unmet_need: float | None = None
    unmet_need_with_max_family_contribution: float | None = None
    seog: float | None = None


class Admission(BaseModel):
    id: int | None = None
    object: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    applied_on: str | None = None
    application_source: str | None = None
    status: str | None = None
    status_updated_at: str | None = None
    waitlisted: bool | None = None
    deferred: bool | None = None
    academic_fit: str | None = None
    probability_of_acceptance: float | None = None

    student: StudentIDs | None = None
    university: UniversityID | None = None
    due_date: DueDate | None = None
    award_letter: AwardLetter | None = None

    custom_field_values: list[CustomFieldValue | None] | None = None


class Following(BaseModel):
    id: int | None = None
    object: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    rank: int | None = None
    academic_fit: str | None = None
    probability_of_acceptance: float | None = None
    added_by: str | None = None

    student: StudentIDs | None = None
    university: UniversityID | None = None
