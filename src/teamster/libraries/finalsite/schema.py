from pydantic import BaseModel


class StatusReport(BaseModel):
    finalsite_student_id: str | None = None
    powerschool_student_number: str | None = None
    enrollment_year: str | None = None
    enrollment_type: str | None = None
    status: str | None = None
    timestamp: str | None = None
    last_name: str | None = None
    first_name: str | None = None
    grade_level: str | None = None
    school: str | None = None
    source_file_name: str | None = None


class User(BaseModel):
    id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    updated_at: str | None = None
    type: str | None = None


class ContactStatus(BaseModel):
    name: str | None = None
    stage: str | None = None
    status_type: str | None = None


class Grade(BaseModel):
    id: str | None = None
    name: str | None = None
    long_name: str | None = None
    canonical_name: str | None = None
    school_level: str | None = None
    promote_to: str | None = None
    promote_grade_id: str | None = None
    created_at: str | None = None


class Phone(BaseModel):
    phone_type: str | None = None
    number: str | None = None


class Household(BaseModel):
    id: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class Relationship(BaseModel):
    id: str | None = None
    rel_id: str | None = None
    rel_name: str | None = None
    rel_type: str | None = None
    primary: bool | None = None
    financial: bool | None = None
    portal_access: bool | None = None


class SchoolYear(BaseModel):
    id: str | None = None
    name: str | None = None
    start_year: int | None = None
    created_at: str | None = None


class CustomAttribute(BaseModel):
    field_id: str | None = None
    field_name: str | None = None
    field_display_name: str | None = None

    value: bool | str | list[str] | None = None


class TrackAttribute(CustomAttribute):
    school_year: SchoolYear | None = None


class Field(BaseModel):
    id: str | None = None
    name: str | None = None
    display_name: str | None = None
    internal_description: str | None = None
    searchable: bool | None = None
    grouping: str | None = None
    parent_id: str | None = None
    ctype: str | None = None
    id_field_counter: int | None = None
    id_field_template: str | None = None
    id_field_autogenerate: bool | None = None
    is_track_siloed: bool | None = None
    created_at: str | None = None

    options: list[str] | None = None


class Contact(BaseModel):
    id: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    preferred_name: str | None = None
    email: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    gender_display: str | None = None
    gender_full_text: str | None = None
    status: str | None = None
    previous_school_1: str | None = None
    inquiry_submit_date: str | None = None
    application_submit_date: str | None = None
    contract_submit_date: str | None = None
    financial_aid_requested: bool | None = None
    financial_aid_amount_requested: str | None = None
    financial_aid_amount: str | None = None
    financial_aid_status: str | None = None
    scholarship_amount: str | None = None
    scholarship_status: str | None = None
    deposit_amount_paid: str | None = None
    tuition_override: str | None = None
    deposit_override: str | None = None
    enrollment_type: str | None = None
    is_alumni: bool | None = None
    review_decision: str | None = None
    billing_autopay_enabled: bool | None = None
    billing_contact_overdue: bool | None = None
    billing_overdue: bool | None = None
    billing_overdue_at: str | None = None
    billing_payment_method: str | None = None
    billing_payment_plan: str | None = None
    current_account_balance: str | None = None
    current_contact_balance: str | None = None
    next_account_balance: str | None = None
    next_account_billing_date: str | None = None
    next_billing_date: str | None = None
    next_contact_balance: str | None = None
    total_account_balance: str | None = None
    total_contact_balance: str | None = None

    school_year: SchoolYear | None = None
    prospect_entry_year: SchoolYear | None = None
    grade: Grade | None = None
    prospect_entry_grade: Grade | None = None
    phone_1: Phone | None = None
    phone_2: Phone | None = None
    phone_3: Phone | None = None

    households: list[Household] | None = None
    relationships: list[Relationship] | None = None
    custom_attributes: list[CustomAttribute] | None = None
    id_attributes: list[CustomAttribute] | None = None
    track_attributes: list[TrackAttribute] | None = None
