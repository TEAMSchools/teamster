from teamster.core.utils.functions import get_avro_record_schema

REF_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
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
    {"name": "email", "type": ["null", "string"], "default": None},
]

ROLE_FIELDS = [
    *REF_FIELDS,
    {"name": "category", "type": ["null", "string"], "default": None},
    {"name": "district", "type": ["null", "string"], "default": None},
]

GENERIC_TAG_TYPE_FIELDS = [
    *CORE_FIELDS,
    {"name": "__v", "type": ["null", "int"], "default": None},
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "color", "type": ["null", "string"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "parent", "type": ["null", "string"], "default": None},
    {"name": "showOnDash", "type": ["null", "boolean"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

CONTENT_FIELDS = [
    {"name": "left", "type": ["null", "string"], "default": None},
    {"name": "right", "type": ["null", "string"], "default": None},
]

ADDITIONAL_FIELD_FIELDS = [
    *REF_FIELDS,
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "enableParticipantsCopy", "type": ["null", "boolean"], "default": None},
    {"name": "hiddenUntilMeetingStart", "type": ["null", "boolean"], "default": None},
    {"name": "isPrivate", "type": ["null", "boolean"], "default": None},
    {"name": "leftName", "type": ["null", "string"], "default": None},
    {"name": "rightName", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {
        "name": "content",
        "type": [
            "null",
            "string",
            "int",
            "boolean",
            get_avro_record_schema(name="content", fields=CONTENT_FIELDS),
        ],
        "default": None,
    },
]

GT_MEETINGTYPE_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "canBePrivate", "type": ["null", "boolean"], "default": None},
    {"name": "canRequireSignature", "type": ["null", "boolean"], "default": None},
    {"name": "coachingEvalType", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "enableModule", "type": ["null", "boolean"], "default": None},
    {"name": "enableParticipantsCopy", "type": ["null", "boolean"], "default": None},
    {"name": "enablePhases", "type": ["null", "boolean"], "default": None},
    {"name": "enableTag1", "type": ["null", "boolean"], "default": None},
    {"name": "enableTag2", "type": ["null", "boolean"], "default": None},
    {"name": "enableTag3", "type": ["null", "boolean"], "default": None},
    {"name": "enableTag4", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromLists", "type": ["null", "boolean"], "default": None},
    {"name": "isWeeklyDataMeeting", "type": ["null", "boolean"], "default": None},
    {"name": "videoForm", "type": ["null", "boolean"], "default": None},
    {
        "name": "excludedModules",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "excludedTag1s",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "excludedTag2s",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "excludedTag3s",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "excludedTag4s",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "resources",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "rolesExcluded",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "schoolsExcluded",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "customAbsentCategories",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
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
]

GT_TAG_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "url", "type": ["null", "string"], "default": None},
    {
        "name": "parents",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "rows",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

INFORMAL_FIELDS = [
    *CORE_FIELDS,
    {"name": "shared", "type": ["null", "string"], "default": None},
    {"name": "private", "type": ["null", "string"], "default": None},
    {
        "name": "tags",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="tag", fields=REF_FIELDS),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "user",
        "type": ["null", get_avro_record_schema(name="user", fields=USER_REF_FIELDS)],
        "default": None,
    },
]

TEXT_BOX_FIELDS = [
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "label", "type": ["null", "string"], "default": None},
]

MEASUREMENT_OPTION_FIELDS = [
    {"name": "label", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "int"], "default": None},
    {"name": "percentage", "type": ["null", "float"], "default": None},
    {
        "name": "created",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

MEASUREMENT_FIELDS = [
    *CORE_FIELDS,
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "rowStyle", "type": ["null", "string"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {
        "name": "textBoxes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="text_box", fields=TEXT_BOX_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "measurementOptions",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement_option", fields=MEASUREMENT_OPTION_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

PARTICIPANT_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "customCategory", "type": ["null", "string"], "default": None},
    {"name": "isAbsent", "type": ["null", "boolean"], "default": None},
    {"name": "user", "type": ["null", "string"], "default": None},
]

TYPE_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "canBePrivate", "type": ["null", "boolean"], "default": None},
    {"name": "canRequireSignature", "type": ["null", "boolean"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
]

MEETING_FIELDS = [
    *CORE_FIELDS,
    {"name": "course", "type": ["null", "string"], "default": None},
    {"name": "enablePhases", "type": ["null", "boolean"], "default": None},
    {"name": "grade", "type": ["null", "string"], "default": None},
    {"name": "isOpenToParticipants", "type": ["null", "boolean"], "default": None},
    {"name": "isTemplate", "type": ["null", "boolean"], "default": None},
    {"name": "isWeeklyDataMeeting", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "meetingtag1", "type": ["null", "string"], "default": None},
    {"name": "meetingtag2", "type": ["null", "string"], "default": None},
    {"name": "meetingtag3", "type": ["null", "string"], "default": None},
    {"name": "meetingtag4", "type": ["null", "string"], "default": None},
    {"name": "private", "type": ["null", "boolean"], "default": None},
    {"name": "school", "type": ["null", "string"], "default": None},
    {"name": "signatureRequired", "type": ["null", "boolean"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {
        "name": "observations",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
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
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "offweek",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "unable",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "participants",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="participant", fields=PARTICIPANT_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "type",
        "type": [
            "null",
            get_avro_record_schema(name="type", fields=TYPE_FIELDS),
        ],
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
]

FEATURE_INSTRUCTION_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "hideOnDraft", "type": ["null", "boolean"], "default": None},
    {"name": "hideOnFinalized", "type": ["null", "boolean"], "default": None},
    {"name": "includeOnEmails", "type": ["null", "boolean"], "default": None},
    {"name": "section", "type": ["null", "string"], "default": None},
    {"name": "text", "type": ["null", "string"], "default": None},
    {"name": "titleOverride", "type": ["null", "string"], "default": None},
]

RESOURCE_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "label", "type": ["null", "string"], "default": None},
    {"name": "url", "type": ["null", "string"], "default": None},
]

SETTING_FIELDS = [
    {"name": "actionStep", "type": ["null", "boolean"], "default": None},
    {"name": "actionStepCreate", "type": ["null", "boolean"], "default": None},
    {"name": "actionStepWorkflow", "type": ["null", "boolean"], "default": None},
    {"name": "allowCoTeacher", "type": ["null", "boolean"], "default": None},
    {"name": "allowTakeOverObservation", "type": ["null", "boolean"], "default": None},
    {"name": "cloneable", "type": ["null", "boolean"], "default": None},
    {"name": "coachActionStep", "type": ["null", "boolean"], "default": None},
    {"name": "coachingEvalType", "type": ["null", "string"], "default": None},
    {"name": "customHtml", "type": ["null", "string"], "default": None},
    {"name": "customHtml1", "type": ["null", "string"], "default": None},
    {"name": "customHtml2", "type": ["null", "string"], "default": None},
    {"name": "customHtml3", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle1", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle2", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle3", "type": ["null", "string"], "default": None},
    {"name": "dashHidden", "type": ["null", "boolean"], "default": None},
    {"name": "debrief", "type": ["null", "boolean"], "default": None},
    {"name": "defaultCourse", "type": ["null", "string"], "default": None},
    {"name": "defaultObsModule", "type": ["null", "string"], "default": None},
    {"name": "defaultObsTag1", "type": ["null", "string"], "default": None},
    {"name": "defaultObsTag2", "type": ["null", "string"], "default": None},
    {"name": "defaultObsTag3", "type": ["null", "string"], "default": None},
    {"name": "defaultObsTag4", "type": ["null", "string"], "default": None},
    {"name": "defaultObsType", "type": ["null", "string"], "default": None},
    {"name": "defaultUsertype", "type": ["null", "string"], "default": None},
    {"name": "descriptionsInEditor", "type": ["null", "boolean"], "default": None},
    {"name": "disableMeetingsTab", "type": ["null", "boolean"], "default": None},
    {"name": "displayLabels", "type": ["null", "boolean"], "default": None},
    {"name": "displayNumbers", "type": ["null", "boolean"], "default": None},
    {"name": "enableClickToFill", "type": ["null", "boolean"], "default": None},
    {"name": "enablePointClick", "type": ["null", "boolean"], "default": None},
    {"name": "filters", "type": ["null", "boolean"], "default": None},
    {"name": "goalCreate", "type": ["null", "boolean"], "default": None},
    {"name": "goals", "type": ["null", "boolean"], "default": None},
    {"name": "hasCompletionMarks", "type": ["null", "boolean"], "default": None},
    {"name": "hasRowDescriptions", "type": ["null", "boolean"], "default": None},
    {"name": "hideEmptyRows", "type": ["null", "boolean"], "default": None},
    {"name": "hideEmptyTextRows", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromCoaches", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromLists", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromRegionalCoaches", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromSchoolAdmins", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromTeachers", "type": ["null", "boolean"], "default": None},
    {"name": "hideOverallScore", "type": ["null", "boolean"], "default": None},
    {"name": "isAlwaysFocus", "type": ["null", "boolean"], "default": None},
    {"name": "isCoachingStartForm", "type": ["null", "boolean"], "default": None},
    {"name": "isCompetencyRubric", "type": ["null", "boolean"], "default": None},
    {"name": "isHolisticDefault", "type": ["null", "boolean"], "default": None},
    {"name": "isPeerRubric", "type": ["null", "boolean"], "default": None},
    {"name": "isPrivate", "type": ["null", "boolean"], "default": None},
    {"name": "isScorePrivate", "type": ["null", "boolean"], "default": None},
    {"name": "isSiteVisit", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "lockScoreAfterDays", "type": ["null", "int", "string"], "default": None},
    {"name": "meetingQuickCreate", "type": ["null", "boolean"], "default": None},
    {
        "name": "meetingTypesExcludedFromScheduling",
        "type": ["null", "string"],
        "default": None,
    },
    {"name": "nameAndSignatureDisplay", "type": ["null", "boolean"], "default": None},
    {"name": "notification", "type": ["null", "boolean"], "default": None},
    {"name": "obsShowEndDate", "type": ["null", "boolean"], "default": None},
    {"name": "obsTypeFinalize", "type": ["null", "boolean"], "default": None},
    {"name": "prepopulateActionStep", "type": ["null", "string"], "default": None},
    {"name": "quickHits", "type": ["null", "string"], "default": None},
    {"name": "requireAll", "type": ["null", "boolean"], "default": None},
    {"name": "requireGoal", "type": ["null", "boolean"], "default": None},
    {"name": "requireObservationType", "type": ["null", "boolean"], "default": None},
    {"name": "requireOnlyScores", "type": ["null", "boolean"], "default": None},
    {"name": "rubrictag1", "type": ["null", "string"], "default": None},
    {"name": "scoreOnForm", "type": ["null", "boolean"], "default": None},
    {"name": "scoreOverride", "type": ["null", "boolean"], "default": None},
    {"name": "scripting", "type": ["null", "boolean"], "default": None},
    {"name": "sendEmailOnSignature", "type": ["null", "boolean"], "default": None},
    {"name": "showAllTextOnOpts", "type": ["null", "boolean"], "default": None},
    {"name": "showAvgByStrand", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationLabels", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationModule", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationTag1", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationTag2", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationTag3", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationTag4", "type": ["null", "boolean"], "default": None},
    {"name": "showObservationType", "type": ["null", "boolean"], "default": None},
    {"name": "showOnDataReports", "type": ["null", "boolean"], "default": None},
    {"name": "showStrandScores", "type": ["null", "boolean"], "default": None},
    {"name": "signature", "type": ["null", "boolean"], "default": None},
    {"name": "signatureOnByDefault", "type": ["null", "boolean"], "default": None},
    {"name": "useAdditiveScoring", "type": ["null", "boolean"], "default": None},
    {"name": "useStrandWeights", "type": ["null", "boolean"], "default": None},
    {"name": "video", "type": ["null", "boolean"], "default": None},
    {"name": "videoForm", "type": ["null", "boolean"], "default": None},
    {
        "name": "requireActionStepBeforeFinalize",
        "type": ["null", "boolean"],
        "default": None,
    },
    {
        "name": "rolesExcluded",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "transferDescriptionToTextbox",
        "type": ["null", "boolean"],
        "default": None,
    },
    {
        "name": "dontRequireTextboxesOnLikertRows",
        "type": ["null", "boolean"],
        "default": None,
    },
    {
        "name": "hiddenFeatures",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "hideFromSchoolAssistantAdmins",
        "type": ["null", "boolean"],
        "default": None,
    },
    {
        "name": "privateRows",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "observationTypesHidden",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "requiredRows",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "schoolsExcluded",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "featureInstructions",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="feature_instruction", fields=FEATURE_INSTRUCTION_FIELDS
                ),
                "default": [],
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
                    name="resource", fields=RESOURCE_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

FORM_FIELDS = [
    {"name": "assignmentSlug", "type": ["null", "string"], "default": None},
    {"name": "hideOnDraft", "type": ["null", "boolean"], "default": None},
    {"name": "hideOnFinalized", "type": ["null", "boolean"], "default": None},
    {"name": "includeInEmail", "type": ["null", "boolean"], "default": None},
    {"name": "mustBeMainPanel", "type": ["null", "boolean"], "default": None},
    {"name": "rubricMeasurement", "type": ["null", "string"], "default": None},
    {"name": "showOnFinalizedPopup", "type": ["null", "boolean"], "default": None},
    {"name": "widgetDescription", "type": ["null", "string"], "default": None},
    {"name": "widgetKey", "type": ["null", "string"], "default": None},
    {"name": "widgetTitle", "type": ["null", "string"], "default": None},
]

LAYOUT_FIELDS = [
    {
        "name": "formLeft",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="form_left", fields=FORM_FIELDS),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "formWide",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="form_wide", fields=FORM_FIELDS),
                "default": [],
            },
        ],
        "default": None,
    },
]

MEASUREMENT_GROUP_MEASUREMENT_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "exclude", "type": ["null", "boolean"], "default": None},
    {"name": "hideDescription", "type": ["null", "boolean"], "default": None},
    {"name": "isPrivate", "type": ["null", "boolean"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "measurement", "type": ["null", "string"], "default": None},
    {"name": "require", "type": ["null", "boolean"], "default": None},
    {"name": "weight", "type": ["null", "int"], "default": None},
]

