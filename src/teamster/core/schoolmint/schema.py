def get_avro_record_schema(name: str, fields: list):
    return {
        "type": "record",
        "name": f"{name.replace('-', '_').replace('/', '_')}_record",
        "fields": fields,
    }


GENERIC_REF_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
]

USER_REF_FIELDS = [*GENERIC_REF_FIELDS, {"name": "email", "type": "string"}]

GENERIC_TAG_TYPE_FIELDS = [
    {"name": "__v", "type": "int"},
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "creator", "type": "string"},
    {"name": "type", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "tags", "type": {"type": "array", "items": "string"}},
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "order", "type": ["null", "int"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
]

INFORMAL_FIELDS = [
    {"name": "shared", "type": "string"},
    {"name": "private", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "_id", "type": "string"},
    {
        "name": "tags",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="tag", fields=GENERIC_REF_FIELDS),
        },
    },
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
    },
    {
        "name": "user",
        "type": get_avro_record_schema(name="user", fields=USER_REF_FIELDS),
    },
]

MEASUREMENT_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "rowStyle", "type": "string"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {
        "name": "textBoxes",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="text_box",
                fields=[
                    {"name": "key", "type": "string"},
                    {"name": "label", "type": "string"},
                ],
            ),
        },
    },
    {
        "name": "measurementOptions",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="measurement_option",
                fields=[
                    {"name": "label", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                    {"name": "value", "type": ["null", "int"], "default": None},
                    {"name": "percentage", "type": ["null", "float"], "default": None},
                    {
                        "name": "created",
                        "type": ["null", "string"],
                        "logicalType": "timestamp-millis",
                        "default": None,
                    },
                ],
            ),
            "default": [],
        },
    },
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
]

