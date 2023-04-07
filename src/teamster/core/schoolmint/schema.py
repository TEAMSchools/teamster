from teamster.core.utils.functions import get_avro_record_schema

REF_FIELDS = [
    {"name": "_id", "type": ["null", "string"]},
    {"name": "name", "type": ["null", "string"], "default": None},
]

CORE_FIELDS = [
    *REF_FIELDS,
    {"name": "district", "type": ["null", "string"], "default": None},
    {
        "name": "created",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "lastModified",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "archivedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

USER_REF_FIELDS = [
    *REF_FIELDS,
    {"name": "email", "type": ["null", "string"]},
]

ROLE_FIELDS = [
    *REF_FIELDS,
    {"name": "category", "type": ["null", "string"]},
    {"name": "district", "type": ["null", "string"]},
]

GENERIC_TAG_TYPE_FIELDS = [
    *CORE_FIELDS,
    {"name": "__v", "type": ["null", "int"]},
    {"name": "showOnDash", "type": ["null", "boolean"], "default": None},
    {"name": "color", "type": ["null", "string"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "parent", "type": ["null"], "default": None},
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
]

ADDITIONAL_FIELD_FIELDS = [
    *REF_FIELDS,
    {"name": "description", "type": ["null", "string"]},
    {"name": "type", "type": ["null", "string"]},
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "leftName", "type": ["null", "string"], "default": None},
    {"name": "rightName", "type": ["null", "string"], "default": None},
    {"name": "hiddenUntilMeetingStart", "type": ["null", "boolean"], "default": None},
    {"name": "enableParticipantsCopy", "type": ["null", "boolean"], "default": None},
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
                    {"name": "left", "type": ["null", "string"]},
                    {"name": "right", "type": ["null", "string"]},
                ],
            ),
        ],
        "default": None,
    },
]

GT_MEETINGTYPE_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "canBePrivate", "type": ["null", "boolean"]},
    {"name": "canRequireSignature", "type": ["null", "boolean"]},
    {"name": "coachingEvalType", "type": ["null", "string"]},
    {
        "name": "customAbsentCategories",
        "type": ["null", {"type": "array", "items": "null"}],
    },
    {"name": "enableModule", "type": ["null", "boolean"]},
    {"name": "enableTag1", "type": ["null", "boolean"]},
    {"name": "enableTag2", "type": ["null", "boolean"]},
    {"name": "enableTag3", "type": ["null", "boolean"]},
    {"name": "enableTag4", "type": ["null", "boolean"]},
    {"name": "isWeeklyDataMeeting", "type": ["null", "boolean"]},
    {"name": "videoForm", "type": ["null", "boolean"]},
    {"name": "resources", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "excludedModules", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "excludedTag1s", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "excludedTag2s", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "excludedTag3s", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "excludedTag4s", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "rolesExcluded", "type": ["null", {"type": "array", "items": "string"}]},
    {"name": "schoolsExcluded", "type": ["null", {"type": "array", "items": "null"}]},
    {
        "name": "additionalFields",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="additional_field", fields=ADDITIONAL_FIELD_FIELDS
                ),
            },
        ],
    },
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "enablePhases", "type": ["null", "boolean"], "default": None},
    {"name": "enableParticipantsCopy", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromLists", "type": ["null", "boolean"], "default": None},
]

GT_TAG_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "parents", "type": ["null", {"type": "array", "items": "string"}]},
    {"name": "rows", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "url", "type": ["null", "string"], "default": None},
]

INFORMAL_FIELDS = [
    *CORE_FIELDS,
    {"name": "shared", "type": ["null", "string"]},
    {"name": "private", "type": ["null", "string"]},
    {
        "name": "tags",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="tag", fields=REF_FIELDS),
            },
        ],
    },
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
    },
    {
        "name": "user",
        "type": ["null", get_avro_record_schema(name="user", fields=USER_REF_FIELDS)],
    },
]

MEASUREMENT_FIELDS = [
    *CORE_FIELDS,
    {"name": "rowStyle", "type": ["null", "string"]},
    {
        "name": "textBoxes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="text_box",
                    fields=[
                        {"name": "key", "type": ["null", "string"]},
                        {"name": "label", "type": ["null", "string"]},
                    ],
                ),
            },
        ],
    },
    {
        "name": "measurementOptions",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement_option",
                    fields=[
                        {"name": "label", "type": ["null", "string"]},
                        {"name": "description", "type": ["null", "string"]},
                        {"name": "_id", "type": ["null", "string"], "default": None},
                        {"name": "value", "type": ["null", "int"], "default": None},
                        {
                            "name": "percentage",
                            "type": ["null", "float"],
                            "default": None,
                        },
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
        ],
    },
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
]