MEASUREMENT_GROUP_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "weight", "type": ["null", "int"], "default": None},
    {
        "name": "measurements",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="measurement", fields=MEASUREMENT_GROUP_MEASUREMENT_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

RUBRIC_FIELDS = [
    *CORE_FIELDS,
    {"name": "isPrivate", "type": ["null", "boolean"], "default": None},
    {"name": "isPublished", "type": ["null", "boolean"], "default": None},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {
        "name": "settings",
        "type": ["null", get_avro_record_schema(name="setting", fields=SETTING_FIELDS)],
        "default": None,
    },
    {
        "name": "layout",
        "type": ["null", get_avro_record_schema(name="layout", fields=LAYOUT_FIELDS)],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
    },
]

SCHOOL_FIELDS = [
    *CORE_FIELDS,
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "address", "type": ["null", "string"], "default": None},
    {"name": "city", "type": ["null", "string"], "default": None},
    {"name": "gradeSpan", "type": ["null", "string"], "default": None},
    {"name": "highGrade", "type": ["null", "string"], "default": None},
    {"name": "internalId", "type": ["null", "string"], "default": None},
    {"name": "lowGrade", "type": ["null", "string"], "default": None},
    {"name": "phone", "type": ["null", "string"], "default": None},
    {"name": "principal", "type": ["null", "string"], "default": None},
    {"name": "region", "type": ["null", "string"], "default": None},
    {"name": "state", "type": ["null", "string"], "default": None},
    {"name": "zip", "type": ["null", "string"], "default": None},
    {
        "name": "nonInstructionalAdmins",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="non_instructional_admin", fields=USER_REF_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "admins",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="admin", fields=USER_REF_FIELDS),
                "default": [],
            },
        ],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
    },
]

