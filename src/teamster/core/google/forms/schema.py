from teamster.core.utils.functions import get_avro_record_schema

INFO_FIELDS = [
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "documentTitle", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
]

QUIZ_SETTING_FIELDS = [
    {"name": "isQuiz", "type": ["null", "boolean"], "default": None},
]

FORM_SETTING_FIELDS = [
    {
        "name": "quizSettings",
        "type": [
            "null",
            get_avro_record_schema(
                name="quiz_settings",
                fields=QUIZ_SETTING_FIELDS,
                namespace="form_setting.quiz_settings",
            ),
        ],
        "default": None,
    }
]

MEDIA_PROPERTY_FIELDS = [
    {"name": "width", "type": ["null", "long"], "default": None},
    {
        "name": "alignment",
        "type": [
            "null",
            {
                "name": "alignment_enum",
                "type": "enum",
                "symbols": ["ALIGNMENT_UNSPECIFIED", "LEFT", "RIGHT", "CENTER"],
            },
        ],
        "default": None,
    },
]


def get_image_fields(namespace):
    return [
        {"name": "contentUri", "type": ["null", "string"], "default": None},
        {"name": "altText", "type": ["null", "string"], "default": None},
        {"name": "sourceUri", "type": ["null", "string"], "default": None},
        {
            "name": "properties",
            "type": [
                "null",
                get_avro_record_schema(
                    name="media_properties",
                    fields=MEDIA_PROPERTY_FIELDS,
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
    ]


def get_option_fields(namespace):
    return [
        {"name": "value", "type": ["null", "string"], "default": None},
        {"name": "isOther", "type": ["null", "boolean"], "default": None},
        {"name": "goToSectionId", "type": ["null", "string"], "default": None},
        {
            "name": "goToAction",
            "type": [
                "null",
                {
                    "name": "go_to_action_enum",
                    "type": "enum",
                    "symbols": [
                        "GO_TO_ACTION_UNSPECIFIED",
                        "NEXT_SECTION",
                        "RESTART_FORM",
                        "SUBMIT_FORM",
                    ],
                },
            ],
            "default": None,
        },
        {
            "name": "image",
            "type": [
                "null",
                get_avro_record_schema(
                    name="image",
                    fields=get_image_fields(namespace=f"{namespace}.option.image"),
                    namespace=f"{namespace}.option.image",
                ),
            ],
            "default": None,
        },
    ]


def get_choice_question_fields(namespace):
    return [
        {"name": "shuffle", "type": ["null", "boolean"], "default": None},
        {
            "name": "type",
            "type": [
                "null",
                {
                    "name": "choice_question_type_enum",
                    "type": "enum",
                    "symbols": [
                        "CHOICE_TYPE_UNSPECIFIED",
                        "RADIO",
                        "CHECKBOX",
                        "DROP_DOWN",
                    ],
                },
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
                        fields=get_option_fields(
                            f"{namespace}.choice_question.options"
                        ),
                        namespace=f"{namespace}.choice_question.options",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
    ]


TEXT_QUESTION_FIELDS = [
    {"name": "paragraph", "type": ["null", "boolean"], "default": None},
]

SCALE_QUESTION_FIELDS = [
    {"name": "low", "type": ["null", "long"], "default": None},
    {"name": "high", "type": ["null", "long"], "default": None},
    {"name": "lowLabel", "type": ["null", "string"], "default": None},
    {"name": "highLabel", "type": ["null", "string"], "default": None},
]

DATE_QUESTION_FIELDS = [
    {"name": "includeTime", "type": ["null", "boolean"], "default": None},
    {"name": "includeYear", "type": ["null", "boolean"], "default": None},
]

TIME_QUESTION_FIELDS = [
    {"name": "duration", "type": ["null", "boolean"], "default": None},
]

FILE_UPLOAD_QUESTION_FIELDS = [
    {"name": "folderId", "type": ["null", "string"], "default": None},
    {"name": "maxFiles", "type": ["null", "long"], "default": None},
    {"name": "maxFileSize", "type": ["null", "string"], "default": None},
    {
        "name": "types",
        "type": [
            "null",
            {
                "type": "array",
                "items": {
                    "name": "file_upload_question_type_enum",
                    "type": "enum",
                    "symbols": [
                        "FILE_TYPE_UNSPECIFIED",
                        "ANY",
                        "DOCUMENT",
                        "PRESENTATION",
                        "SPREADSHEET",
                        "DRAWING",
                        "PDF",
                        "IMAGE",
                        "VIDEO",
                        "AUDIO",
                    ],
                },
                "default": [],
            },
        ],
        "default": None,
    },
]

ROW_QUESTION_FIELDS = [
    {"name": "title", "type": ["null", "string"], "default": None},
]

TEXT_LINK_FIELDS = [
    {"name": "uri", "type": ["null", "string"], "default": None},
    {"name": "displayText", "type": ["null", "string"], "default": None},
]

VIDEO_LINK_FIELDS = [
    {"name": "displayText", "type": ["null", "string"], "default": None},
    {"name": "youtubeUri", "type": ["null", "string"], "default": None},
]


def get_extra_material_fields(namespace):
    return [
        {
            "name": "link",
            "type": [
                "null",
                get_avro_record_schema(
                    name="text_link", fields=TEXT_LINK_FIELDS, namespace=namespace
                ),
            ],
            "default": None,
        },
        {
            "name": "video",
            "type": [
                "null",
                get_avro_record_schema(
                    name="video_link", fields=VIDEO_LINK_FIELDS, namespace=namespace
                ),
            ],
            "default": None,
        },
    ]


def get_feedback_fields(namespace):
    return [
        {"name": "text", "type": ["null", "string"], "default": None},
        {
            "name": "material",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="extra_material",
                        fields=get_extra_material_fields(namespace=namespace),
                        namespace=namespace,
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
    ]


ANSWER_FIELDS = [
    {"name": "value", "type": ["null", "string"], "default": None},
]


def get_correct_answers_fields(namespace):
    return [
        {
            "name": "answers",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="answer",
                        fields=ANSWER_FIELDS,
                        namespace=f"{namespace}.correct_answers.answers",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        }
    ]


def get_grading_fields(namespace):
    return [
        {"name": "pointValue", "type": ["null", "long"], "default": None},
        {
            "name": "correctAnswers",
            "type": [
                "null",
                get_avro_record_schema(
                    name="correct_answers",
                    fields=get_correct_answers_fields(
                        namespace=f"{namespace}.grading.correct_answers"
                    ),
                    namespace=f"{namespace}.grading.correct_answers",
                ),
            ],
            "default": None,
        },
        {
            "name": "whenRight",
            "type": [
                "null",
                get_avro_record_schema(
                    name="when_right",
                    fields=get_feedback_fields(
                        namespace=f"{namespace}.grading.when_right"
                    ),
                    namespace=f"{namespace}.grading.when_right",
                ),
            ],
            "default": None,
        },
        {
            "name": "whenWrong",
            "type": [
                "null",
                get_avro_record_schema(
                    name="when_wrong",
                    fields=get_feedback_fields(
                        namespace=f"{namespace}.grading.when_wrong"
                    ),
                    namespace=f"{namespace}.grading.when_wrong",
                ),
            ],
            "default": None,
        },
        {
            "name": "generalFeedback",
            "type": [
                "null",
                get_avro_record_schema(
                    name="general_feedback",
                    fields=get_feedback_fields(
                        namespace=f"{namespace}.grading.general_feedback"
                    ),
                    namespace=f"{namespace}.grading.general_feedback",
                ),
            ],
            "default": None,
        },
    ]


def get_question_fields(namespace):
    return [
        {"name": "questionId", "type": ["null", "string"], "default": None},
        {"name": "required", "type": ["null", "boolean"], "default": None},
        {
            "name": "grading",
            "type": [
                "null",
                get_avro_record_schema(
                    name="grading",
                    fields=get_grading_fields(
                        namespace=f"{namespace}.question.grading"
                    ),
                    namespace=f"{namespace}.question.grading",
                ),
            ],
            "default": None,
        },
        {
            "name": "choiceQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="choice_question",
                    fields=get_choice_question_fields(
                        namespace=f"{namespace}.question.choice_question"
                    ),
                    namespace=f"{namespace}.question.choice_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "textQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="text_question",
                    fields=TEXT_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.text_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "scaleQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="scale_question",
                    fields=SCALE_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.scale_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "dateQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="date_question",
                    fields=DATE_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.date_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "timeQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="time_question",
                    fields=TIME_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.time_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "fileUploadQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="file_upload_question",
                    fields=FILE_UPLOAD_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.file_upload_question",
                ),
            ],
            "default": None,
        },
        {
            "name": "rowQuestion",
            "type": [
                "null",
                get_avro_record_schema(
                    name="row_question",
                    fields=ROW_QUESTION_FIELDS,
                    namespace=f"{namespace}.question.row_question",
                ),
            ],
            "default": None,
        },
    ]


QUESTION_ITEM_FIELDS = [
    {
        "name": "question",
        "type": [
            "null",
            get_avro_record_schema(
                name="row_question",
                fields=get_question_fields(namespace="question_item.question"),
                namespace="question_item.question",
            ),
        ],
        "default": None,
    },
    {
        "name": "image",
        "type": [
            "null",
            get_avro_record_schema(
                name="image",
                fields=get_image_fields(namespace="question_item.image"),
                namespace="question_item.image",
            ),
        ],
        "default": None,
    },
]

GRID_FIELDS = [
    {"name": "shuffleQuestions", "type": ["null", "boolean"], "default": None},
    {
        "name": "columns",
        "type": [
            "null",
            get_avro_record_schema(
                name="choice_question",
                fields=get_choice_question_fields(namespace="grid.columns"),
                namespace="grid.columns",
            ),
        ],
        "default": None,
    },
]

QUESTION_GROUP_ITEM_FIELDS = [
    {
        "name": "image",
        "type": [
            "null",
            get_avro_record_schema(
                name="image",
                fields=get_image_fields(namespace="question_group_item.image"),
                namespace="question_group_item.image",
            ),
        ],
        "default": None,
    },
    {
        "name": "grid",
        "type": [
            "null",
            get_avro_record_schema(
                name="grid", fields=GRID_FIELDS, namespace="question_group_item.grid"
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
                    fields=get_question_fields(
                        namespace="question_group_item.questions"
                    ),
                    namespace="question_group_item.questions",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

IMAGE_ITEM_FIELDS = [
    {
        "name": "image",
        "type": [
            "null",
            get_avro_record_schema(
                name="image",
                fields=get_image_fields(namespace="image_item.image"),
                namespace="image_item.image",
            ),
        ],
        "default": None,
    }
]

VIDEO_FIELDS = [
    {"name": "youtubeUri", "type": ["null", "string"], "default": None},
    {
        "name": "properties",
        "type": [
            "null",
            get_avro_record_schema(
                name="media_properties",
                fields=MEDIA_PROPERTY_FIELDS,
                namespace="video.properties",
            ),
        ],
        "default": None,
    },
]

VIDEO_ITEM_FIELDS = [
    {"name": "caption", "type": ["null", "string"], "default": None},
    {
        "name": "video",
        "type": [
            "null",
            get_avro_record_schema(
                name="video", fields=VIDEO_FIELDS, namespace="video_item.video"
            ),
        ],
        "default": None,
    },
]

PAGE_BREAK_ITEM_FIELDS = []

TEXT_ITEM_FIELDS = []

ITEM_FIELDS = [
    {"name": "itemId", "type": ["null", "string"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {
        "name": "questionItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="question_item",
                fields=QUESTION_ITEM_FIELDS,
                namespace="item.question_item",
            ),
        ],
        "default": None,
    },
    {
        "name": "questionGroupItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="question_group_item",
                fields=QUESTION_GROUP_ITEM_FIELDS,
                namespace="item.question_group_item",
            ),
        ],
        "default": None,
    },
    {
        "name": "pageBreakItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="page_break_item",
                fields=PAGE_BREAK_ITEM_FIELDS,
                namespace="item.page_break_item",
            ),
        ],
        "default": None,
    },
    {
        "name": "textItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="text_item",
                fields=TEXT_ITEM_FIELDS,
                namespace="item.text_item",
            ),
        ],
        "default": None,
    },
    {
        "name": "imageItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="image_item",
                fields=IMAGE_ITEM_FIELDS,
                namespace="item.image_item",
            ),
        ],
        "default": None,
    },
    {
        "name": "videoItem",
        "type": [
            "null",
            get_avro_record_schema(
                name="video_item",
                fields=VIDEO_ITEM_FIELDS,
                namespace="item.video_item",
            ),
        ],
        "default": None,
    },
]

