def get_avro_record_schema(name: str, fields: list):
    return {
        "type": "record",
        "name": f"{name.replace('-', '_')}_record",
        "fields": fields,
    }


GENERIC_REF_FIELDS = [
    {{"name": "_id", "type": ["string"]}, {"name": "name", "type": ["string"]}}
]

ASSIGNMENT_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "excludeFromBank", "type": ["boolean"]},
    {"name": "locked", "type": ["boolean"]},
    {"name": "private", "type": ["boolean"]},
    {"name": "coachingActivity", "type": ["boolean"]},
    {"name": "name", "type": ["string"]},
    {"name": "type", "type": ["string"]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "parent", "type": [None]},
    {"name": "grade", "type": [None]},
    {"name": "course", "type": [None]},
    {
        "name": "creator",
        "type": [get_avro_record_schema(name="creator", fields=GENERIC_REF_FIELDS)],
    },
    {
        "name": "user",
        "type": [get_avro_record_schema(name="user", fields=GENERIC_REF_FIELDS)],
    },
    {
        "name": "progress",
        "type": [
            get_avro_record_schema(
                name="progress",
                fields=[
                    {"name": "percent", "type": ["int"]},
                    {"name": "assigner", "type": [None]},
                    {"name": "justification", "type": [None]},
                    {"name": "date", "type": [None]},
                ],
            ),
        ],
    },
    {
        "name": "tags",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="tag",
                    fields=[
                        {
                            {"name": "_id", "type": ["string"]},
                            {"name": "name", "type": ["string"]},
                            {"name": "url", "type": ["string"]},
                        }
                    ],
                ),
            }
        ],
    },
]

GENERIC_TAG_TYPE_FIELDS = [
    {"name": "showOnDash", "type": ["boolean"]},
    {"name": "_id", "type": ["string"]},
    {"name": "abbreviation", "type": ["string"]},
    {"name": "color", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "order", "type": ["int"]},
    {"name": "district", "type": ["string"]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "parent", "type": [None]},
    {"name": "creator", "type": [None]},
    {"name": "tags", "type": [{"type": "array", "items": None}]},
]

INFORMAL_FIELDS = [
    {"name": "shared", "type": ["string"]},
    {"name": "private", "type": ["string"]},
    {"name": "user", "type": ["string"]},
    {"name": "creator", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "_id", "type": ["string"]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "tags", "type": [{"type": "array", "items": "string"}]},
]

MEASUREMENT_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "sortId", "type": ["string"]},
    {"name": "description", "type": ["string"]},
    {"name": "isPercentage", "type": ["boolean"]},
    {"name": "district", "type": ["string"]},
    {"name": "scaleMin", "type": ["int"]},
    {"name": "scaleMax", "type": ["int"]},
    {"name": "rowStyle", "type": ["string"]},
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "measurementType", "type": [None]},
    {"name": "textBoxes", "type": [{"type": "array", "items": "string"}]},
    {"name": "measurementGroups", "type": [{"type": "array", "items": "None"}]},
    {
        "name": "measurementOptions",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement_options",
                    fields=[
                        {"name": "_id", "type": "string"},
                        {"name": "value", "type": "int"},
                        {"name": "label", "type": "string"},
                        {"name": "description", "type": "string"},
                        {"name": "percentage", "type": "int"},
                        {
                            "name": "created",
                            "type": {
                                "type": "string",
                                "logicalType": "timestamp-millis",
                            },
                        },
                    ],
                ),
            }
        ],
    },
]

