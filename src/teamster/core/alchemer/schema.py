SURVEY_FIELDS = [
    {"name": "created_on", "type": ["null", "string"], "default": None},  # logicalType
    {"name": "forward_only", "type": ["null", "boolean"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "internal_title", "type": ["null", "string"], "default": None},
    {"name": "languages", "type": ["null", "string"], "default": None},
    {"name": "links", "type": ["null", "string"], "default": None},
    {"name": "modified_on", "type": ["null", "string"], "default": None},  # logicalType
    {"name": "statistics", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "theme", "type": ["null", "string"], "default": None},
    {"name": "title_ml", "type": ["null", "string"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    # {"name": "team", "type": ["null", "record"], "default": None},
    # {"name": "team[id]", "type": ["null", "string"], "default": None},
    # {"name": "team[name]", "type": ["null", "string"], "default": None},
    {"name": "blockby", "type": ["null", "array"], "default": None},
    {"name": "pages", "type": ["null", "array"], "default": None},
]

ENDPOINT_FIELDS = {"survey": SURVEY_FIELDS}