MEETING_FIELDS = [
    *CORE_FIELDS,
    {"name": "private", "type": ["null", "boolean"]},
    {
        "name": "observations",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
    },
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
    },
    {
        "name": "participants",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="participant",
                    fields=[
                        {"name": "user", "type": ["null", "string"]},
                        {"name": "isAbsent", "type": ["null", "boolean"]},
                        {"name": "customCategory", "type": ["null"]},
                        {"name": "_id", "type": ["null", "string"], "default": None},
                    ],
                ),
            },
        ],
    },
    {
        "name": "type",
        "type": [
            "null",
            get_avro_record_schema(
                name="type",
                fields=[
                    {"name": "name", "type": ["null", "string"]},
                    {"name": "canRequireSignature", "type": ["null", "boolean"]},
                    {"name": "canBePrivate", "type": ["null", "boolean"]},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                ],
            ),
        ],
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
        "name": "date",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
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
                    name="additional_field", fields=ADDITIONAL_FIELD_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {"name": "meetingtag1", "type": ["null", "string"], "default": None},
    {"name": "meetingtag2", "type": ["null", "string"], "default": None},
    {"name": "meetingtag3", "type": ["null", "string"], "default": None},
    {"name": "meetingtag4", "type": ["null", "string"], "default": None},
    {"name": "enablePhases", "type": ["null", "boolean"], "default": None},
]

