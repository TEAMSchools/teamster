import json

import py_avro_schema
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


"""
helper classes for backwards compatibility
"""


class person_data_record(PersonData): ...


class income_form_data_record(IncomeFormData): ...


ASSET_SCHEMA = {
    "person_data": json.loads(
        py_avro_schema.generate(py_type=person_data_record, namespace="person_data")
    ),
    "income_form_data": json.loads(
        py_avro_schema.generate(
            py_type=income_form_data_record, namespace="income_form_data"
        )
    ),
}