VIDEO_NOTE_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "createdOnMillisecond", "type": ["null", "int"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "text", "type": ["null", "string"], "default": None},
]

VIDEO_USER_FIELDS = [
    {"name": "user", "type": ["null", "string"], "default": None},
    {"name": "role", "type": ["null", "string"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {
        "name": "sharedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

VIDEO_FIELDS = [
    *CORE_FIELDS,
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "fileName", "type": ["null", "string"], "default": None},
    {"name": "isCollaboration", "type": ["null", "boolean"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "parent", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "style", "type": ["null", "string"], "default": None},
    {"name": "thumbnail", "type": ["null", "string"], "default": None},
    {"name": "url", "type": ["null", "string"], "default": None},
    {"name": "zencoderJobId", "type": ["null", "string"], "default": None},
    {
        "name": "observations",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "comments",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "editors",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "commenters",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "creator",
        "type": ["null", get_avro_record_schema(name="creator", fields=REF_FIELDS)],
        "default": None,
    },
    {
        "name": "videoNotes",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="video_notes", fields=VIDEO_NOTE_FIELDS
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "users",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="user", fields=VIDEO_USER_FIELDS),
                "default": [],
            },
        ],
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
    {"name": "__v", "type": ["null", "int"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "abbreviation", "type": ["null", "string"], "default": None},
    {"name": "archivedAt", "type": ["null", "string"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "district", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
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
]

EXPECTATION_FIELDS = [
    {"name": "meeting", "type": ["null", "int"], "default": None},
    {"name": "exceeding", "type": ["null", "int"], "default": None},
    {"name": "meetingAggregate", "type": ["null", "int"], "default": None},
    {"name": "exceedingAggregate", "type": ["null", "int"], "default": None},
    {"name": "summary", "type": ["null", "string"], "default": None},
]

DISTRICT_DATA_USERTYPE_FIELDS = [
    *USER_TYPE_FIELDS,
    {
        "name": "expectations",
        "type": [
            "null",
            get_avro_record_schema(
                name="expectation", namespace="district_data", fields=EXPECTATION_FIELDS
            ),
        ],
        "default": None,
    },
]

DISTRICT_DATA_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "coach", "type": ["null", "string"], "default": None},
    {"name": "course", "type": ["null", "string"], "default": None},
    {"name": "district", "type": ["null", "string"], "default": None},
    {"name": "grade", "type": ["null", "string"], "default": None},
    {"name": "inactive", "type": ["null", "boolean"], "default": None},
    {"name": "internalId", "type": ["null", "string"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "nonInstructional", "type": ["null", "boolean"], "default": None},
    {"name": "readonly", "type": ["null", "boolean"], "default": None},
    {"name": "school", "type": ["null", "string"], "default": None},
    {"name": "showOnDashboards", "type": ["null", "boolean"], "default": None},
    {"name": "usertag1", "type": ["null", "string"], "default": None},
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
                fields=DISTRICT_DATA_USERTYPE_FIELDS,
            ),
        ],
        "default": None,
    },
]

PREFERENCE_FIELDS = [
    {"name": "actionsDashTimeframe", "type": ["null", "string"], "default": None},
    {"name": "homepage", "type": ["null", "string"], "default": None},
    {"name": "lastSchoolSelected", "type": ["null", "string"], "default": None},
    {"name": "showActionStepMessage", "type": ["null", "boolean"], "default": None},
    {"name": "showDCPSMessage", "type": ["null", "boolean"], "default": None},
    {"name": "showSystemWideMessage", "type": ["null", "boolean"], "default": None},
    {"name": "showTutorial", "type": ["null", "boolean"], "default": None},
    {"name": "timezone", "type": ["null", "int"], "default": None},
    {"name": "timezoneText", "type": ["null", "string"], "default": None},
    {
        "name": "unsubscribedTo",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
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
                        "type": [
                            "null",
                            {"type": "array", "items": "string", "default": []},
                        ],
                        "default": None,
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
                        "type": [
                            "null",
                            {"type": "array", "items": "string", "default": []},
                        ],
                        "default": None,
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
                    {"name": "panelWidth", "type": ["null", "string"], "default": None},
                    {
                        "name": "collapsedPanes",
                        "type": [
                            "null",
                            {"type": "array", "items": "string", "default": []},
                        ],
                        "default": None,
                    },
                ],
            ),
        ],
        "default": None,
    },
]