SETTING_FIELDS = [
    {"name": "actionStepCreate", "type": ["null", "boolean"]},
    {"name": "actionStepWorkflow", "type": ["null", "boolean"]},
    {"name": "allowCoTeacher", "type": ["null", "boolean"]},
    {"name": "allowTakeOverObservation", "type": ["null", "boolean"]},
    {"name": "coachingEvalType", "type": ["null", "string"]},
    {"name": "debrief", "type": ["null", "boolean"]},
    {"name": "defaultObsModule", "type": ["null"]},
    {"name": "defaultObsType", "type": ["null", "string"]},
    {"name": "descriptionsInEditor", "type": ["null", "boolean"]},
    {"name": "displayLabels", "type": ["null", "boolean"]},
    {"name": "displayNumbers", "type": ["null", "boolean"]},
    {"name": "enablePointClick", "type": ["null", "boolean"]},
    {"name": "hasCompletionMarks", "type": ["null", "boolean"]},
    {"name": "hasRowDescriptions", "type": ["null", "boolean"]},
    {"name": "hideFromLists", "type": ["null", "boolean"]},
    {"name": "hideOverallScore", "type": ["null", "boolean"]},
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "isScorePrivate", "type": ["null", "boolean"]},
    {"name": "lockScoreAfterDays", "type": ["int", "string"]},
    {"name": "notification", "type": ["null", "boolean"]},
    {"name": "obsTypeFinalize", "type": ["null", "boolean"]},
    {"name": "prepopulateActionStep", "type": ["string", "null"]},
    {"name": "quickHits", "type": ["null", "string"]},
    {"name": "requireActionStepBeforeFinalize", "type": ["null", "boolean"]},
    {"name": "requireAll", "type": ["null", "boolean"]},
    {"name": "rolesExcluded", "type": ["null", {"type": "array", "items": "string"}]},
    {"name": "scoreOnForm", "type": ["null", "boolean"]},
    {"name": "scoreOverride", "type": ["null", "boolean"]},
    {"name": "sendEmailOnSignature", "type": ["null", "boolean"]},
    {"name": "showAllTextOnOpts", "type": ["null", "boolean"]},
    {"name": "showObservationLabels", "type": ["null", "boolean"]},
    {"name": "showObservationModule", "type": ["null", "boolean"]},
    {"name": "showObservationTag1", "type": ["null", "boolean"]},
    {"name": "showObservationTag2", "type": ["null", "boolean"]},
    {"name": "showObservationTag3", "type": ["null", "boolean"]},
    {"name": "showObservationType", "type": ["null", "boolean"]},
    {"name": "signature", "type": ["null", "boolean"]},
    {"name": "signatureOnByDefault", "type": ["null", "boolean"]},
    {"name": "transferDescriptionToTextbox", "type": ["null", "boolean"]},
    {"name": "videoForm", "type": ["null", "boolean"]},
    {"name": "actionStep", "type": ["null", "boolean"], "default": None},
    {"name": "cloneable", "type": ["null", "boolean"], "default": None},
    {"name": "coachActionStep", "type": ["null", "boolean"], "default": None},
    {"name": "customHtml", "type": ["null", "string"], "default": None},
    {"name": "customHtml1", "type": ["null", "string"], "default": None},
    {"name": "customHtml2", "type": ["null", "string"], "default": None},
    {"name": "customHtml3", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle1", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle2", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle3", "type": ["null", "string"], "default": None},
    {"name": "dashHidden", "type": ["null", "boolean"], "default": None},
    {"name": "defaultCourse", "type": ["null"], "default": None},
    {"name": "defaultObsTag1", "type": ["null"], "default": None},
    {"name": "defaultObsTag2", "type": ["null"], "default": None},
    {"name": "defaultObsTag3", "type": ["null"], "default": None},
    {"name": "defaultObsTag4", "type": ["null"], "default": None},
    {"name": "defaultUsertype", "type": ["null"], "default": None},
    {"name": "disableMeetingsTab", "type": ["null", "boolean"], "default": None},
    {
        "name": "dontRequireTextboxesOnLikertRows",
        "type": ["null", "boolean"],
        "default": None,
    },
    {"name": "enableClickToFill", "type": ["null", "boolean"], "default": None},
    {"name": "filters", "type": ["null", "boolean"], "default": None},
    {"name": "goalCreate", "type": ["null", "boolean"], "default": None},
    {"name": "goals", "type": ["null", "boolean"], "default": None},
    {
        "name": "hiddenFeatures",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {"name": "hideEmptyRows", "type": ["null", "boolean"], "default": None},
    {"name": "hideEmptyTextRows", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromCoaches", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromRegionalCoaches", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromSchoolAdmins", "type": ["null", "boolean"], "default": None},
    {
        "name": "hideFromSchoolAssistantAdmins",
        "type": ["null", "boolean"],
        "default": None,
    },
    {"name": "hideFromTeachers", "type": ["null", "boolean"], "default": None},
    {"name": "isAlwaysFocus", "type": ["null", "boolean"], "default": None},
    {"name": "isHolisticDefault", "type": ["null", "boolean"], "default": None},
    {"name": "isCoachingStartForm", "type": ["null", "boolean"], "default": None},
    {"name": "isCompetencyRubric", "type": ["null", "boolean"], "default": None},
    {"name": "isPeerRubric", "type": ["null", "boolean"], "default": None},
    {"name": "isSiteVisit", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "meetingQuickCreate", "type": ["null", "boolean"], "default": None},
    {"name": "nameAndSignatureDisplay", "type": ["null", "boolean"], "default": None},
    {"name": "obsShowEndDate", "type": ["null", "boolean"], "default": None},
    {"name": "meetingTypesExcludedFromScheduling", "type": ["null"], "default": None},
    {
        "name": "privateRows",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "observationTypesHidden",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {
        "name": "requiredRows",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {"name": "requireObservationType", "type": ["null", "boolean"], "default": None},
    {"name": "requireOnlyScores", "type": ["null", "boolean"], "default": None},
    {"name": "requireGoal", "type": ["null", "boolean"], "default": None},
    {"name": "rubrictag1", "type": ["null", "string"], "default": None},
    {
        "name": "schoolsExcluded",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
    {"name": "scripting", "type": ["null", "boolean"], "default": None},
    {"name": "showAvgByStrand", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationTag4", "type": ["null", "boolean"], "default": None},
    {"name": "showOnDataReports", "type": ["null", "boolean"], "default": None},
    {"name": "showStrandScores", "type": ["null", "boolean"], "default": None},
    {"name": "useAdditiveScoring", "type": ["null", "boolean"], "default": None},
    {"name": "useStrandWeights", "type": ["null", "boolean"], "default": None},
    {"name": "video", "type": ["null", "boolean"], "default": None},
    {
        "name": "featureInstructions",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="feature_instruction",
                    fields=[
                        {"name": "hideOnDraft", "type": ["null", "boolean"]},
                        {"name": "hideOnFinalized", "type": ["null", "boolean"]},
                        {"name": "includeOnEmails", "type": ["null", "boolean"]},
                        {"name": "_id", "type": ["null", "string"]},
                        {"name": "section", "type": ["null", "string"]},
                        {"name": "text", "type": ["null", "string"]},
                        {"name": "titleOverride", "type": ["null", "string"]},
                    ],
                ),
            },
        ],
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
                        {"name": "label", "type": ["null", "string"]},
                        {"name": "url", "type": ["null", "string"]},
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
]

FORM_FIELDS = [
    {"name": "widgetTitle", "type": ["null", "string"]},
    {"name": "widgetKey", "type": ["null", "string"]},
    {"name": "widgetDescription", "type": ["null", "string"], "default": None},
    {"name": "assignmentSlug", "type": ["null", "string"], "default": None},
    {"name": "hideOnDraft", "type": ["null", "boolean"], "default": None},
    {"name": "hideOnFinalized", "type": ["null", "boolean"], "default": None},
    {"name": "includeInEmail", "type": ["null", "boolean"], "default": None},
    {"name": "rubricMeasurement", "type": ["null", "string"], "default": None},
    {"name": "showOnFinalizedPopup", "type": ["null", "boolean"], "default": None},
    {"name": "mustBeMainPanel", "type": ["null", "boolean"], "default": None},
]

LAYOUT_FIELDS = [
    {
        "name": "formLeft",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="form_left", fields=FORM_FIELDS),
            },
        ],
    },
    {
        "name": "formWide",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="form_wide", fields=FORM_FIELDS),
            },
        ],
    },
]

