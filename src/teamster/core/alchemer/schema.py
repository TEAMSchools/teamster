from teamster.core.utils.functions import get_avro_record_schema

ATOM_FIELDS = [
    {"name": "type", "type": ["null", "string"], "default": None},
    {
        "name": "value",
        "type": ["null", "string", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

SHOW_RULE_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "operator", "type": ["null", "string"], "default": None},
    {
        "name": "same_page_skus",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

SURVEY_OPTION_PROPERTY_FIELDS = [
    {"name": "all", "type": ["null", "boolean"], "default": None},
    {"name": "checked", "type": ["null", "boolean"], "default": None},
    {"name": "dependent", "type": ["null", "string"], "default": None},
    {"name": "disabled", "type": ["null", "boolean"], "default": None},
    {"name": "fixed", "type": ["null", "boolean"], "default": None},
    {"name": "na", "type": ["null", "boolean"], "default": None},
    {"name": "none", "type": ["null", "boolean"], "default": None},
    {"name": "other", "type": ["null", "boolean"], "default": None},
    {"name": "otherrequired", "type": ["null", "boolean"], "default": None},
    {"name": "requireother", "type": ["null", "boolean"], "default": None},
    {"name": "piping_exclude", "type": ["null", "string"], "default": None},
    {"name": "show_rules_logic_map", "type": ["null", "string"], "default": None},
    {
        "name": "left-label",
        "type": ["null", {"type": "map", "values": ["null", "string"], "default": {}}],
        "default": None,
    },
    {
        "name": "right-label",
        "type": ["null", {"type": "map", "values": ["null", "string"], "default": {}}],
        "default": None,
    },
]

SURVEY_OPTION_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
    {
        "name": "title",
        "type": ["null", {"type": "map", "values": ["string", "int"], "default": {}}],
        "default": None,
    },
]

SURVEY_QUESTION_PROPERTY_FIELDS = [
    {"name": "break_after", "type": ["null", "boolean"], "default": None},
    {"name": "custom_css", "type": ["null", "string"], "default": None},
    {"name": "data_json", "type": ["null", "boolean"], "default": None},
    {"name": "data_type", "type": ["null", "string"], "default": None},
    {"name": "disabled", "type": ["null", "boolean"], "default": None},
    {"name": "element_style", "type": ["null", "string"], "default": None},
    {"name": "exclude_number", "type": ["null", "string"], "default": None},
    {"name": "extentions", "type": ["null", "string"], "default": None},
    {"name": "force_currency", "type": ["null", "boolean"], "default": None},
    {"name": "force_int", "type": ["null", "boolean"], "default": None},
    {"name": "force_numeric", "type": ["null", "boolean"], "default": None},
    {"name": "force_percent", "type": ["null", "boolean"], "default": None},
    {"name": "hidden", "type": ["null", "boolean"], "default": None},
    {"name": "hide_after_response", "type": ["null", "boolean"], "default": None},
    {"name": "labels_right", "type": ["null", "boolean"], "default": None},
    {"name": "map_key", "type": ["null", "string"], "default": None},
    {"name": "max_number", "type": ["null", "string"], "default": None},
    {"name": "maxfiles", "type": ["null", "string"], "default": None},
    {"name": "min_answers_per_row", "type": ["null", "string"], "default": None},
    {"name": "min_number", "type": ["null", "string"], "default": None},
    {"name": "minimum_response", "type": ["null", "int"], "default": None},
    {"name": "only_whole_num", "type": ["null", "boolean"], "default": None},
    {"name": "option_sort", "type": ["null", "string"], "default": None},
    {"name": "orientation", "type": ["null", "string"], "default": None},
    {"name": "required", "type": ["null", "boolean"], "default": None},
    {"name": "show_title", "type": ["null", "boolean"], "default": None},
    {"name": "sizelimit", "type": ["null", "int"], "default": None},
    {"name": "soft-required", "type": ["null", "boolean"], "default": None},
    {"name": "sub_questions", "type": ["null", "int"], "default": None},
    {"name": "subtype", "type": ["null", "string"], "default": None},
    {"name": "url", "type": ["null", "string"], "default": None},
    {
        "name": "question_description_above",
        "type": ["null", "boolean"],
        "default": None,
    },
    {
        "name": "defaulttext",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "question_description",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "limits",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "placeholder",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "inputmask",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "outbound",
        "type": [
            "null",
            {
                "type": "array",
                "items": {"type": "map", "values": "string", "default": {}},
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "messages",
        "type": [
            "null",
            {
                "type": "map",
                "values": [
                    {"type": "array", "items": "string", "default": []},
                    {"type": "map", "values": "string", "default": {}},
                ],
                "default": {},
            },
        ],
        "default": None,
    },
    {
        "name": "message",
        "type": [
            "null",
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
]

SURVEY_QUESTION_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {"name": "base_type", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "shortname", "type": ["null", "string"], "default": None},
    {"name": "has_showhide_deps", "type": ["null", "boolean"], "default": None},
    {"name": "comment", "type": ["null", "boolean"], "default": None},
    {
        "name": "description",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "varname",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "title",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
]

SURVEY_PAGE_PROPERTY_FIELDS = [
    {"name": "hidden", "type": ["null", "boolean"], "default": None},
    {"name": "piped_from", "type": ["null", "string"], "default": None},
    {"name": "page-group", "type": ["null", "string"], "default": None},
]

SURVEY_TEAM_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
]

ACTION_FIELDS = [
    {"name": "jump", "type": ["null", "string"]},
    {"name": "redirect", "type": ["null", "boolean"]},
    {"name": "save_data", "type": ["null", "boolean"]},
    {"name": "complete", "type": ["null", "boolean"]},
    {"name": "disqualify", "type": ["null", "boolean"]},
]

SURVEY_CAMPAIGN_FIELDS = [
    {"name": "close_message", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "invite_id", "type": ["null", "string"], "default": None},
    {"name": "language", "type": ["null", "string"], "default": None},
    {"name": "limit_responses", "type": ["null", "string"], "default": None},
    {"name": "link_type", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "primary_theme_content", "type": ["null", "string"], "default": None},
    {"name": "primary_theme_options", "type": ["null", "string"], "default": None},
    {"name": "SSL", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "subtype", "type": ["null", "string"], "default": None},
    {"name": "token_variables", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "uri", "type": ["null", "string"], "default": None},
    {
        "name": "date_created",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "date_modified",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "link_close_date",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "link_open_date",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
]

SURVEY_DATA_ANSWER_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {"name": "option", "type": ["null", "string"], "default": None},
    {"name": "rank", "type": ["null", "string"], "default": None},
]

SURVEY_DATA_OPTIONS_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {"name": "option", "type": ["null", "string"], "default": None},
    {"name": "answer", "type": ["null", "string"], "default": None},
    {"name": "original_answer", "type": ["null", "string"], "default": None},
]


def get_atom_fields(namespace, depth=1):
    if depth > 0:
        return [
            {
                "name": "atom",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="atom",
                        fields=[
                            *ATOM_FIELDS,
                            *SHOW_RULE_FIELDS,
                            *get_atom_fields(
                                namespace=f"{namespace}.atom", depth=(depth - 1)
                            ),
                        ],
                        namespace=namespace,
                    ),
                ],
                "default": None,
            },
            {
                "name": "atom2",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="atom2",
                        fields=[
                            *ATOM_FIELDS,
                            *SHOW_RULE_FIELDS,
                            *get_atom_fields(
                                namespace=f"{namespace}.atom2", depth=(depth - 1)
                            ),
                        ],
                        namespace=namespace,
                    ),
                ],
                "default": None,
            },
        ]
    else:
        return []


