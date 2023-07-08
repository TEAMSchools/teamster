ADDITIONAL_EARNING_FIELDS = [
    {"name": "additional_earnings_code", "type": ["null", "string"], "default": None},
    {"name": "check_voucher_number", "type": ["null", "string"], "default": None},
    {"name": "cost_number_description", "type": ["null", "string"], "default": None},
    {"name": "cost_number", "type": ["null", "string"], "default": None},
    {"name": "employee_number", "type": ["null", "double"], "default": None},
    {"name": "file_number_pay_statements", "type": ["null", "long"], "default": None},
    {"name": "gross_pay", "type": ["null", "string"], "default": None},
    {"name": "pay_date", "type": ["null", "string"], "default": None},
    {"name": "payroll_company_code", "type": ["null", "string"], "default": None},
    {"name": "position_status", "type": ["null", "string"], "default": None},
    {
        "name": "additional_earnings_description",
        "type": ["null", "string"],
        "default": None,
    },
]

COMPREHENSIVE_BENEFIT_FIELDS = [
    {"name": "position_id", "type": ["null", "string"], "default": None},
    {"name": "plan_type", "type": ["null", "string"], "default": None},
    {"name": "plan_name", "type": ["null", "string"], "default": None},
    {"name": "coverage_level", "type": ["null", "string"], "default": None},
]

PENSION_BENEFIT_FIELDS = [
    {"name": "employee_number", "type": ["null", "double"], "default": None},
    {"name": "position_id", "type": ["null", "string"], "default": None},
    {"name": "plan_type", "type": ["null", "string"], "default": None},
    {"name": "plan_name", "type": ["null", "string"], "default": None},
    {"name": "coverage_level", "type": ["null", "string"], "default": None},
    {"name": "effective_date", "type": ["null", "string"], "default": None},
]

ACCRUAL_REPORTING_PERIOD_SUMMARY_FIELDS = [
    {"name": "employee_name_id", "type": ["null", "string"], "default": None},
    {"name": "accrual_code", "type": ["null", "string"], "default": None},
    {"name": "accrual_reporting_period", "type": ["null", "string"], "default": None},
    {
        "name": "accrual_opening_vested_balance_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_earned_to_date_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_taken_to_date_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_available_balance_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_planned_takings_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_pending_grants_hours",
        "type": ["null", "double"],
        "default": None,
    },
    {
        "name": "accrual_ending_vested_balance_hours",
        "type": ["null", "double"],
        "default": None,
    },
]

TIME_DETAIL_FIELDS = [
    {"name": "days", "type": ["null", "double"], "default": None},
    {"name": "employee_name", "type": ["null", "string"], "default": None},
    {"name": "employee_payrule", "type": ["null", "string"], "default": None},
    {"name": "hours", "type": ["null", "double"], "default": None},
    {"name": "job", "type": ["null", "string"], "default": None},
    {"name": "location", "type": ["null", "string"], "default": None},
    {"name": "money", "type": ["null", "double"], "default": None},
    {"name": "transaction_apply_date", "type": ["null", "string"], "default": None},
    {"name": "transaction_apply_to", "type": ["null", "string"], "default": None},
    {"name": "transaction_end_date_time", "type": ["null", "string"], "default": None},
    {"name": "transaction_in_exceptions", "type": ["null", "string"], "default": None},
    {"name": "transaction_out_exceptions", "type": ["null", "string"], "default": None},
    {"name": "transaction_type", "type": ["null", "string"], "default": None},
    {
        "name": "transaction_start_date_time",
        "type": ["null", "string"],
        "default": None,
    },
]

ASSET_FIELDS = {
    "additional_earnings_report": ADDITIONAL_EARNING_FIELDS,
    "comprehensive_benefits_report": COMPREHENSIVE_BENEFIT_FIELDS,
    "pension_and_benefits_enrollments": PENSION_BENEFIT_FIELDS,
    "AccrualReportingPeriodSummary": ACCRUAL_REPORTING_PERIOD_SUMMARY_FIELDS,
    "TimeDetails": TIME_DETAIL_FIELDS,
}