MEASUREMENT_GROUP_MEASUREMENT_FIELDS = [
    {"name": "measurement", "type": ["null", "string"]},
    {"name": "weight", "type": ["null", "int"]},
    {"name": "require", "type": ["null", "boolean"]},
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "exclude", "type": ["null", "boolean"], "default": None},
    {"name": "hideDescription", "type": ["null", "boolean"], "default": None},
]

MEASUREMENT_GROUP_FIELDS = [
    {"name": "name", "type": ["null", "string"]},
    {"name": "key", "type": ["null", "string"]},
    {"name": "weight", "type": ["null", "int"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {
        "name": "measurements",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement", fields=MEASUREMENT_GROUP_MEASUREMENT_FIELDS
                ),
            },
        ],
    },
]

RUBRIC_FIELDS = [
    *CORE_FIELDS,
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "isPublished", "type": ["null", "boolean"]},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {
        "name": "settings",
        "type": ["null", get_avro_record_schema(name="setting", fields=SETTING_FIELDS)],
    },
    {
        "name": "layout",
        "type": ["null", get_avro_record_schema(name="layout", fields=LAYOUT_FIELDS)],
    },
    {
        "name": "measurementGroups",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement_group", fields=MEASUREMENT_GROUP_FIELDS
                ),
            },
        ],
    },
]

OBSERVATION_GROUP_FIELDS = [
    *REF_FIELDS,
    {
        "name": "observers",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observer", fields=USER_REF_FIELDS
                ),
            },
        ],
    },
    {
        "name": "observees",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observee", fields=USER_REF_FIELDS
                ),
            },
        ],
    },
]

SCHOOL_FIELDS = [
    *CORE_FIELDS,
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "internalId", "type": ["null", "string"], "default": None},
    {"name": "city", "type": ["null", "string"], "default": None},
    {"name": "address", "type": ["null", "string"], "default": None},
    {"name": "zip", "type": ["null", "string"], "default": None},
    {"name": "region", "type": ["null", "string"], "default": None},
    {"name": "state", "type": ["null", "string"], "default": None},
    {"name": "phone", "type": ["null", "string"], "default": None},
    {"name": "gradeSpan", "type": ["null", "string"], "default": None},
    {"name": "lowGrade", "type": ["null", "string"], "default": None},
    {"name": "highGrade", "type": ["null", "string"], "default": None},
    {"name": "principal", "type": ["null", "string"], "default": None},
    {
        "name": "nonInstructionalAdmins",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="non_instructional_admin", fields=USER_REF_FIELDS
                ),
            },
        ],
    },
    {
        "name": "admins",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="admin", fields=USER_REF_FIELDS),
            },
        ],
    },
    {
        "name": "assistantAdmins",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="assistant_admin", fields=USER_REF_FIELDS
                ),
            },
        ],
    },
    {
        "name": "observationGroups",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observation_group", fields=OBSERVATION_GROUP_FIELDS
                ),
            },
        ],
    },
]

VIDEO_FIELDS = [
    *CORE_FIELDS,
    {"name": "url", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "style", "type": ["null", "string"]},
    {"name": "observations", "type": ["null", {"type": "array", "items": "string"}]},
    {"name": "comments", "type": ["null", {"type": "array", "items": "null"}]},
    {
        "name": "creator",
        "type": ["null", get_avro_record_schema(name="creator", fields=REF_FIELDS)],
    },
    {
        "name": "videoNotes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="video_notes",
                    fields=[
                        {"name": "_id", "type": ["null", "string"]},
                        {"name": "text", "type": ["null", "string"]},
                        {"name": "createdOnMillisecond", "type": ["null", "int"]},
                        {"name": "creator", "type": ["null", "string"]},
                    ],
                ),
            },
        ],
    },
    {
        "name": "users",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="user",
                    fields=[
                        {"name": "user", "type": ["null", "string"]},
                        {"name": "role", "type": ["null", "string"]},
                        {"name": "_id", "type": ["null", "string"], "default": None},
                        {
                            "name": "sharedAt",
                            "type": ["null", "string"],
                            "logicalType": "timestamp-millis",
                            "default": None,
                        },
                    ],
                ),
            },
        ],
    },
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "thumbnail", "type": ["null", "string"], "default": None},
    {"name": "fileName", "type": ["null", "string"], "default": None},
    {"name": "zencoderJobId", "type": ["null", "string"], "default": None},
    {"name": "parent", "type": ["null", "string"], "default": None},
    {"name": "isCollaboration", "type": ["null", "boolean"], "default": None},
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "editors",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "commenters",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
]

