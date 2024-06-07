from pydantic import BaseModel


class AccrualReportingPeriodSummary(BaseModel):
    employee_name_id: str | None = None
    accrual_code: str | None = None
    accrual_reporting_period: str | None = None
    accrual_opening_vested_balance_hours: float | None = None
    accrual_earned_to_date_hours: float | None = None
    accrual_taken_to_date_hours: float | None = None
    accrual_available_balance_hours: float | None = None
    accrual_planned_takings_hours: float | None = None
    accrual_pending_grants_hours: float | None = None
    accrual_ending_vested_balance_hours: float | None = None


class TimeDetail(BaseModel):
    days: float | None = None
    employee_name: str | None = None
    employee_payrule: str | None = None
    hours: float | None = None
    job: str | None = None
    location: str | None = None
    money: float | None = None
    transaction_apply_date: str | None = None
    transaction_apply_to: str | None = None
    transaction_end_date_time: str | None = None
    transaction_in_exceptions: str | None = None
    transaction_out_exceptions: str | None = None
    transaction_type: str | None = None
    transaction_start_date_time: str | None = None
