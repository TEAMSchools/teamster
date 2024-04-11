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
    "accrual_reporting_period_summary": ACCRUAL_REPORTING_PERIOD_SUMMARY_FIELDS,
    "time_details": TIME_DETAIL_FIELDS,
}