PLU_CONFIG_FIELDS = [
    {"name": "required", "type": ["null", "int"], "default": None},
    {
        "name": "startDate",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "endDate",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

USER_TYPE_FIELDS = [
    {"name": "__v", "type": ["null", "int"]},
    {"name": "_id", "type": ["null", "string"]},
    {"name": "abbreviation", "type": ["null", "string"]},
    {"name": "creator", "type": ["null", "string"]},
    {"name": "district", "type": ["null", "string"]},
    {"name": "name", "type": ["null", "string"]},
    {"name": "archivedAt", "type": ["null"]},
    {"name": "created", "type": ["null", "string"], "logicalType": "timestamp-millis"},
    {
        "name": "lastModified",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
    },
]

DISTRICT_DATA_FIELDS = [
    {"name": "district", "type": ["null", "string"]},
    {"name": "showOnDashboards", "type": ["null", "boolean"]},
    {"name": "internalId", "type": ["null", "string"], "default": None},
    {"name": "school", "type": ["null", "string"], "default": None},
    {"name": "grade", "type": ["null", "string"], "default": None},
    {"name": "course", "type": ["null", "string"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "coach", "type": ["null", "string"], "default": None},
    {"name": "usertag1", "type": ["null", "string"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "readonly", "type": ["null", "boolean"], "default": None},
    {"name": "inactive", "type": ["null", "boolean"], "default": None},
    {"name": "nonInstructional", "type": ["null", "boolean"], "default": None},
    {"name": "videoLicense", "type": ["null", "boolean"], "default": None},
    {
        "name": "archivedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "pluConfig",
        "type": [
            "null",
            get_avro_record_schema(
                name="plu_config", namespace="district_data", fields=PLU_CONFIG_FIELDS
            ),
        ],
        "default": None,
    },
    {
        "name": "usertype",
        "type": [
            "null",
            get_avro_record_schema(
                name="usertype",
                namespace="district_data",
                fields=[
                    *USER_TYPE_FIELDS,
                    {
                        "name": "expectations",
                        "type": [
                            "null",
                            get_avro_record_schema(
                                name="expectation",
                                namespace="district_data",
                                fields=[
                                    {"name": "meeting", "type": ["null", "int"]},
                                    {"name": "exceeding", "type": ["null", "int"]},
                                    {
                                        "name": "meetingAggregate",
                                        "type": ["null", "int"],
                                    },
                                    {
                                        "name": "exceedingAggregate",
                                        "type": ["null", "int"],
                                    },
                                    {"name": "summary", "type": ["null"]},
                                ],
                            ),
                        ],
                    },
                ],
            ),
        ],
        "default": None,
    },
]

PREFERENCE_FIELDS = [
    {"name": "timezone", "type": ["null", "int"], "default": None},
    {"name": "timezoneText", "type": ["null", "string"], "default": None},
    {"name": "actionsDashTimeframe", "type": ["null", "string"], "default": None},
    {"name": "homepage", "type": ["null", "string"], "default": None},
    {"name": "showTutorial", "type": ["null", "boolean"], "default": None},
    {"name": "showActionStepMessage", "type": ["null", "boolean"], "default": None},
    {"name": "showDCPSMessage", "type": ["null", "boolean"], "default": None},
    {"name": "showSystemWideMessage", "type": ["null", "boolean"], "default": None},
    {"name": "lastSchoolSelected", "type": ["null", "string"], "default": None},
    {
        "name": "unsubscribedTo",
        "type": ["null", {"type": "array", "items": "string"}],
        "default": None,
    },
    {
        "name": "adminDashboard",
        "type": [
            "null",
            get_avro_record_schema(
                name="admin_dashboard",
                fields=[
                    {
                        "name": "hidden",
                        "type": ["null", {"type": "array", "items": "null"}],
                    }
                ],
            ),
        ],
        "default": None,
    },
    {
        "name": "navBar",
        "type": [
            "null",
            get_avro_record_schema(
                name="nav_bar",
                fields=[
                    {
                        "name": "shortcuts",
                        "type": ["null", {"type": "array", "items": "string"}],
                    }
                ],
            ),
        ],
        "default": None,
    },
    {
        "name": "obsPage",
        "type": [
            "null",
            get_avro_record_schema(
                name="obs_page",
                fields=[
                    {"name": "panelWidth", "type": ["null", "string"]},
                    {
                        "name": "collapsedPanes",
                        "type": ["null", {"type": "array", "items": "string"}],
                        "default": None,
                    },
                ],
            ),
        ],
        "default": None,
    },
]

USER_FIELDS = [
    *CORE_FIELDS,
    {"name": "districts", "type": ["null", {"type": "array", "items": "string"}]},
    {"name": "internalId", "type": ["null", "string"]},
    {"name": "accountingId", "type": ["null", "string"]},
    {"name": "powerSchoolId", "type": ["null", "string"]},
    {"name": "canvasId", "type": ["null", "string"]},
    {"name": "first", "type": ["null", "string"]},
    {"name": "last", "type": ["null", "string"]},
    {"name": "endOfYearVisible", "type": ["null", "boolean"]},
    {"name": "inactive", "type": ["null", "boolean"]},
    {"name": "showOnDashboards", "type": ["null", "boolean"]},
    {"name": "coach", "type": ["null", "string"]},
    {
        "name": "lastActivity",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
    },
    {
        "name": "additionalEmails",
        "type": ["null", {"type": "array", "items": "string"}],
    },
    {"name": "endOfYearLog", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "pastUserTypes", "type": ["null", {"type": "array", "items": "null"}]},
    {
        "name": "roles",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="role", fields=REF_FIELDS),
            },
        ],
    },
    {
        "name": "regionalAdminSchools",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="regional_admin_school", fields=REF_FIELDS
                ),
            },
        ],
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
                        {"name": "id", "type": ["null", "string"]},
                        {"name": "type", "type": ["null", "string"]},
                    ],
                ),
            },
        ],
    },
    {
        "name": "defaultInformation",
        "type": [
            "null",
            get_avro_record_schema(
                name="default_information",
                fields=[
                    {"name": "gradeLevel", "type": ["null", "string"], "default": None},
                    {"name": "school", "type": ["null", "string"], "default": None},
                    {"name": "course", "type": ["null", "string"], "default": None},
                    {"name": "period", "type": ["null", "string"], "default": None},
                ],
            ),
        ],
    },
    {
        "name": "preferences",
        "type": [
            "null",
            get_avro_record_schema(name="preference", fields=PREFERENCE_FIELDS),
        ],
    },
    {"name": "calendarEmail", "type": ["null", "string"], "default": None},
    {"name": "cleverId", "type": ["null", "string"], "default": None},
    {"name": "email", "type": ["null", "string"], "default": None},
    {"name": "googleid", "type": ["null", "string"], "default": None},
    {"name": "isPracticeUser", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "nonInstructional", "type": ["null", "boolean"], "default": None},
    {"name": "oktaId", "type": ["null", "string"], "default": None},
    {"name": "readonly", "type": ["null", "boolean"], "default": None},
    {"name": "sibmeId", "type": ["null", "string"], "default": None},
    {"name": "sibmeToken", "type": ["null", "string"], "default": None},
    {"name": "usertag1", "type": ["null", "string"], "default": None},
    {"name": "usertag2", "type": ["null", "string"], "default": None},
    {"name": "usertag3", "type": ["null", "string"], "default": None},
    {"name": "usertag4", "type": ["null", "string"], "default": None},
    {"name": "usertag5", "type": ["null", "string"], "default": None},
    {"name": "usertag6", "type": ["null", "string"], "default": None},
    {"name": "usertag7", "type": ["null", "string"], "default": None},
    {"name": "usertag8", "type": ["null", "string"], "default": None},
    {"name": "videoLicense", "type": ["null", "boolean"], "default": None},
    {"name": "evaluator", "type": ["null"], "default": None},
    {"name": "track", "type": ["null"], "default": None},
    {
        "name": "usertype",
        "type": [
            "null",
            get_avro_record_schema(
                name="usertype",
                fields=[
                    *USER_TYPE_FIELDS,
                    {
                        "name": "expectations",
                        "type": [
                            "null",
                            get_avro_record_schema(
                                name="expectation",
                                namespace="usertype",
                                fields=[
                                    {"name": "meeting", "type": ["null", "int"]},
                                    {"name": "exceeding", "type": ["null", "int"]},
                                    {
                                        "name": "meetingAggregate",
                                        "type": ["null", "int"],
                                    },
                                    {
                                        "name": "exceedingAggregate",
                                        "type": ["null", "int"],
                                    },
                                    {"name": "summary", "type": ["null"]},
                                ],
                            ),
                        ],
                    },
                ],
            ),
        ],
        "default": None,
    },
    {
        "name": "pluConfig",
        "type": [
            "null",
            get_avro_record_schema(name="plu_config", fields=PLU_CONFIG_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "districtData",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="district_data", fields=DISTRICT_DATA_FIELDS
                ),
            },
        ],
        "default": None,
    },
]