MEETING_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "locked", "type": ["boolean"]},
    {"name": "private", "type": ["boolean"]},
    {"name": "signatureRequired", "type": ["boolean"]},
    {"name": "title", "type": ["string"]},
    {"name": "type", "type": ["string"]},
    {"name": "creator", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "date", "type": [{"type": "string", "logicalType": "timestamp-millis"}]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "grade", "type": [None]},
    {"name": "school", "type": [None]},
    {"name": "course", "type": [None]},
    {"name": "observations", "type": [{"type": "array", "items": "string"}]},
    {"name": "actionSteps", "type": [{"type": "array", "items": "None"}]},
    {"name": "onleave", "type": [{"type": "array", "items": "None"}]},
    {"name": "offweek", "type": [{"type": "array", "items": "None"}]},
    {"name": "unable", "type": [{"type": "array", "items": "None"}]},
    {"name": "additionalFields", "type": [{"type": "array", "items": "None"}]},
    {"name": "participants", "type": [{"type": "array", "items": "None"}]},
]

OBSERVATION_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "isPublished", "type": ["boolean"]},
    {"name": "sendEmail", "type": ["boolean"]},
    {"name": "requireSignature", "type": ["boolean"]},
    {"name": "locked", "type": ["boolean"]},
    {"name": "isPrivate", "type": ["boolean"]},
    {"name": "signed", "type": ["boolean"]},
    {"name": "observer", "type": ["string"]},
    {"name": "rubric", "type": ["string"]},
    {"name": "teacher", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "observationType", "type": ["string"]},
    {"name": "quickHits", "type": ["string"]},
    {"name": "score", "type": ["float"]},
    {"name": "scoreAveragedByStrand", "type": ["float"]},
    {
        "name": "observedAt",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "firstPublished",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastPublished",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "observedUntil", "type": [None]},
    {"name": "viewedByTeacher", "type": [None]},
    {"name": "archivedAt", "type": [None]},
    {"name": "observationModule", "type": [None]},
    {"name": "observationtag1", "type": [None]},
    {"name": "observationtag2", "type": [None]},
    {"name": "observationtag3", "type": [None]},
    {"name": "files", "type": [{"type": "array", "items": "None"}]},
    {"name": "meetings", "type": [{"type": "array", "items": "None"}]},
    {"name": "tags", "type": [{"type": "array", "items": "None"}]},
    {
        "name": "observationScores",
        "type": [
            [
                get_avro_record_schema(
                    name="observation_scores",
                    fields=[
                        {
                            {"name": "measurement", "type": ["string"]},
                            {"name": "measurementGroup", "type": ["string"]},
                            {"name": "valueScore", "type": ["int"]},
                            {"name": "valueText", "type": [None]},
                            {"name": "percentage", "type": [None]},
                            {
                                "name": "lastModified",
                                "type": [
                                    {
                                        "type": "string",
                                        "logicalType": "timestamp-millis",
                                    }
                                ],
                            },
                            {
                                "name": "checkboxes",
                                "type": [
                                    {
                                        "type": "array",
                                        "items": {
                                            "label": "string",
                                            "value": "boolean",
                                        },
                                    }
                                ],
                            },
                            {
                                "name": "textBoxes",
                                "type": [
                                    {
                                        "type": "array",
                                        "items": {"label": "string", "text": "string"},
                                    }
                                ],
                            },
                        },
                    ],
                ),
            ]
        ],
    },
    {
        "name": "magicNotes",
        "type": [
            [
                get_avro_record_schema(
                    name="magic_notes",
                    fields=[
                        {"name": "shared", "type": ["boolean"]},
                        {"name": "text", "type": ["string"]},
                        {
                            "name": "created",
                            "type": [
                                {"type": "string", "logicalType": "timestamp-millis"}
                            ],
                        },
                    ],
                ),
            ]
        ],
    },
]

ROLE_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "category", "type": ["string"]},
]

