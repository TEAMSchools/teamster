import json

import py_avro_schema
from pydantic import BaseModel


class AdditionalEarnings(BaseModel):
    additional_earnings_code: str | None = None
    check_voucher_number: str | int | None = None
    cost_number_description: str | None = None
    cost_number: str | None = None
    employee_number: float | None = None
    file_number_pay_statements: int | None = None
    gross_pay: str | None = None
    pay_date: str | None = None
    payroll_company_code: str | None = None
    position_status: str | None = None
    additional_earnings_description: str | None = None


class ComprehensiveBenefits(BaseModel):
    position_id: str | None = None
    plan_type: str | None = None
    plan_name: str | None = None
    coverage_level: str | None = None


class PensionBenefitsEnrollments(BaseModel):
    employee_number: float | None = None
    position_id: str | None = None
    plan_type: str | None = None
    plan_name: str | None = None
    coverage_level: str | None = None
    effective_date: str | None = None


ASSET_SCHEMA = {
    "additional_earnings_report": json.loads(
        py_avro_schema.generate(
            py_type=AdditionalEarnings, namespace="additional_earnings_report"
        )
    ),
    "comprehensive_benefits_report": json.loads(
        py_avro_schema.generate(
            py_type=ComprehensiveBenefits, namespace="comprehensive_benefits_report"
        )
    ),
    "pension_and_benefits_enrollments": json.loads(
        py_avro_schema.generate(
            py_type=PensionBenefitsEnrollments,
            namespace="pension_and_benefits_enrollments",
        )
    ),
}