def get_rule_fields(namespace):
    return [
        {
            "name": "logic",
            "type": [
                "null",
                get_avro_record_schema(
                    name="rule",
                    fields=[
                        *SHOW_RULE_FIELDS,
                        *ATOM_FIELDS,
                        *get_atom_fields(namespace=f"{namespace}.rule", depth=9),
                    ],
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
        {"name": "logic_map", "type": ["null", "string"], "default": None},
        {
            "name": "actions",
            "type": [
                "null",
                get_avro_record_schema(
                    name="action", fields=ACTION_FIELDS, namespace=namespace
                ),
            ],
            "default": None,
        },
    ]


def get_survey_question_property_fields(namespace):
    return [
        *SURVEY_QUESTION_PROPERTY_FIELDS,
        {
            "name": "show_rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="show_rule",
                    fields=[
                        *SHOW_RULE_FIELDS,
                        *ATOM_FIELDS,
                        *get_atom_fields(namespace=f"{namespace}.show_rule", depth=9),
                    ],
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
        {
            "name": "rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="rule",
                    fields=get_rule_fields(namespace=f"{namespace}.rule"),
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
    ]


def get_survey_option_property_fields(namespace):
    return [
        *SURVEY_OPTION_PROPERTY_FIELDS,
        {
            "name": "show_rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="show_rule",
                    fields=[
                        *SHOW_RULE_FIELDS,
                        *ATOM_FIELDS,
                        *get_atom_fields(namespace=f"{namespace}.show_rule", depth=8),
                    ],
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
    ]


def get_survey_option_fields(namespace):
    return [
        *SURVEY_OPTION_FIELDS,
        {
            "name": "properties",
            "type": [
                "null",
                get_avro_record_schema(
                    name="property",
                    fields=get_survey_option_property_fields(
                        namespace=f"{namespace}.property"
                    ),
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
    ]


def get_survey_question_fields(namespace, depth=1):
    if depth > 0:
        return [
            *SURVEY_QUESTION_FIELDS,
            {
                "name": "properties",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="property",
                        fields=get_survey_question_property_fields(
                            namespace=f"{namespace}.property"
                        ),
                        namespace=namespace,
                    ),
                ],
                "default": None,
            },
            {
                "name": "options",
                "type": [
                    "null",
                    {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="option",
                            fields=get_survey_option_fields(
                                namespace=f"{namespace}.option"
                            ),
                            namespace=namespace,
                        ),
                        "default": [],
                    },
                ],
                "default": None,
            },
            {
                "name": "sub_questions",
                "type": [
                    "null",
                    {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="question",
                            fields=get_survey_question_fields(
                                namespace=f"{namespace}.sub_question",
                                depth=(depth - 1),
                            ),
                            namespace=namespace,
                        ),
                        "default": [],
                    },
                ],
                "default": None,
            },
        ]
    else:
        return []


SURVEY_PAGE_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {
        "name": "title",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "description",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "properties",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            get_avro_record_schema(
                name="property",
                fields=SURVEY_PAGE_PROPERTY_FIELDS,
                namespace="survey.page",
            ),
        ],
        "default": None,
    },
    {
        "name": "questions",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="question",
                    fields=get_survey_question_fields(
                        namespace="survey.page.question", depth=2
                    ),
                    namespace="survey.page",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

SURVEY_FIELDS = [
    {"name": "auto_close", "type": ["null", "string"], "default": None},
    {"name": "blockby", "type": ["null", "string"], "default": None},
    {"name": "forward_only", "type": ["null", "boolean"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "internal_title", "type": ["null", "string"], "default": None},
    {"name": "overall_quota", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "theme", "type": ["null", "string"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {
        "name": "created_on",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "modified_on",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "languages",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "statistics",
        "type": ["null", {"type": "map", "values": ["string", "int"], "default": {}}],
        "default": None,
    },
    {
        "name": "title_ml",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "links",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "team",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="team", fields=SURVEY_TEAM_FIELDS),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "pages",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="page", fields=SURVEY_PAGE_FIELDS, namespace="survey"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]


def get_survey_data_fields(namespace, depth=1):
    if depth > 0:
        return [
            {"name": "id", "type": ["null", "int"], "default": None},
            {"name": "type", "type": ["null", "string"], "default": None},
            {"name": "parent", "type": ["null", "int"], "default": None},
            {"name": "question", "type": ["null", "string"], "default": None},
            {"name": "section_id", "type": ["null", "int"], "default": None},
            {"name": "original_answer", "type": ["null", "string"], "default": None},
            {"name": "answer_id", "type": ["null", "int", "string"], "default": None},
            {"name": "shown", "type": ["null", "boolean"], "default": None},
            {
                "name": "answer",
                "type": [
                    "null",
                    "string",
                    {
                        "type": "map",
                        "values": [
                            "string",
                            get_avro_record_schema(
                                name="answer",
                                fields=SURVEY_DATA_ANSWER_FIELDS,
                                namespace=namespace,
                            ),
                        ],
                        "default": {},
                    },
                ],
                "default": None,
            },
            {
                "name": "options",
                "type": [
                    "null",
                    {
                        "type": "map",
                        "values": get_avro_record_schema(
                            name="option",
                            fields=SURVEY_DATA_OPTIONS_FIELDS,
                            namespace=namespace,
                        ),
                        "default": {},
                    },
                ],
                "default": None,
            },
            {
                "name": "subquestions",
                "type": [
                    "null",
                    {
                        "type": "map",
                        "values": [
                            get_avro_record_schema(
                                name="subquestion",
                                fields=get_survey_data_fields(
                                    namespace=f"{namespace}.subquestion",
                                    depth=(depth - 1),
                                ),
                                namespace=namespace,
                            ),
                            {
                                "type": "map",
                                "values": get_avro_record_schema(
                                    name="subquestion_map",
                                    fields=get_survey_data_fields(
                                        namespace=f"{namespace}.subquestion_map",
                                        depth=(depth - 1),
                                    ),
                                    namespace=namespace,
                                ),
                                "default": {},
                            },
                        ],
                        "default": {},
                    },
                ],
                "default": None,
            },
        ]
    else:
        return []


SURVEY_RESPONSE_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "contact_id", "type": ["null", "string"], "default": None},
    {"name": "is_test_data", "type": ["null", "string"], "default": None},
    {"name": "session_id", "type": ["null", "string"], "default": None},
    {"name": "language", "type": ["null", "string"], "default": None},
    {"name": "link_id", "type": ["null", "string"], "default": None},
    {"name": "ip_address", "type": ["null", "string"], "default": None},
    {"name": "referer", "type": ["null", "string"], "default": None},
    {"name": "user_agent", "type": ["null", "string"], "default": None},
    {"name": "response_time", "type": ["null", "int"], "default": None},
    {"name": "comments", "type": ["null", "string"], "default": None},
    {"name": "longitude", "type": ["null", "string"], "default": None},
    {"name": "latitude", "type": ["null", "string"], "default": None},
    {"name": "country", "type": ["null", "string"], "default": None},
    {"name": "city", "type": ["null", "string"], "default": None},
    {"name": "region", "type": ["null", "string"], "default": None},
    {"name": "postal", "type": ["null", "string"], "default": None},
    {"name": "dma", "type": ["null", "string"], "default": None},
    {
        "name": "date_submitted",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "date_started",
        "type": ["null", "string"],
        "default": None,
        "logicalType": "timestamp-micros",
    },
    {
        "name": "url_variables",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {
                "type": "map",
                "values": ["string", {"type": "map", "values": "string"}],
                "default": {},
            },
        ],
        "default": None,
    },
    {
        "name": "survey_data",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {
                "type": "map",
                "values": get_avro_record_schema(
                    name="survey_data",
                    fields=get_survey_data_fields(namespace="surveyresponse", depth=2),
                ),
                "default": {},
            },
        ],
        "default": None,
    },
    {
        "name": "data_quality",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {
                "type": "map",
                "values": [
                    "null",
                    {"type": "array", "items": "string", "default": []},
                    {
                        "type": "map",
                        "values": [
                            "int",
                            {"type": "array", "items": "string", "default": []},
                            {
                                "type": "map",
                                "values": [
                                    "int",
                                    {"type": "array", "items": "string", "default": []},
                                ],
                                "default": {},
                            },
                        ],
                        "default": {},
                    },
                ],
                "default": {},
            }
            # get_avro_record_schema(name="data_quality", fields=DATA_QUALITY_FIELDS),
        ],
        "default": None,
    },
]

ENDPOINT_FIELDS = {
    "survey": SURVEY_FIELDS,
    "survey_campaign": SURVEY_CAMPAIGN_FIELDS,
    "survey_response": SURVEY_RESPONSE_FIELDS,
    "survey_question": get_survey_question_fields(namespace="surveyquestion", depth=2),
}