RUBRIC_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "scaleMin", "type": ["int"]},
    {"name": "scaleMax", "type": ["int"]},
    {"name": "isPrivate", "type": ["boolean"]},
    {"name": "name", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "scoringMethod", "type": ["string"]},
    {"name": "order", "type": ["int"]},
    {"name": "isPublished", "type": ["boolean"]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "_measurementGroups", "type": [None]},
    {
        "name": "settings",
        "type": [
            get_avro_record_schema(
                name="settings",
                fields=[
                    {"name": "enableClickToFill", "type": ["boolean"]},
                    {"name": "actionStepCreate", "type": ["boolean"]},
                    {"name": "signature", "type": ["boolean"]},
                    {"name": "signatureOnByDefault", "type": ["boolean"]},
                    {"name": "notification", "type": ["boolean"]},
                    {"name": "debrief", "type": ["boolean"]},
                    {"name": "isPrivate", "type": ["boolean"]},
                    {"name": "isScorePrivate", "type": ["boolean"]},
                    {"name": "isSiteVisit", "type": ["boolean"]},
                    {"name": "requireAll", "type": ["boolean"]},
                    {"name": "dontRequireTextboxesOnLikertRows", "type": ["boolean"]},
                    {"name": "scoreOverride", "type": ["boolean"]},
                    {"name": "scoreOnForm", "type": ["boolean"]},
                    {"name": "hasCompletionMarks", "type": ["boolean"]},
                    {"name": "isPeerRubric", "type": ["boolean"]},
                    {"name": "isAlwaysFocus", "type": ["boolean"]},
                    {"name": "showAllTextOnOpts", "type": ["boolean"]},
                    {"name": "hideFromLists", "type": ["boolean"]},
                    {"name": "hideFromTeachers", "type": ["boolean"]},
                    {"name": "hideFromCoaches", "type": ["boolean"]},
                    {"name": "hideFromRegionalCoaches", "type": ["boolean"]},
                    {"name": "hideFromSchoolAdmins", "type": ["boolean"]},
                    {"name": "hideFromSchoolAssistantAdmins", "type": ["boolean"]},
                    {"name": "isCoachingStartForm", "type": ["boolean"]},
                    {"name": "videoForm", "type": ["boolean"]},
                    {"name": "meetingQuickCreate", "type": ["boolean"]},
                    {"name": "displayNumbers", "type": ["boolean"]},
                    {"name": "displayLabels", "type": ["boolean"]},
                    {"name": "hasRowDescriptions", "type": ["boolean"]},
                    {"name": "actionStepWorkflow", "type": ["boolean"]},
                    {"name": "obsTypeFinalize", "type": ["boolean"]},
                    {"name": "descriptionsInEditor", "type": ["boolean"]},
                    {"name": "showObservationLabels", "type": ["boolean"]},
                    {"name": "showObservationType", "type": ["boolean"]},
                    {"name": "showObservationModule", "type": ["boolean"]},
                    {"name": "showObservationTag1", "type": ["boolean"]},
                    {"name": "showObservationTag2", "type": ["boolean"]},
                    {"name": "showObservationTag3", "type": ["boolean"]},
                    {"name": "hideEmptyRows", "type": ["boolean"]},
                    {"name": "hideOverallScore", "type": ["boolean"]},
                    {"name": "hideEmptyTextRows", "type": ["boolean"]},
                    {"name": "sendEmailOnSignature", "type": ["boolean"]},
                    {"name": "showStrandScores", "type": ["boolean"]},
                    {"name": "showAvgByStrand", "type": ["boolean"]},
                    {"name": "cloneable", "type": ["boolean"]},
                    {"name": "customHtmlTitle", "type": ["string"]},
                    {"name": "customHtml", "type": ["string"]},
                    {"name": "lockScoreAfterDays", "type": ["string"]},
                    {"name": "quickHits", "type": ["string"]},
                    {"name": "prepopulateActionStep", "type": [None]},
                    {"name": "defaultObsType", "type": [None]},
                    {"name": "defaultObsModule", "type": [None]},
                    {"name": "defaultObsTag1", "type": [None]},
                    {"name": "defaultObsTag2", "type": [None]},
                    {"name": "defaultObsTag3", "type": [None]},
                    {"name": "defaultUsertype", "type": [None]},
                    {"name": "defaultCourse", "type": [None]},
                ],
            )
        ],
    },
    {"name": "measurements", "type": [{"type": "array", "items": "string"}]},
    {
        "name": "layout",
        "type": [
            get_avro_record_schema(
                name="layout",
                fields=[
                    {
                        "name": "formLeft",
                        "type": [
                            [
                                get_avro_record_schema(
                                    name="form_left",
                                    fields=[
                                        {"name": "hideOnDraft", "type": ["boolean"]},
                                        {
                                            "name": "hideOnFinalized",
                                            "type": ["boolean"],
                                        },
                                        {"name": "widgetKey", "type": ["string"]},
                                        {"name": "widgetTitle", "type": ["string"]},
                                        {"name": "rubricMeasurement", "type": [None]},
                                        {"name": "widgetDescription", "type": [None]},
                                    ],
                                ),
                            ]
                        ],
                    },
                    {
                        "name": "formWide",
                        "type": [
                            [
                                get_avro_record_schema(
                                    name="form_wide",
                                    fields=[
                                        {"name": "hideOnDraft", "type": ["boolean"]},
                                        {
                                            "name": "hideOnFinalized",
                                            "type": ["boolean"],
                                        },
                                        {
                                            "name": "rubricMeasurement",
                                            "type": ["string"],
                                        },
                                        {"name": "widgetKey", "type": ["string"]},
                                        {"name": "widgetTitle", "type": ["string"]},
                                        {"name": "widgetDescription", "type": [None]},
                                    ],
                                ),
                            ]
                        ],
                    },
                ],
            ),
        ],
    },
    {
        "name": "measurementGroups",
        "type": [
            [
                get_avro_record_schema(
                    name="measurement_group",
                    fields=[
                        {"name": "_id", "type": ["string"]},
                        {"name": "name", "type": ["string"]},
                        {"name": "key", "type": ["string"]},
                        {
                            "name": "measurements",
                            "type": [
                                [
                                    get_avro_record_schema(
                                        name="measurement",
                                        fields=[
                                            {"name": "require", "type": ["boolean"]},
                                            {"name": "isPrivate", "type": ["boolean"]},
                                            {"name": "weight", "type": ["int"]},
                                            {"name": "exclude", "type": ["boolean"]},
                                            {"name": "measurement", "type": ["string"]},
                                        ],
                                    ),
                                ]
                            ],
                        },
                    ],
                ),
            ]
        ],
    },
]

