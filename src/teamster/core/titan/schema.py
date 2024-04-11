PERSON_DATA_FIELDS = [
    {"name": "eligibility_benefit_type", "type": ["null", "string"], "default": None},
    {"name": "eligibility_end_date", "type": ["null", "string"], "default": None},
    {"name": "eligibility_start_date", "type": ["null", "string"], "default": None},
    {"name": "eligibility", "type": ["null", "long", "string"], "default": None},
    {"name": "is_directly_certified", "type": ["null", "boolean"], "default": None},
    {"name": "person_identifier", "type": ["null", "long"], "default": None},
    {"name": "total_balance", "type": ["null", "string", "double"], "default": None},
    {
        "name": "total_positive_balance",
        "type": ["null", "string", "double"],
        "default": None,
    },
    {
        "name": "application_academic_school_year",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "application_approved_benefit_type",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "eligibility_determination_reason",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "total_negative_balance",
        "type": ["null", "string", "double"],
        "default": None,
    },
]

INCOME_FORM_DATA_FIELDS = [
    {"name": "student_identifier", "type": ["null", "long"], "default": None},
    {"name": "eligibility_result", "type": ["null", "long", "string"], "default": None},
    {"name": "academic_year", "type": ["null", "string"], "default": None},
    {"name": "reference_code", "type": ["null", "string"], "default": None},
    {"name": "date_signed", "type": ["null", "string"], "default": None},
]

ASSET_FIELDS = {
    "person_data": PERSON_DATA_FIELDS,
    "income_form_data": INCOME_FORM_DATA_FIELDS,
}