FORM_FIELDS = [
    {"name": "formId", "type": ["null", "string"], "default": None},
    {"name": "revisionId", "type": ["null", "string"], "default": None},
    {"name": "responderUri", "type": ["null", "string"], "default": None},
    {"name": "linkedSheetId", "type": ["null", "string"], "default": None},
    {
        "name": "info",
        "type": [
            "null",
            get_avro_record_schema(
                name="info", fields=INFO_FIELDS, namespace="form.info"
            ),
        ],
        "default": None,
    },
    {
        "name": "settings",
        "type": [
            "null",
            get_avro_record_schema(
                name="settings", fields=FORM_SETTING_FIELDS, namespace="form.settings"
            ),
        ],
        "default": None,
    },
    {
        "name": "items",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="item", fields=ITEM_FIELDS, namespace="form.items"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

GRADE_FIELDS = [
    {"name": "score", "type": ["null", "double"], "default": None},
    {"name": "correct", "type": ["null", "boolean"], "default": None},
    {
        "name": "feedback",
        "type": [
            "null",
            get_avro_record_schema(
                name="feedback",
                fields=get_feedback_fields(
                    namespace="response.responses.answers.grade.feedback"
                ),
                namespace="response.responses.answers.grade.feedback",
            ),
        ],
        "default": None,
    },
]

TEXT_ANSWER_FIELDS = [
    {"name": "value", "type": ["null", "string"], "default": None},
]

TEXT_ANSWERS_FIELDS = [
    {
        "name": "answers",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="text_answer",
                    fields=TEXT_ANSWER_FIELDS,
                    namespace="response.responses.answers.text_answers.answers",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

FILE_UPLOAD_ANSWER_FIELDS = [
    {"name": "fileId", "type": ["null", "string"], "default": None},
    {"name": "fileName", "type": ["null", "string"], "default": None},
    {"name": "mimeType", "type": ["null", "string"], "default": None},
]

FILE_UPLOAD_ANSWERS_FIELDS = [
    {
        "name": "answers",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="file_upload_answer",
                    fields=FILE_UPLOAD_ANSWER_FIELDS,
                    namespace="response.responses.answers.file_upload_answers.answers",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

RESPONSE_ANSWER_FIELDS = [
    {"name": "questionId", "type": ["null", "string"], "default": None},
    {
        "name": "grade",
        "type": [
            "null",
            get_avro_record_schema(
                name="grade",
                fields=GRADE_FIELDS,
                namespace="response.responses.answers.grade",
            ),
        ],
        "default": None,
    },
    {
        "name": "textAnswers",
        "type": [
            "null",
            get_avro_record_schema(
                name="text_answers",
                fields=TEXT_ANSWERS_FIELDS,
                namespace="response.responses.answers.text_answers",
            ),
        ],
        "default": None,
    },
    {
        "name": "fileUploadAnswers",
        "type": [
            "null",
            get_avro_record_schema(
                name="file_upload_answer",
                fields=FILE_UPLOAD_ANSWERS_FIELDS,
                namespace="response.responses.answers.file_upload_answers",
            ),
        ],
        "default": None,
    },
]

FORM_RESPONSE_FIELDS = [
    {"name": "formId", "type": ["null", "string"], "default": None},
    {"name": "responseId", "type": ["null", "string"], "default": None},
    {"name": "respondentEmail", "type": ["null", "string"], "default": None},
    {"name": "totalScore", "type": ["null", "double"], "default": None},
    {
        "name": "createTime",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "lastSubmittedTime",
        "type": ["null", "string"],
        "logicalType": "timestamp-micros",
        "default": None,
    },
    {
        "name": "answers",
        "type": [
            "null",
            {
                "type": "map",
                "values": get_avro_record_schema(
                    name="answer",
                    fields=RESPONSE_ANSWER_FIELDS,
                    namespace="response.responses.answers",
                ),
                "default": {},
            },
        ],
        "default": None,
    },
]

RESPONSE_FIELDS = [
    {"name": "nextPageToken", "type": ["null", "string"], "default": None},
    {
        "name": "responses",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="form_response",
                    fields=FORM_RESPONSE_FIELDS,
                    namespace="response.responses",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

ASSET_FIELDS = {
    "form": FORM_FIELDS,
    "responses": RESPONSE_FIELDS,
}