USER_EXPECTATION_FIELDS = [
    {"name": "meeting", "type": ["null", "int"], "default": None},
    {"name": "exceeding", "type": ["null", "int"], "default": None},
    {"name": "meetingAggregate", "type": ["null", "int"], "default": None},
    {"name": "exceedingAggregate", "type": ["null", "int"], "default": None},
    {"name": "summary", "type": ["null", "string"], "default": None},
]

USER_USERTYPE_FIELDS = [
    *USER_TYPE_FIELDS,
    {
        "name": "expectations",
        "type": [
            "null",
            get_avro_record_schema(
                name="expectation", namespace="usertype", fields=USER_EXPECTATION_FIELDS
            ),
        ],
        "default": None,
    },
]

USER_FIELDS = [
    *CORE_FIELDS,
    {"name": "accountingId", "type": ["null", "string"], "default": None},
    {"name": "calendarEmail", "type": ["null", "string"], "default": None},
    {"name": "canvasId", "type": ["null", "string"], "default": None},
    {"name": "cleverId", "type": ["null", "string"], "default": None},
    {"name": "coach", "type": ["null", "string"], "default": None},
    {"name": "email", "type": ["null", "string"], "default": None},
    {"name": "endOfYearVisible", "type": ["null", "boolean"], "default": None},
    {"name": "evaluator", "type": ["null", "string"], "default": None},
    {"name": "first", "type": ["null", "string"], "default": None},
    {"name": "googleid", "type": ["null", "string"], "default": None},
    {"name": "inactive", "type": ["null", "boolean"], "default": None},
    {"name": "internalId", "type": ["null", "string"], "default": None},
    {"name": "isPracticeUser", "type": ["null", "boolean"], "default": None},
    {"name": "last", "type": ["null", "string"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "nonInstructional", "type": ["null", "boolean"], "default": None},
    {"name": "oktaId", "type": ["null", "string"], "default": None},
    {"name": "powerSchoolId", "type": ["null", "string"], "default": None},
    {"name": "readonly", "type": ["null", "boolean"], "default": None},
    {"name": "showOnDashboards", "type": ["null", "boolean"], "default": None},
    {"name": "sibmeId", "type": ["null", "string"], "default": None},
    {"name": "sibmeToken", "type": ["null", "string"], "default": None},
    {"name": "track", "type": ["null", "string"], "default": None},
    {"name": "usertag1", "type": ["null", "string"], "default": None},
    {"name": "usertag2", "type": ["null", "string"], "default": None},
    {"name": "usertag3", "type": ["null", "string"], "default": None},
    {"name": "usertag4", "type": ["null", "string"], "default": None},
    {"name": "usertag5", "type": ["null", "string"], "default": None},
    {"name": "usertag6", "type": ["null", "string"], "default": None},
    {"name": "usertag7", "type": ["null", "string"], "default": None},
    {"name": "usertag8", "type": ["null", "string"], "default": None},
    {"name": "videoLicense", "type": ["null", "boolean"], "default": None},
    {
        "name": "districts",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "lastActivity",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "additionalEmails",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "endOfYearLog",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "pastUserTypes",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "roles",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(name="role", fields=REF_FIELDS),
                "default": [],
            },
        ],
        "default": None,
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
                "default": [],
            },
        ],
        "default": None,
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
                        {"name": "id", "type": ["null", "string"], "default": None},
                        {"name": "type", "type": ["null", "string"], "default": None},
                    ],
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "defaultInformation",
        "type": [
            "null",
            get_avro_record_schema(
                name="default_information",
                fields=[
                    {"name": "course", "type": ["null", "string"], "default": None},
                    {"name": "gradeLevel", "type": ["null", "string"], "default": None},
                    {"name": "period", "type": ["null", "string"], "default": None},
                    {"name": "school", "type": ["null", "string"], "default": None},
                ],
            ),
        ],
        "default": None,
    },
    {
        "name": "preferences",
        "type": [
            "null",
            get_avro_record_schema(name="preference", fields=PREFERENCE_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "usertype",
        "type": [
            "null",
            get_avro_record_schema(name="usertype", fields=USER_USERTYPE_FIELDS),
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
                "default": [],
            },
        ],
        "default": None,
    },
]