SCHOOL_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "abbreviation", "type": ["string"]},
    {"name": "address", "type": ["string"]},
    {"name": "city", "type": ["string"]},
    {"name": "cluster", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "gradeSpan", "type": ["string"]},
    {"name": "highGrade", "type": ["string"]},
    {"name": "internalId", "type": ["string"]},
    {"name": "lowGrade", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "phone", "type": ["string"]},
    {"name": "principal", "type": ["string"]},
    {"name": "region", "type": ["string"]},
    {"name": "state", "type": ["string"]},
    {"name": "ward", "type": ["string"]},
    {"name": "zip", "type": ["string"]},
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "archivedAt", "type": [None]},
    {
        "name": "admins",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="admins", fields=GENERIC_REF_FIELDS
                ),
            }
        ],
    },
    {
        "name": "assistantAdmins",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="assistantAdmins", fields=GENERIC_REF_FIELDS
                ),
            }
        ],
    },
    {"name": "nonInstructionalAdmins", "type": [{"type": "array", "items": "None"}]},
    {
        "name": "observationGroups",
        "type": [
            [
                get_avro_record_schema(
                    name="observation_group",
                    fields=[
                        {"name": "_id", "type": ["string"]},
                        {"name": "locked", "type": ["boolean"]},
                        {"name": "name", "type": ["string"]},
                        {
                            "name": "lastModified",
                            "type": [
                                {
                                    "type": "string",
                                    "logicalType": "timestamp-millis",
                                }
                            ],
                        },
                        {
                            "name": "admins",
                            "type": [{"type": "array", "items": "None"}],
                        },
                        {
                            "name": "observers",
                            "type": [
                                [
                                    get_avro_record_schema(
                                        name="observers", fields=GENERIC_REF_FIELDS
                                    )
                                ]
                            ],
                        },
                        {
                            "name": "observees",
                            "type": [
                                [
                                    get_avro_record_schema(
                                        name="observees", fields=GENERIC_REF_FIELDS
                                    )
                                ]
                            ],
                        },
                    ],
                ),
            ]
        ],
    },
]

