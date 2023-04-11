from teamster.core.utils.functions import get_avro_record_schema

ATOM_CORE_FIELDS = [
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

SHOW_RULE_CORE_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "operator", "type": ["null", "string"], "default": None},
    {
        "name": "same_page_skus",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]


def get_atom_fields(namespace, depth=1):
    if depth > 0:
        return [
            *ATOM_CORE_FIELDS,
            *SHOW_RULE_CORE_FIELDS,
            {
                "name": "atom",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="atom",
                        fields=[
                            *ATOM_CORE_FIELDS,
                            *SHOW_RULE_CORE_FIELDS,
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
                            *ATOM_CORE_FIELDS,
                            *SHOW_RULE_CORE_FIELDS,
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


SURVEY_QUESTION_PROPERTY_SHOW_RULE_FIELDS = [
    *SHOW_RULE_CORE_FIELDS,
    *get_atom_fields(namespace="survey.page.question.property.show_rule", depth=7),
]

SURVEY_OPTION_PROPERTY_SHOW_RULE_FIELDS = [
    *SHOW_RULE_CORE_FIELDS,
    *get_atom_fields(namespace="survey.page.question.option.property.show_rule"),
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
    {"name": "piping_exclude", "type": ["null", "string"], "default": None},
    {"name": "show_rules_logic_map", "type": ["null", "string"], "default": None},
    {
        "name": "show_rules",
        "type": [
            "null",
            get_avro_record_schema(
                name="show_rule",
                fields=SURVEY_OPTION_PROPERTY_SHOW_RULE_FIELDS,
                namespace="survey.page.question.option.property",
            ),
        ],
        "default": None,
    },
]

SURVEY_OPTION_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
    {
        "name": "title",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "properties",
        "type": [
            "null",
            get_avro_record_schema(
                name="property",
                fields=SURVEY_OPTION_PROPERTY_FIELDS,
                namespace="survey.page.question.option",
            ),
        ],
        "default": None,
    },
]

MESSAGE_FIELDS = [
    {
        "name": "payment-description",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "payment_button_text",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "payment-summary",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "configurator_button_text",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "configurator_complete",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "configurator_error",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "inputmask",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "r_extreme_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "l_extreme_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "center_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "right_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "left_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "conjoint_best_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "conjoint_worst_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "conjoint_none_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "conjoint_card_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "conjoint_error_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "maxdiff_best_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "maxdiff_worst_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "maxdiff_attribute_label",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "maxdiff_sets_message",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "na_text",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "maxdiff_of",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
    {
        "name": "th_content",
        "type": [
            "null",
            {"type": "array", "items": "string", "default": []},
            {"type": "map", "values": "string", "default": {}},
        ],
        "default": None,
    },
]

SURVEY_QUESTION_PROPERTY_FIELDS = [
    {"name": "custom_css", "type": ["null", "string"], "default": None},
    {"name": "disabled", "type": ["null", "boolean"], "default": None},
    {"name": "element_style", "type": ["null", "string"], "default": None},
    {"name": "exclude_number", "type": ["null", "string"], "default": None},
    {"name": "force_currency", "type": ["null", "boolean"], "default": None},
    {"name": "force_numeric", "type": ["null", "boolean"], "default": None},
    {"name": "force_percent", "type": ["null", "boolean"], "default": None},
    {"name": "hidden", "type": ["null", "boolean"], "default": None},
    {"name": "hide_after_response", "type": ["null", "boolean"], "default": None},
    {"name": "labels_right", "type": ["null", "boolean"], "default": None},
    {"name": "limits", "type": ["null", "int"], "default": None},
    {"name": "map_key", "type": ["null", "string"], "default": None},
    {"name": "max_number", "type": ["null", "string"], "default": None},
    {"name": "min_answers_per_row", "type": ["null", "string"], "default": None},
    {"name": "min_number", "type": ["null", "string"], "default": None},
    {"name": "minimum_response", "type": ["null", "int"], "default": None},
    {"name": "only_whole_num", "type": ["null", "boolean"], "default": None},
    {"name": "option_sort", "type": ["null", "string"], "default": None},
    {"name": "orientation", "type": ["null", "string"], "default": None},
    {"name": "required", "type": ["null", "boolean"], "default": None},
    {"name": "show_title", "type": ["null", "boolean"], "default": None},
    {"name": "soft-required", "type": ["null", "boolean"], "default": None},
    {"name": "sub_questions", "type": ["null", "int"], "default": None},
    {"name": "subtype", "type": ["null", "string"], "default": None},
    {"name": "url", "type": ["null", "string"], "default": None},
    {"name": "break_after", "type": ["null", "boolean"], "default": None},
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
        "name": "placeholder",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "inputmask",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "messages",
        "type": [
            "null",
            get_avro_record_schema(
                name="message",
                fields=MESSAGE_FIELDS,
                namespace="survey.page.question.property",
            ),
        ],
        "default": None,
    },
    {
        "name": "show_rules",
        "type": [
            "null",
            get_avro_record_schema(
                name="show_rule",
                fields=SURVEY_QUESTION_PROPERTY_SHOW_RULE_FIELDS,
                namespace="survey.page.question.property",
            ),
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
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "title",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "properties",
        "type": [
            "null",
            get_avro_record_schema(
                name="property",
                fields=SURVEY_QUESTION_PROPERTY_FIELDS,
                namespace="survey.page.question",
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
                    fields=SURVEY_OPTION_FIELDS,
                    namespace="survey.page.question",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

SURVEY_PAGE_PROPERTY_FIELDS = [
    {"name": "hidden", "type": ["null", "boolean"], "default": None},
    {"name": "piped_from", "type": ["null", "string"], "default": None},
]

SURVEY_PAGE_FIELDS = [
    {"name": "id", "type": ["null", "int"], "default": None},
    {
        "name": "title",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "description",
        "type": ["null", {"type": "map", "values": "string", "default": {}}],
        "default": None,
    },
    {
        "name": "properties",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="property",
                    fields=SURVEY_PAGE_PROPERTY_FIELDS,
                    namespace="survey.page",
                ),
                "default": [],
            },
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
                    fields=SURVEY_QUESTION_FIELDS,
                    namespace="survey.page",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

TEAM_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
]

SURVEY_FIELDS = [
    {"name": "auto_close", "type": ["null"], "default": None},
    {"name": "blockby", "type": ["null", "string"], "default": None},
    {"name": "forward_only", "type": ["null", "boolean"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "internal_title", "type": ["null", "string"], "default": None},
    {"name": "overall_quota", "type": ["null"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "theme", "type": ["null", "string"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "created_on", "type": ["null", "string"], "default": None},  # logicalType
    {"name": "modified_on", "type": ["null", "string"], "default": None},  # logicalType
    {
        "name": "languages",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "statistics",
        "type": ["null", {"type": "map", "values": "int", "default": {}}],
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
                "items": get_avro_record_schema(name="team", fields=TEAM_FIELDS),
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

ENDPOINT_FIELDS = {"survey": SURVEY_FIELDS, "survey/question": SURVEY_QUESTION_FIELDS}

# # Continuous Sum
# max_total string
# must_be_max boolean
# max_total_noshow boolean

# # File Upload
# sizelimit int
# extensions string
# maxfiles string

# # URL Redirect
# url URL
# fieldname string
# mapping string
# default string
