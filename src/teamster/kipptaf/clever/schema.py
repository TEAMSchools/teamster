CORE_FIELDS = [
    {"name": "sis_id", "type": ["null", "string", "long"], "default": None},
    {"name": "clever_user_id", "type": ["null", "string"], "default": None},
    {"name": "clever_school_id", "type": ["null", "string"], "default": None},
    {"name": "school_name", "type": ["null", "string"], "default": None},
    {"name": "staff_id", "type": ["null", "string"], "default": None},
    {
        "name": "date",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "date",
    },
]

RESOURCE_USAGE_FIELDS = [
    *CORE_FIELDS,
    {"name": "resource_type", "type": ["null", "string"], "default": None},
    {"name": "resource_name", "type": ["null", "string"], "default": None},
    {"name": "resource_id", "type": ["null", "string"], "default": None},
    {"name": "num_access", "type": ["null", "long"], "default": None},
]

DAILY_PARTICIPATION_FIELDS = [
    *CORE_FIELDS,
    {"name": "active", "type": ["null", "boolean"], "default": None},
    {"name": "num_logins", "type": ["null", "long"], "default": None},
    {"name": "num_resources_accessed", "type": ["null", "long"], "default": None},
]

ASSET_FIELDS = {
    "daily_participation": DAILY_PARTICIPATION_FIELDS,
    "resource_usage": RESOURCE_USAGE_FIELDS,
}