ASSIGNMENT_FIELDS = [
    *CORE_FIELDS,
    {"name": "excludeFromBank", "type": ["null", "boolean"]},
    {"name": "locked", "type": ["null", "boolean"]},
    {"name": "private", "type": ["null", "boolean"]},
    {"name": "coachingActivity", "type": ["null", "boolean"]},
    {"name": "type", "type": ["null", "string"]},
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
    },
    {
        "name": "user",
        "type": ["null", get_avro_record_schema(name="user", fields=USER_REF_FIELDS)],
    },
    {
        "name": "progress",
        "type": [
            "null",
            get_avro_record_schema(
                name="progress",
                fields=[
                    {"name": "percent", "type": ["null", "int"]},
                    {"name": "assigner", "type": ["null", "string"]},
                    {"name": "justification", "type": ["null", "string"]},
                    {
                        "name": "date",
                        "type": ["null", "string"],
                        "logicalType": "timestamp-millis",
                    },
                    {"name": "_id", "type": ["null", "string"], "default": None},
                ],
            ),
        ],
    },
    {
        "name": "tags",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="tag",
                    fields=[
                        *REF_FIELDS,
                        {"name": "url", "type": ["null", "string"], "default": None},
                    ],
                ),
            },
        ],
    },
    {"name": "parent", "type": ["null"], "default": None},
    {"name": "goalType", "type": ["null"], "default": None},
    {
        "name": "observation",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "school",
        "type": [
            "null",
            get_avro_record_schema(name="school", fields=REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "grade",
        "type": [
            "null",
            get_avro_record_schema(name="grade", fields=REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "course",
        "type": [
            "null",
            get_avro_record_schema(name="course", fields=REF_FIELDS),
        ],
        "default": None,
    },
]

OBSERVATION_SCORE_FIELDS = [
    {"name": "measurement", "type": ["null", "string"]},
    {"name": "measurementGroup", "type": ["null", "string"]},
    {"name": "valueText", "type": ["null", "string"]},
    {
        "name": "lastModified",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
    },
    {
        "name": "checkboxes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="checkbox",
                    fields=[
                        {"name": "label", "type": ["null", "string"]},
                        {"name": "value", "type": ["null", "boolean"], "default": None},
                    ],
                ),
            },
        ],
    },
    {
        "name": "textBoxes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="text_box",
                    fields=[
                        {"name": "key", "type": ["null", "string"]},
                        {"name": "value", "type": ["null", "string"]},
                    ],
                ),
            },
        ],
    },
    {"name": "percentage", "type": ["null", "float"], "default": None},
    {"name": "valueScore", "type": ["null", "int"], "default": None},
]