MEETING_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "private", "type": "boolean"},
    {
        "name": "observations",
        "type": {"type": "array", "items": "string", "default": []},
    },
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
    },
    {
        "name": "participants",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="participant",
                fields=[
                    {"name": "user", "type": "string"},
                    {"name": "isAbsent", "type": "boolean"},
                    {"name": "customCategory", "type": "null"},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                ],
            ),
        },
    },
    {
        "name": "type",
        "type": get_avro_record_schema(
            name="type",
            fields=[
                {"name": "name", "type": "string"},
                {"name": "canRequireSignature", "type": "boolean"},
                {"name": "canBePrivate", "type": "boolean"},
                {"name": "_id", "type": ["null", "string"], "default": None},
            ],
        ),
    },
    {"name": "course", "type": ["null", "string"], "default": None},
    {"name": "grade", "type": ["null", "string"], "default": None},
    {"name": "isOpenToParticipants", "type": ["null", "boolean"], "default": None},
    {"name": "isTemplate", "type": ["null", "boolean"], "default": None},
    {"name": "isWeeklyDataMeeting", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "school", "type": ["null", "string"], "default": None},
    {"name": "signatureRequired", "type": ["null", "boolean"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {
        "name": "created",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "date",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "actionSteps",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "onleave",
        "type": ["null", {"type": "array", "items": "null", "default": []}],
        "default": None,
    },
    {
        "name": "offweek",
        "type": ["null", {"type": "array", "items": "null", "default": []}],
        "default": None,
    },
    {
        "name": "unable",
        "type": ["null", {"type": "array", "items": "null", "default": []}],
        "default": None,
    },
    {
        "name": "additionalFields",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="additional_field",
                    fields=[
                        {"name": "_id", "type": "string"},
                        {"name": "name", "type": "string"},
                        {"name": "description", "type": "string"},
                        {"name": "type", "type": "string"},
                        {"name": "isPrivate", "type": "boolean"},
                        {
                            "name": "content",
                            "type": [
                                "null",
                                "string",
                                "int",
                                "boolean",
                                get_avro_record_schema(
                                    name="content",
                                    fields=[
                                        {"name": "left", "type": "string"},
                                        {"name": "right", "type": "string"},
                                    ],
                                ),
                            ],
                            "default": None,
                        },
                    ],
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

ROLE_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "category", "type": "string"},
]

RUBRIC_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "isPrivate", "type": "boolean"},
    {"name": "isPublished", "type": "boolean"},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "settings",
        "type": get_avro_record_schema(
            name="setting",
            fields=[
                {"name": "actionStepCreate", "type": "boolean"},
                {"name": "actionStepWorkflow", "type": "boolean"},
                {"name": "allowCoTeacher", "type": "boolean"},
                {"name": "allowTakeOverObservation", "type": "boolean"},
                {"name": "cloneable", "type": "boolean"},
                {"name": "coachingEvalType", "type": "string"},
                {"name": "debrief", "type": "boolean"},
                {"name": "defaultObsModule", "type": "null"},
                {"name": "defaultObsTag1", "type": "null"},
                {"name": "defaultObsTag2", "type": "null"},
                {"name": "defaultObsTag3", "type": "null"},
                {"name": "defaultObsType", "type": ["null", "string"]},
                {"name": "descriptionsInEditor", "type": "boolean"},
                {"name": "displayLabels", "type": "boolean"},
                {"name": "displayNumbers", "type": "boolean"},
                {"name": "enablePointClick", "type": "boolean"},
                {"name": "hasCompletionMarks", "type": "boolean"},
                {"name": "hasRowDescriptions", "type": "boolean"},
                {"name": "hideFromLists", "type": "boolean"},
                {"name": "hideOverallScore", "type": "boolean"},
                {"name": "isPrivate", "type": "boolean"},
                {"name": "isScorePrivate", "type": "boolean"},
                {"name": "lockScoreAfterDays", "type": ["int", "string"]},
                {"name": "notification", "type": "boolean"},
                {"name": "obsTypeFinalize", "type": "boolean"},
                {"name": "prepopulateActionStep", "type": ["string", "null"]},
                {"name": "quickHits", "type": ["null", "string"]},
                {"name": "requireActionStepBeforeFinalize", "type": "boolean"},
                {"name": "requireAll", "type": "boolean"},
                {"name": "rolesExcluded", "type": {"type": "array", "items": "string"}},
                {"name": "scoreOnForm", "type": "boolean"},
                {"name": "scoreOverride", "type": "boolean"},
                {"name": "sendEmailOnSignature", "type": "boolean"},
                {"name": "showAllTextOnOpts", "type": "boolean"},
                {"name": "showAvgByStrand", "type": "boolean"},
                {"name": "showObservationLabels", "type": "boolean"},
                {"name": "showObservationModule", "type": "boolean"},
                {"name": "showObservationTag1", "type": "boolean"},
                {"name": "showObservationTag2", "type": "boolean"},
                {"name": "showObservationTag3", "type": "boolean"},
                {"name": "showObservationType", "type": "boolean"},
                {"name": "showStrandScores", "type": "boolean"},
                {"name": "signature", "type": "boolean"},
                {"name": "signatureOnByDefault", "type": "boolean"},
                {"name": "transferDescriptionToTextbox", "type": "boolean"},
                {"name": "videoForm", "type": "boolean"},
                {"name": "actionStep", "type": ["null", "boolean"], "default": None},
                {
                    "name": "coachActionStep",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {"name": "customHtml", "type": ["null", "string"], "default": None},
                {
                    "name": "customHtmlTitle",
                    "type": ["null", "string"],
                    "default": None,
                },
                {"name": "dashHidden", "type": ["null", "boolean"], "default": None},
                {"name": "defaultCourse", "type": "null", "default": None},
                {"name": "defaultObsTag4", "type": "null", "default": None},
                {"name": "defaultUsertype", "type": "null", "default": None},
                {
                    "name": "disableMeetingsTab",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "dontRequireTextboxesOnLikertRows",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "enableClickToFill",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "featureInstructions",
                    "type": [
                        "null",
                        {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="feature_instruction",
                                fields=[
                                    {"name": "hideOnDraft", "type": "boolean"},
                                    {"name": "hideOnFinalized", "type": "boolean"},
                                    {"name": "includeOnEmails", "type": "boolean"},
                                    {"name": "_id", "type": "string"},
                                    {"name": "section", "type": "string"},
                                    {"name": "text", "type": "string"},
                                    {"name": "titleOverride", "type": "string"},
                                ],
                            ),
                        },
                    ],
                    "default": None,
                },
                {"name": "filters", "type": ["null", "boolean"], "default": None},
                {"name": "goalCreate", "type": ["null", "boolean"], "default": None},
                {"name": "goals", "type": ["null", "boolean"], "default": None},
                {
                    "name": "hiddenFeatures",
                    "type": ["null", {"type": "array", "items": "string"}],
                    "default": None,
                },
                {"name": "hideEmptyRows", "type": ["null", "boolean"], "default": None},
                {
                    "name": "hideEmptyTextRows",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "hideFromCoaches",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "hideFromRegionalCoaches",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "hideFromSchoolAdmins",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "hideFromSchoolAssistantAdmins",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "hideFromTeachers",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {"name": "isAlwaysFocus", "type": ["null", "boolean"], "default": None},
                {
                    "name": "isHolisticDefault",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "isCoachingStartForm",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "isCompetencyRubric",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {"name": "isPeerRubric", "type": ["null", "boolean"], "default": None},
                {"name": "isSiteVisit", "type": ["null", "boolean"], "default": None},
                {"name": "locked", "type": ["null", "boolean"], "default": None},
                {
                    "name": "meetingQuickCreate",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "meetingTypesExcludedFromScheduling",
                    "type": "null",
                    "default": None,
                },
                {
                    "name": "nameAndSignatureDisplay",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "observationTypesHidden",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "obsShowEndDate",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "privateRows",
                    "type": ["null", {"type": "array", "items": "string"}],
                    "default": None,
                },
                {
                    "name": "requireOnlyScores",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "resources",
                    "type": [
                        "null",
                        {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="resource",
                                fields=[
                                    {"name": "label", "type": "string"},
                                    {"name": "url", "type": "string"},
                                    {
                                        "name": "_id",
                                        "type": ["null", "string"],
                                        "default": None,
                                    },
                                ],
                            ),
                        },
                    ],
                    "default": None,
                },
                {"name": "requireGoal", "type": ["null", "boolean"], "default": None},
                {"name": "rubrictag1", "type": ["null", "string"], "default": None},
                {
                    "name": "schoolsExcluded",
                    "type": ["null", {"type": "array", "items": "null"}],
                    "default": None,
                },
                {"name": "scripting", "type": ["null", "boolean"], "default": None},
                {
                    "name": "showObservationTag4",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "showOnDataReports",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "useAdditiveScoring",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {
                    "name": "useStrandWeights",
                    "type": ["null", "boolean"],
                    "default": None,
                },
                {"name": "video", "type": ["null", "boolean"], "default": None},
            ],
        ),
    },
    {
        "name": "layout",
        "type": get_avro_record_schema(
            name="layout",
            fields=[
                {
                    "name": "formLeft",
                    "type": {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="form_left",
                            fields=[
                                {"name": "widgetTitle", "type": "string"},
                                {"name": "widgetKey", "type": ["null", "string"]},
                                {
                                    "name": "widgetDescription",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "assignmentSlug",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "hideOnDraft",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "hideOnFinalized",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "includeInEmail",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "rubricMeasurement",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "showOnFinalizedPopup",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                            ],
                        ),
                    },
                },
                {
                    "name": "formWide",
                    "type": {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="form_wide",
                            fields=[
                                {"name": "widgetTitle", "type": "string"},
                                {"name": "widgetKey", "type": ["null", "string"]},
                                {
                                    "name": "widgetDescription",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "assignmentSlug",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "hideOnDraft",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "hideOnFinalized",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "includeInEmail",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                                {
                                    "name": "rubricMeasurement",
                                    "type": ["null", "string"],
                                    "default": None,
                                },
                                {
                                    "name": "showOnFinalizedPopup",
                                    "type": ["null", "boolean"],
                                    "default": None,
                                },
                            ],
                        ),
                    },
                },
            ],
        ),
    },
    {
        "name": "measurementGroups",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="measurement_group",
                fields=[
                    {"name": "name", "type": "string"},
                    {"name": "key", "type": "string"},
                    {"name": "weight", "type": ["null", "int"], "default": None},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                    {
                        "name": "description",
                        "type": ["null", "string"],
                        "default": None,
                    },
                    {
                        "name": "measurements",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="measurement",
                                fields=[
                                    {"name": "measurement", "type": ["null", "string"]},
                                    {"name": "weight", "type": "int"},
                                    {"name": "require", "type": "boolean"},
                                    {"name": "isPrivate", "type": "boolean"},
                                    {
                                        "name": "_id",
                                        "type": ["null", "string"],
                                        "default": None,
                                    },
                                    {
                                        "name": "key",
                                        "type": ["null", "string"],
                                        "default": None,
                                    },
                                    {
                                        "name": "exclude",
                                        "type": ["null", "boolean"],
                                        "default": None,
                                    },
                                    {
                                        "name": "hideDescription",
                                        "type": ["null", "boolean"],
                                        "default": None,
                                    },
                                ],
                            ),
                        },
                    },
                ],
            ),
        },
    },
]