PROGRESS_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "assigner", "type": ["null", "string"], "default": None},
    {"name": "justification", "type": ["null", "string"], "default": None},
    {"name": "percent", "type": ["null", "int"], "default": None},
    {
        "name": "date",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

ASSIGNMENT_FIELDS = [
    *CORE_FIELDS,
    {"name": "coachingActivity", "type": ["null", "boolean"], "default": None},
    {"name": "excludeFromBank", "type": ["null", "boolean"], "default": None},
    {"name": "goalType", "type": ["null", "string"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "parent", "type": ["null", "string"], "default": None},
    {"name": "private", "type": ["null", "boolean"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {
        "name": "observation",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "user",
        "type": ["null", get_avro_record_schema(name="user", fields=USER_REF_FIELDS)],
        "default": None,
    },
    {
        "name": "creator",
        "type": [
            "null",
            get_avro_record_schema(name="creator", fields=USER_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "progress",
        "type": [
            "null",
            get_avro_record_schema(name="progress", fields=PROGRESS_FIELDS),
        ],
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
                "default": [],
            },
        ],
        "default": None,
    },
]

OBSERVATION_SCORE_FIELDS = [
    {"name": "measurement", "type": ["null", "string"], "default": None},
    {"name": "measurementGroup", "type": ["null", "string"], "default": None},
    {"name": "percentage", "type": ["null", "float"], "default": None},
    {"name": "valueScore", "type": ["null", "int"], "default": None},
    {"name": "valueText", "type": ["null", "string"], "default": None},
    {
        "name": "lastModified",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
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
                        {"name": "label", "type": ["null", "string"], "default": None},
                        {"name": "value", "type": ["null", "boolean"], "default": None},
                    ],
                ),
                "default": [],
            },
        ],
        "default": None,
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
                        {"name": "key", "type": ["null", "string"], "default": None},
                        {"name": "value", "type": ["null", "string"], "default": None},
                    ],
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

TAG_NOTE_FIELDS = [
    {"name": "notes", "type": ["null", "string"], "default": None},
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

ATTACHMENT_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "file", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "private", "type": ["null", "boolean"], "default": None},
    {"name": "resource", "type": ["null", "string"], "default": None},
    {
        "name": "created",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
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
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "column", "type": ["null", "string"], "default": None},
    {"name": "shared", "type": ["null", "boolean"], "default": None},
    {"name": "text", "type": ["null", "string"], "default": None},
    {
        "name": "created",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
]

VIDEO_NOTE_FIELDS = [
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "creator", "type": ["null", "string"], "default": None},
    {"name": "shared", "type": ["null", "boolean"], "default": None},
    {"name": "text", "type": ["null", "string"], "default": None},
    {"name": "timestamp", "type": ["null", "string"], "default": None},
]

