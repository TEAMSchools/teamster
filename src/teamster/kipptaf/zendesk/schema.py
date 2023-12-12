from teamster.core.utils.functions import get_avro_record_schema

MINUTE_FIELDS = [
    {"name": "calendar", "type": ["null", "long"], "default": None},
    {"name": "business", "type": ["null", "long"], "default": None},
]

TICKET_METRIC_FIELDS = [
    {"name": "id", "type": ["null", "long"], "default": None},
    {"name": "ticket_id", "type": ["null", "long"], "default": None},
    {"name": "assignee_stations", "type": ["null", "long"], "default": None},
    {"name": "group_stations", "type": ["null", "long"], "default": None},
    {"name": "reopens", "type": ["null", "long"], "default": None},
    {"name": "replies", "type": ["null", "long"], "default": None},
    {"name": "url", "type": ["null", "string"], "default": None},
    {
        "name": "assignee_updated_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "assigned_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "created_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "initially_assigned_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "latest_comment_added_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "requester_updated_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "solved_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "status_updated_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "updated_at",
        "type": ["null", "string"],
        "logicalType": "timestamp",
        "default": None,
    },
    {
        "name": "agent_wait_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="agent_wait_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
    {
        "name": "first_resolution_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="first_resolution_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
    {
        "name": "full_resolution_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="full_resolution_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
    {
        "name": "on_hold_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="on_hold_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
    {
        "name": "reply_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="reply_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
    {
        "name": "requester_wait_time_in_minutes",
        "type": [
            "null",
            get_avro_record_schema(
                name="requester_wait_time_in_minutes",
                fields=MINUTE_FIELDS,
                namespace="ticket_metric",
            ),
        ],
        "default": None,
    },
]

ASSET_FIELDS = {
    "ticket_metrics": TICKET_METRIC_FIELDS,
}