TAG_NOTE_FIELDS = [
    {"name": "notes", "type": ["null", "string"], "default": None},
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "null"}],
        "default": None,
    },
]

ATTACHMENT_FIELDS = [
    {"name": "id", "type": ["null", "string"]},
    {"name": "file", "type": ["null", "string"]},
    {"name": "private", "type": ["null", "boolean"]},
    {"name": "creator", "type": ["null", "string"]},
    {"name": "created", "type": ["null", "string"], "logicalType": "timestamp-millis"},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "resource", "type": ["null", "string"], "default": None},
]

TEACHING_ASSIGNMENT_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "school", "type": ["null", "string"], "default": None},
    {"name": "course", "type": ["null", "string"], "default": None},
    {"name": "grade", "type": ["null", "string"], "default": None},
    {"name": "gradeLevel", "type": ["null", "string"], "default": None},
    {"name": "period", "type": ["null", "string"], "default": None},
]

MAGIC_NOTE_FIELDS = [
    {"name": "_id", "type": ["null", "string"]},
    {"name": "text", "type": ["null", "string"]},
    {"name": "shared", "type": ["null", "boolean"]},
    {"name": "created", "type": ["null", "string"], "logicalType": "timestamp-millis"},
    {"name": "column", "type": ["null"], "default": None},
]

VIDEO_NOTE_FIELDS = [
    {"name": "_id", "type": ["null", "string"]},
    {"name": "text", "type": ["null", "string"]},
    {"name": "timestamp", "type": ["null", "string"]},
    {"name": "creator", "type": ["null", "string"]},
    {"name": "shared", "type": ["null", "boolean"]},
]

