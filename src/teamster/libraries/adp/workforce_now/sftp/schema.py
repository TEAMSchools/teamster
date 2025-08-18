from pydantic import BaseModel


class AdditionalEarnings(BaseModel):
    additional_earnings_code: str | None = None
    additional_earnings_description: str | None = None
    check_voucher_number: str | None = None
    cost_number_description: str | None = None
    cost_number: str | None = None
    employee_number: str | None = None
    file_number_pay_statements: str | None = None
    gross_pay: str | None = None
    pay_date: str | None = None
    payroll_company_code: str | None = None
    position_status: str | None = None


class ComprehensiveBenefits(BaseModel):
    coverage_level: str | None = None
    plan_name: str | None = None
    plan_type: str | None = None
    position_id: str | None = None


class PensionBenefitsEnrollments(BaseModel):
    coverage_level: str | None = None
    effective_date: str | None = None
    employee_number: str | None = None
    enrollment_end_date: str | None = None
    enrollment_start_date: str | None = None
    enrollment_status: str | None = None
    plan_name: str | None = None
    plan_type: str | None = None
    position_id: str | None = None


class TimeAndAttendance(BaseModel):
    badge: str | None = None
    include_in_time_summary_payroll: str | None = None
    pay_class: str | None = None
    position_id: str | None = None
    supervisor_id: str | None = None
    supervisor_position: str | None = None