SCHOOL_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {
        "name": "nonInstructionalAdmins",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="non_instructional_admin", fields=GENERIC_REF_FIELDS
            ),
        },
    },
    {
        "name": "admins",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="admin", fields=GENERIC_REF_FIELDS),
        },
    },
    {
        "name": "assistantAdmins",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="assistant_admin", fields=GENERIC_REF_FIELDS
            ),
        },
    },
    {
        "name": "observationGroups",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="observation_group",
                fields=[
                    {"name": "_id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {
                        "name": "observers",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="observer", fields=GENERIC_REF_FIELDS
                            ),
                        },
                    },
                    {
                        "name": "observees",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="observee", fields=GENERIC_REF_FIELDS
                            ),
                        },
                    },
                ],
            ),
        },
    },
]

VIDEO_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "url", "type": ["null", "string"]},
    {"name": "name", "type": "string"},
    {"name": "style", "type": "string"},
    {
        "name": "created",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {
        "name": "lastModified",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {"name": "observations", "type": {"type": "array", "items": "string"}},
    {"name": "comments", "type": {"type": "array", "items": "null"}},
    {
        "name": "videoNotes",
        "type": {
            "type": "array",
            "items": [
                "null",
                get_avro_record_schema(
                    name="video_notes",
                    fields=[
                        {"name": "_id", "type": "string"},
                        {"name": "text", "type": "string"},
                        {"name": "createdOnMillisecond", "type": "int"},
                        {"name": "creator", "type": "string"},
                    ],
                ),
            ],
        },
    },
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=GENERIC_REF_FIELDS),
    },
    {
        "name": "users",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="user",
                fields=[
                    {"name": "user", "type": "string"},
                    {"name": "role", "type": "string"},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                ],
            ),
        },
    },
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "thumbnail", "type": ["null", "string"], "default": None},
    {"name": "fileName", "type": ["null", "string"], "default": None},
    {"name": "zencoderJobId", "type": ["null", "string"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
]

USER_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "internalId", "type": ["null", "string"]},
    {"name": "accountingId", "type": ["null", "string"]},
    {"name": "powerSchoolId", "type": ["null", "string"]},
    {"name": "canvasId", "type": ["null", "string"]},
    {"name": "name", "type": "string"},
    {"name": "first", "type": ["null", "string"]},
    {"name": "last", "type": ["null", "string"]},
    {"name": "email", "type": "string"},
    {"name": "endOfYearVisible", "type": ["null", "boolean"]},
    {"name": "inactive", "type": ["null", "boolean"]},
    {"name": "showOnDashboards", "type": "boolean"},
    {"name": "coach", "type": ["null", "string"]},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "created", "type": {"type": "string", "logicalType": "timestamp-millis"}},
    {
        "name": "lastActivity",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {"name": "districts", "type": {"type": "array", "items": "string"}},
    {"name": "additionalEmails", "type": {"type": "array", "items": "string"}},
    {"name": "endOfYearLog", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "pastUserTypes", "type": ["null", {"type": "array", "items": "null"}]},
    {
        "name": "regionalAdminSchools",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="regional_admin_school",
                fields=[
                    {"name": "_id", "type": "string"},
                    {"name": "name", "type": "string"},
                ],
            ),
        },
    },
    {
        "name": "externalIntegrations",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="external_integration",
                    fields=[
                        {"name": "type", "type": "string"},
                        {"name": "id", "type": "string"},
                    ],
                ),
            },
        ],
    },
    {
        "name": "roles",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="role",
                fields=[
                    {"name": "_id", "type": "string"},
                    {"name": "name", "type": "string"},
                ],
            ),
        },
    },
    {
        "name": "defaultInformation",
        "type": get_avro_record_schema(
            name="default_information",
            fields=[
                {"name": "gradeLevel", "type": ["null", "string"], "default": None},
                {"name": "school", "type": ["null", "string"], "default": None},
                {"name": "course", "type": ["null", "string"], "default": None},
                {"name": "period", "type": ["null", "string"], "default": None},
            ],
        ),
    },
    {
        "name": "preferences",
        "type": ["null", get_avro_record_schema(name="preference", fields=[])],
    },
]