OBSERVATION_FIELDS = [
    *CORE_FIELDS,
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "isPublished", "type": ["null", "boolean"]},
    {"name": "locked", "type": ["null", "boolean"]},
    {
        "name": "observedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
    },
    {
        "name": "firstPublished",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
    },
    {
        "name": "meetings",
        "type": ["null", {"type": "array", "items": "string"}],
    },
    {"name": "tags", "type": ["null", {"type": "array", "items": "string"}]},
    {
        "name": "rubric",
        "type": ["null", get_avro_record_schema(name="rubric", fields=REF_FIELDS)],
    },
    {
        "name": "observer",
        "type": [
            "null",
            get_avro_record_schema(name="observer", fields=USER_REF_FIELDS),
        ],
    },
    {
        "name": "teacher",
        "type": [
            "null",
            get_avro_record_schema(name="teacher", fields=USER_REF_FIELDS),
        ],
    },
    {
        "name": "observationScores",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observation_score", fields=OBSERVATION_SCORE_FIELDS
                ),
            },
        ],
    },
    {"name": "observationModule", "type": ["null"], "default": None},
    {"name": "observationtag1", "type": ["null"], "default": None},
    {"name": "observationtag2", "type": ["null"], "default": None},
    {"name": "observationtag3", "type": ["null"], "default": None},
    {"name": "observationType", "type": ["null", "string"], "default": None},
    {"name": "requireSignature", "type": ["null", "boolean"], "default": None},
    {"name": "privateNotes1", "type": ["null", "string"], "default": None},
    {"name": "privateNotes2", "type": ["null", "string"], "default": None},
    {"name": "privateNotes3", "type": ["null", "string"], "default": None},
    {"name": "privateNotes4", "type": ["null", "string"], "default": None},
    {"name": "sharedNotes1", "type": ["null", "string"], "default": None},
    {"name": "sharedNotes2", "type": ["null", "string"], "default": None},
    {"name": "sharedNotes3", "type": ["null", "string"], "default": None},
    {"name": "quickHits", "type": ["null", "string"], "default": None},
    {"name": "assignActionStepWidgetText", "type": ["null", "string"], "default": None},
    {"name": "score", "type": ["null", "float"], "default": None},
    {"name": "scoreAveragedByStrand", "type": ["null", "float"], "default": None},
    {"name": "sendEmail", "type": ["null", "boolean"], "default": None},
    {"name": "signed", "type": ["null", "boolean"], "default": None},
    {
        "name": "observedUntil",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "viewedByTeacher",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "signedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "lastPublished",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
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
    {
        "name": "teachingAssignment",
        "type": [
            "null",
            get_avro_record_schema(
                name="teaching_assignment", fields=TEACHING_ASSIGNMENT_FIELDS
            ),
        ],
        "default": None,
    },
    {
        "name": "magicNotes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="magic_note", fields=MAGIC_NOTE_FIELDS
                ),
            },
        ],
        "default": None,
    },
    {
        "name": "videos",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="video",
                    fields=[
                        {"name": "video", "type": ["null", "string"]},
                        {
                            "name": "includeVideoTimestamps",
                            "type": ["null", "boolean"],
                        },
                    ],
                ),
            },
        ],
        "default": None,
    },
    {
        "name": "videoNotes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="video_note", fields=VIDEO_NOTE_FIELDS
                ),
            },
        ],
        "default": None,
    },
    {
        "name": "attachments",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="attachment", fields=ATTACHMENT_FIELDS
                ),
            },
        ],
        "default": None,
    },
    {
        "name": "tagNotes1",
        "type": [
            "null",
            get_avro_record_schema(name="tag_note_1", fields=TAG_NOTE_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "tagNotes2",
        "type": [
            "null",
            get_avro_record_schema(name="tag_note_2", fields=TAG_NOTE_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "tagNotes3",
        "type": [
            "null",
            get_avro_record_schema(name="tag_note_3", fields=TAG_NOTE_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "tagNotes4",
        "type": [
            "null",
            get_avro_record_schema(name="tag_note_4", fields=TAG_NOTE_FIELDS),
        ],
        "default": None,
    },
]

ENDPOINT_FIELDS = {
    "generic-tags/assignmentpresets": GENERIC_TAG_TYPE_FIELDS,
    "generic-tags/courses": GENERIC_TAG_TYPE_FIELDS,
    "generic-tags/grades": GENERIC_TAG_TYPE_FIELDS,
    "generic-tags/measurementgroups": GENERIC_TAG_TYPE_FIELDS,
    "generic-tags/observationtypes": GENERIC_TAG_TYPE_FIELDS,
    "generic-tags/meetingtypes": GT_MEETINGTYPE_FIELDS,
    "generic-tags/tags": GT_TAG_FIELDS,
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
