from teamster.core.utils.functions import get_avro_record_schema

VIEW_FIELDS = [
    {"name": "content_url", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "owner_id", "type": ["null", "string"], "default": None},
    {"name": "project_id", "type": ["null", "string"], "default": None},
    {"name": "total_views", "type": ["null", "long"], "default": None},
]

WORKBOOK_FIELDS = [
    {"name": "content_url", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "owner_id", "type": ["null", "string"], "default": None},
    {"name": "project_id", "type": ["null", "string"], "default": None},
    {"name": "project_name", "type": ["null", "string"], "default": None},
    {"name": "size", "type": ["null", "long"], "default": None},
    {"name": "show_tabs", "type": ["null", "boolean"], "default": None},
    {"name": "webpage_url", "type": ["null", "string"], "default": None},
    {
        "name": "views",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="view", fields=VIEW_FIELDS, namespace="workbook"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

ASSET_FIELDS = {
    "workbook": WORKBOOK_FIELDS,
}