ASSIGNMENT_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "excludeFromBank", "type": "boolean"},
    {"name": "locked", "type": "boolean"},
    {"name": "private", "type": "boolean"},
    {"name": "coachingActivity", "type": "boolean"},
    {"name": "type", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
    },
    {
        "name": "user",
        "type": get_avro_record_schema(name="user", fields=USER_REF_FIELDS),
    },
    {
        "name": "progress",
        "type": get_avro_record_schema(
            name="progress",
            fields=[
                {"name": "percent", "type": "int"},
                {"name": "assigner", "type": ["null", "string"]},
                {"name": "justification", "type": ["null", "string"]},
                {
                    "name": "date",
                    "type": [
                        "null",
                        {"type": "string", "logicalType": "timestamp-millis"},
                    ],
                },
            ],
        ),
    },
    {
        "name": "tags",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="tag",
                fields=[
                    {"name": "_id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "url", "type": ["null", "string"], "default": None},
                ],
            ),
        },
    },
    {"name": "name", "type": ["null", "string"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "school",
        "type": [
            "null",
            get_avro_record_schema(name="school", fields=GENERIC_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "grade",
        "type": [
            "null",
            get_avro_record_schema(name="grade", fields=GENERIC_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "course",
        "type": [
            "null",
            get_avro_record_schema(name="course", fields=GENERIC_REF_FIELDS),
        ],
        "default": None,
    },
]

OBSERVATION_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "isPublished", "type": "boolean"},
    {"name": "locked", "type": ["null", "boolean"]},
    {"name": "observationModule", "type": "null"},
    {"name": "observationtag1", "type": "null"},
    {"name": "observationtag2", "type": "null"},
    {"name": "observationtag3", "type": "null"},
    {"name": "observationType", "type": ["null", "string"]},
    {"name": "requireSignature", "type": ["null", "boolean"]},
    {
        "name": "viewedByTeacher",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "created", "type": {"type": "string", "logicalType": "timestamp-millis"}},
    {
        "name": "observedAt",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {
        "name": "firstPublished",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {
        "name": "lastModified",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {"name": "meetings", "type": {"type": "array", "items": ["null", "string"]}},
    {"name": "tags", "type": {"type": "array", "items": "null"}},
    {
        "name": "videos",
        "type": {
            "type": "array",
            "items": [
                "null",
                get_avro_record_schema(
                    name="video",
                    fields=[
                        {"name": "video", "type": "string"},
                        {"name": "includeVideoTimestamps", "type": "boolean"},
                    ],
                ),
            ],
        },
    },
    {
        "name": "rubric",
        "type": get_avro_record_schema(name="rubric", fields=GENERIC_REF_FIELDS),
    },
    {
        "name": "observer",
        "type": get_avro_record_schema(name="observer", fields=USER_REF_FIELDS),
    },
    {
        "name": "teacher",
        "type": get_avro_record_schema(name="teacher", fields=USER_REF_FIELDS),
    },
    {
        "name": "attachments",
        "type": {
            "type": "array",
            "items": [
                "null",
                get_avro_record_schema(
                    name="attachment",
                    fields=[
                        {"name": "file", "type": "string"},
                        {"name": "resource", "type": ["null"]},
                        {"name": "private", "type": "boolean"},
                        {"name": "_id", "type": "string"},
                        {"name": "id", "type": "string"},
                        {"name": "creator", "type": "string"},
                        {
                            "name": "created",
                            "type": "string",
                            "logicalType": "timestamp-millis",
                        },
                    ],
                ),
            ],
        },
    },
    {
        "name": "teachingAssignment",
        "type": get_avro_record_schema(
            name="teaching_assignment",
            fields=[
                {"name": "_id", "type": "string"},
                {"name": "school", "type": ["null", "string"], "default": None},
                {"name": "course", "type": ["null", "string"], "default": None},
                {"name": "grade", "type": ["null", "string"], "default": None},
            ],
        ),
    },
    {
        "name": "magicNotes",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="magic_note",
                fields=[
                    {"name": "_id", "type": "string"},
                    {"name": "text", "type": "string"},
                    {"name": "shared", "type": "boolean"},
                    {
                        "name": "created",
                        "type": {"type": "string", "logicalType": "timestamp-millis"},
                    },
                    {"name": "column", "type": "null", "default": None},
                ],
            ),
        },
    },
    {
        "name": "observationScores",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="observation_score",
                fields=[
                    {"name": "measurement", "type": "string"},
                    {"name": "measurementGroup", "type": "string"},
                    {"name": "valueScore", "type": ["null", "int"]},
                    {"name": "valueText", "type": "null"},
                    {"name": "percentage", "type": "null"},
                    {
                        "name": "lastModified",
                        "type": {"type": "string", "logicalType": "timestamp-millis"},
                    },
                    {
                        "name": "checkboxes",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="checkbox",
                                fields=[
                                    {"name": "label", "type": "string"},
                                    {
                                        "name": "value",
                                        "type": ["null", "boolean"],
                                        "default": None,
                                    },
                                ],
                            ),
                        },
                    },
                    {
                        "name": "textBoxes",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="text_box",
                                fields=[
                                    {"name": "key", "type": "string"},
                                    {"name": "value", "type": ["null", "string"]},
                                ],
                            ),
                        },
                    },
                ],
            ),
        },
    },
    {"name": "score", "type": ["null", "float"], "default": None},
    {"name": "quickHits", "type": ["null", "string"], "default": None},
    {"name": "scoreAveragedByStrand", "type": ["null", "float"], "default": None},
    {"name": "sendEmail", "type": ["null", "boolean"], "default": None},
    {"name": "signed", "type": ["null", "boolean"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "observedUntil",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "signedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "lastPublished",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "comments",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {
        "name": "listTwoColumnA",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "listTwoColumnB",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "listTwoColumnAPaired",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {
        "name": "listTwoColumnBPaired",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {
        "name": "eventLog",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {
        "name": "files",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
]

ENDPOINT_FIELDS = {
    "generic-tags/assignmentpresets": GENERIC_TAG_TYPE_FIELDS,
    "informals": INFORMAL_FIELDS,
    "measurements": MEASUREMENT_FIELDS,
    "meetings": MEETING_FIELDS,
    "roles": ROLE_FIELDS,
    "rubrics": RUBRIC_FIELDS,
    "schools": SCHOOL_FIELDS,
    "videos": VIDEO_FIELDS,
    "users": USER_FIELDS,
    "assignments": ASSIGNMENT_FIELDS,
    "observations": OBSERVATION_FIELDS,
}

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
#     {"name": "archivedAt", "type": ["null"]},
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
#                             "content": "null",
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
#     {"name": "archivedAt", "type": ["null"]},
#     {"name": "objective", "type": ["null"]},
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
#     {"name": "archivedAt", "type": ["null"]},
#     {"name": "submitDate", "type": ["null"]},
#     {"name": "submitNote", "type": ["null"]},
#     {"name": "teacherNote", "type": ["null"]},
#     {"name": "attachments", "type": [{"type": "array", "items": "null"}]},
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
#                             "description": "null",
#                             "content": "null",
#                         },
#                     ],
#                     "name": "string",
#                 },
#             ]
#         ],
#     },
# ]