OBSERVATION_FIELDS = [
    *CORE_FIELDS,
    {"name": "assignActionStepWidgetText", "type": ["null", "string"], "default": None},
    {"name": "isPrivate", "type": ["null", "boolean"], "default": None},
    {"name": "isPublished", "type": ["null", "boolean"], "default": None},
    {"name": "locked", "type": ["null", "boolean"], "default": None},
    {"name": "observationModule", "type": ["null", "string"], "default": None},
    {"name": "observationtag1", "type": ["null", "string"], "default": None},
    {"name": "observationtag2", "type": ["null", "string"], "default": None},
    {"name": "observationtag3", "type": ["null", "string"], "default": None},
    {"name": "observationType", "type": ["null", "string"], "default": None},
    {"name": "privateNotes1", "type": ["null", "string"], "default": None},
    {"name": "privateNotes2", "type": ["null", "string"], "default": None},
    {"name": "privateNotes3", "type": ["null", "string"], "default": None},
    {"name": "privateNotes4", "type": ["null", "string"], "default": None},
    {"name": "quickHits", "type": ["null", "string"], "default": None},
    {"name": "requireSignature", "type": ["null", "boolean"], "default": None},
    {"name": "score", "type": ["null", "float"], "default": None},
    {"name": "scoreAveragedByStrand", "type": ["null", "float"], "default": None},
    {"name": "sendEmail", "type": ["null", "boolean"], "default": None},
    {"name": "sharedNotes1", "type": ["null", "string"], "default": None},
    {"name": "sharedNotes2", "type": ["null", "string"], "default": None},
    {"name": "sharedNotes3", "type": ["null", "string"], "default": None},
    {"name": "signed", "type": ["null", "boolean"], "default": None},
    {
        "name": "observedAt",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
    {
        "name": "firstPublished",
        "type": ["null", "string"],
        "logicalType": "timestamp-millis",
        "default": None,
    },
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
        "name": "meetings",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "tags",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "comments",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "listTwoColumnA",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "listTwoColumnB",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "listTwoColumnAPaired",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "listTwoColumnBPaired",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "eventLog",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "files",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "rubric",
        "type": ["null", get_avro_record_schema(name="rubric", fields=REF_FIELDS)],
        "default": None,
    },
    {
        "name": "observer",
        "type": [
            "null",
            get_avro_record_schema(name="observer", fields=USER_REF_FIELDS),
        ],
        "default": None,
    },
    {
        "name": "teacher",
        "type": [
            "null",
            get_avro_record_schema(name="teacher", fields=USER_REF_FIELDS),
        ],
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
        "name": "observationScores",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observation_score", fields=OBSERVATION_SCORE_FIELDS
                ),
                "default": [],
            },
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
                "default": [],
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
                "default": [],
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
                "default": [],
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
    {
        "name": "videos",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="video",
                    fields=[
                        {"name": "video", "type": ["null", "string"], "default": None},
                        {
                            "name": "includeVideoTimestamps",
                            "type": ["null", "boolean"],
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
