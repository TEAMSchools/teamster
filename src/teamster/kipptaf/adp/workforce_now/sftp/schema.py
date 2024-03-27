ADDITIONAL_EARNING_FIELDS = [
    {"name": "additional_earnings_code", "type": ["null", "string"], "default": None},
    {
        "name": "check_voucher_number",
        "type": ["null", "string", "long"],
        "default": None,
    },
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

ASSET_FIELDS = {
    "additional_earnings_report": ADDITIONAL_EARNING_FIELDS,
    "comprehensive_benefits_report": COMPREHENSIVE_BENEFIT_FIELDS,
    "pension_and_benefits_enrollments": PENSION_BENEFIT_FIELDS,
}