USER_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "email", "type": ["string"]},
    {"name": "endOfYearVisible", "type": ["boolean"]},
    {"name": "first", "type": ["string"]},
    {"name": "inactive", "type": ["boolean"]},
    {"name": "internalId", "type": ["string"]},
    {"name": "last", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "showOnDashboards", "type": ["boolean"]},
    {"name": "accountingId", "type": ["string"]},
    {"name": "powerSchoolId", "type": ["string"]},
    {
        "name": "archivedAt",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastActivity",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "canvasId", "type": [None]},
    {"name": "coach", "type": [None]},
    {"name": "districts", "type": [{"type": "array", "items": "string"}]},
    {"name": "additionalEmails", "type": [{"type": "array", "items": "None"}]},
    {"name": "endOfYearLog", "type": [{"type": "array", "items": "None"}]},
    {"name": "pastUserTypes", "type": [{"type": "array", "items": "None"}]},
    {"name": "regionalAdminSchools", "type": [{"type": "array", "items": "None"}]},
    {"name": "externalIntegrations", "type": [{"type": "array", "items": "None"}]},
    {
        "name": "roles",
        "type": [
            [
                get_avro_record_schema(
                    name="role",
                    fields=[
                        {"name": "role", "type": ["string"]},
                        {
                            "name": "districts",
                            "type": [{"type": "array", "items": "string"}],
                        },
                    ],
                ),
            ],
        ],
    },
    {
        "name": "defaultInformation",
        "type": [
            get_avro_record_schema(
                name="default_information",
                fields=[
                    {"name": "period", "type": [None]},
                    {
                        "name": "gradeLevel",
                        "type": [
                            get_avro_record_schema(
                                name="gradeLevel", fields=GENERIC_REF_FIELDS
                            )
                        ],
                    },
                    {
                        "name": "school",
                        "type": [
                            get_avro_record_schema(
                                name="school", fields=GENERIC_REF_FIELDS
                            )
                        ],
                    },
                    {
                        "name": "course",
                        "type": [
                            get_avro_record_schema(
                                name="course", fields=GENERIC_REF_FIELDS
                            )
                        ],
                    },
                ],
            ),
        ],
    },
    {
        "name": "preferences",
        "type": [
            get_avro_record_schema(
                name="preference",
                fields=[
                    {
                        "name": "unsubscribedTo",
                        "type": [{"type": "array", "items": "None"}],
                    },
                    {"name": "homepage", "type": ["string"]},
                    {"name": "timezoneText", "type": ["string"]},
                ],
            ),
        ],
    },
]

VIDEO_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "creator", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "url", "type": ["string"]},
    {"name": "thumbnail", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "fileName", "type": ["string"]},
    {"name": "zencoderJobId", "type": ["string"]},
    {"name": "status", "type": ["string"]},
    {"name": "style", "type": ["string"]},
    {
        "name": "created",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": [{"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "users", "type": [{"type": "array", "items": "None"}]},
    {"name": "observations", "type": [{"type": "array", "items": "None"}]},
    {"name": "comments", "type": [{"type": "array", "items": "None"}]},
    {"name": "videoNotes", "type": [{"type": "array", "items": "None"}]},
]

ENDPOINT_FIELDS = {}

