import json

from py_avro_schema import generate
from pydantic import BaseModel


class AdditionalEarning(BaseModel):
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


class ComprehensiveBenefit(BaseModel):
    position_id: str | None = None
    plan_type: str | None = None
    plan_name: str | None = None
    coverage_level: str | None = None


class PensionBenefit(BaseModel):
    employee_number: float | None = None
    position_id: str | None = None
    plan_type: str | None = None
    plan_name: str | None = None
    coverage_level: str | None = None
    effective_date: str | None = None


ASSET_FIELDS = {
    "additional_earnings_report": json.loads(
        generate(py_type=AdditionalEarning, namespace="additional_earnings_report")
    ),
    "comprehensive_benefits_report": json.loads(
        generate(
            py_type=ComprehensiveBenefit, namespace="comprehensive_benefits_report"
        )
    ),
    "pension_and_benefits_enrollments": json.loads(
        generate(py_type=PensionBenefit, namespace="pension_and_benefits_enrollments")
    ),
}