# LESSON_PLAN_FORM_FIELDS = [
#     {"name": "_id", "type": ["string"]},
#     {"name": "district", "type": ["string"]},
#     {"name": "order", "type": ["int"]},
#     {"name": "name", "type": ["string"]},
#     {
#         "name": "created",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {
#         "name": "lastModified",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {"name": "archivedAt", "type": [None]},
#     {
#         "name": "creator",
#         "type": [{"_id": "string", "name": "string", "email": "string"}],
#     },
#     {"name": "settings", "type": [{}]},
#     {
#         "name": "fieldGroups",
#         "type": [
#             [
#                 {
#                     "_id": "string",
#                     "description": "string",
#                     "fields": [
#                         {
#                             "_id": "string",
#                             "name": "string",
#                             "description": "string",
#                             "isPrivate": "boolean",
#                             "type": "string",
#                             "content": None,
#                         },
#                     ],
#                     "name": "string",
#                 }
#             ]
#         ],
#     },
# ]

# LESSON_PLAN_GROUP_FIELDS = [
#     {"name": "_id", "type": ["string"]},
#     {"name": "name", "type": ["string"]},
#     {"name": "district", "type": ["string"]},
#     {"name": "status", "type": ["string"]},
#     {
#         "name": "teachDate",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {
#         "name": "created",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {
#         "name": "lastModified",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {"name": "archivedAt", "type": [None]},
#     {"name": "objective", "type": [None]},
#     {"name": "documents", "type": [{"type": "array", "items": "string"}]},
#     {
#         "name": "creator",
#         "type": [{"_id": "string", "email": "string", "name": "string"}],
#     },
#     {
#         "name": "course",
#         "type": [get_avro_record_schema(name="course", fields=GENERIC_REF_FIELDS)],
#     },
#     {
#         "name": "grade",
#         "type": [get_avro_record_schema(name="grade", fields=GENERIC_REF_FIELDS)],
#     },
#     {
#         "name": "school",
#         "type": [get_avro_record_schema(name="school", fields=GENERIC_REF_FIELDS)],
#     },
#     {
#         "name": "standard",
#         "type": [get_avro_record_schema(name="standard", fields=GENERIC_REF_FIELDS)],
#     },
#     {"name": "reviews", "type": [[{"_id": "string", "status": "string"}]]},
# ]

# LESSON_PLAN_REVIEW_FIELDS = [
#     {"name": "_id", "type": ["string"]},
#     {"name": "needsResubmit", "type": ["boolean"]},
#     {"name": "district", "type": ["string"]},
#     {"name": "document", "type": ["string"]},
#     {"name": "status", "type": ["string"]},
#     {
#         "name": "created",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {
#         "name": "lastModified",
#         "type": [{"type": "string", "logicalType": "timestamp-millis"}],
#     },
#     {"name": "archivedAt", "type": [None]},
#     {"name": "submitDate", "type": [None]},
#     {"name": "submitNote", "type": [None]},
#     {"name": "teacherNote", "type": [None]},
#     {"name": "attachments", "type": [{"type": "array", "items": "None"}]},
#     {
#         "name": "creator",
#         "type": [{"_id": "string", "name": "string", "email": "string"}],
#     },
#     {
#         "name": "group",
#         "type": [get_avro_record_schema(name="group", fields=GENERIC_REF_FIELDS)],
#     },
#     {
#         "name": "form",
#         "type": [get_avro_record_schema(name="form", fields=GENERIC_REF_FIELDS)],
#     },
#     {
#         "name": "fieldGroups",
#         "type": [
#             [
#                 {
#                     "_id": "string",
#                     "description": "string",
#                     "fields": [
#                         {
#                             "_id": "string",
#                             "name": "string",
#                             "isPrivate": "boolean",
#                             "type": "string",
#                             "description": None,
#                             "content": None,
#                         },
#                     ],
#                     "name": "string",
#                 },
#             ]
#         ],
#     },
# ]
