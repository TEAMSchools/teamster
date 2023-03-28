def get_avro_record_schema(name: str, fields: list, namespace: str = None):
    return {
        "type": "record",
        "name": f"{name.replace('-', '_').replace('/', '_')}_record",
        "namespace": namespace,
        "fields": fields,
    }


REF_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": ["null", "string"], "default": None},
]

CORE_FIELDS = [
    *REF_FIELDS,
    {"name": "district", "type": ["null", "string"], "default": None},
    {
        "name": "created",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "lastModified",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
]

USER_REF_FIELDS = [
    *REF_FIELDS,
    {"name": "email", "type": "string"},
]

ROLE_FIELDS = [
    *REF_FIELDS,
    {"name": "category", "type": "string"},
    {"name": "district", "type": "string"},
]

GENERIC_TAG_TYPE_FIELDS = [
    *CORE_FIELDS,
    {"name": "__v", "type": "int"},
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
    {"name": "description", "type": "string"},
    {"name": "type", "type": "string"},
    {"name": "isPrivate", "type": "boolean"},
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
                    {"name": "left", "type": "string"},
                    {"name": "right", "type": "string"},
                ],
            ),
        ],
        "default": None,
    },
]

GT_MEETINGTYPE_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "canBePrivate", "type": "boolean"},
    {"name": "canRequireSignature", "type": "boolean"},
    {"name": "coachingEvalType", "type": "string"},
    {"name": "customAbsentCategories", "type": {"type": "array", "items": "null"}},
    {"name": "enableModule", "type": "boolean"},
    {"name": "enableTag1", "type": "boolean"},
    {"name": "enableTag2", "type": "boolean"},
    {"name": "enableTag3", "type": "boolean"},
    {"name": "enableTag4", "type": "boolean"},
    {"name": "isWeeklyDataMeeting", "type": "boolean"},
    {"name": "videoForm", "type": "boolean"},
    {"name": "resources", "type": {"type": "array", "items": "null"}},
    {"name": "excludedModules", "type": {"type": "array", "items": "null"}},
    {"name": "excludedTag1s", "type": {"type": "array", "items": "null"}},
    {"name": "excludedTag2s", "type": {"type": "array", "items": "null"}},
    {"name": "excludedTag3s", "type": {"type": "array", "items": "null"}},
    {"name": "excludedTag4s", "type": {"type": "array", "items": "null"}},
    {"name": "rolesExcluded", "type": {"type": "array", "items": "string"}},
    {"name": "schoolsExcluded", "type": {"type": "array", "items": "null"}},
    {
        "name": "additionalFields",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="additional_field", fields=ADDITIONAL_FIELD_FIELDS
            ),
        },
    },
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "enablePhases", "type": ["null", "boolean"], "default": None},
    {"name": "enableParticipantsCopy", "type": ["null", "boolean"], "default": None},
    {"name": "hideFromLists", "type": ["null", "boolean"], "default": None},
]

GT_TAG_FIELDS = [
    *GENERIC_TAG_TYPE_FIELDS,
    {"name": "parents", "type": {"type": "array", "items": "string"}},
    {"name": "rows", "type": {"type": "array", "items": "null"}},
    {"name": "url", "type": ["null", "string"], "default": None},
]

INFORMAL_FIELDS = [
    *CORE_FIELDS,
    {"name": "shared", "type": "string"},
    {"name": "private", "type": "string"},
    {
        "name": "tags",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="tag", fields=REF_FIELDS),
        },
    },
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
    *CORE_FIELDS,
    {"name": "rowStyle", "type": "string"},
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
]

MEETING_FIELDS = [
    *CORE_FIELDS,
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
        "name": "date",
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
    {"name": "coachActionStep", "type": ["null", "boolean"], "default": None},
    {"name": "customHtml", "type": ["null", "string"], "default": None},
    {"name": "customHtmlTitle", "type": ["null", "string"], "default": None},
    {"name": "dashHidden", "type": ["null", "boolean"], "default": None},
    {"name": "defaultCourse", "type": ["null"], "default": None},
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
    {"name": "observationTypesHidden", "type": ["null", "boolean"], "default": None},
    {"name": "obsShowEndDate", "type": ["null", "boolean"], "default": None},
    {"name": "meetingTypesExcludedFromScheduling", "type": ["null"], "default": None},
    {
        "name": "privateRows",
        "type": ["null", {"type": "array", "items": "string"}],
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
    {"name": "showObservationTag4", "type": ["null", "boolean"], "default": None},
    {"name": "showOnDataReports", "type": ["null", "boolean"], "default": None},
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
]

FORM_FIELDS = [
    {"name": "widgetTitle", "type": "string"},
    {"name": "widgetKey", "type": ["null", "string"]},
    {"name": "widgetDescription", "type": ["null", "string"], "default": None},
    {"name": "assignmentSlug", "type": ["null", "string"], "default": None},
    {"name": "hideOnDraft", "type": ["null", "boolean"], "default": None},
    {"name": "hideOnFinalized", "type": ["null", "boolean"], "default": None},
    {"name": "includeInEmail", "type": ["null", "boolean"], "default": None},
    {"name": "rubricMeasurement", "type": ["null", "string"], "default": None},
    {"name": "showOnFinalizedPopup", "type": ["null", "boolean"], "default": None},
]

LAYOUT_FIELDS = [
    {
        "name": "formLeft",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="form_left", fields=FORM_FIELDS),
        },
    },
    {
        "name": "formWide",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="form_wide", fields=FORM_FIELDS),
        },
    },
]

MEASUREMENT_GROUP_MEASUREMENT_FIELDS = [
    {"name": "measurement", "type": ["null", "string"]},
    {"name": "weight", "type": "int"},
    {"name": "require", "type": "boolean"},
    {"name": "isPrivate", "type": "boolean"},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
    {"name": "exclude", "type": ["null", "boolean"], "default": None},
    {"name": "hideDescription", "type": ["null", "boolean"], "default": None},
]

MEASUREMENT_GROUP_FIELDS = [
    {"name": "name", "type": "string"},
    {"name": "key", "type": "string"},
    {"name": "weight", "type": ["null", "int"], "default": None},
    {"name": "_id", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {
        "name": "measurements",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="measurement", fields=MEASUREMENT_GROUP_MEASUREMENT_FIELDS
            ),
        },
    },
]

RUBRIC_FIELDS = [
    *CORE_FIELDS,
    {"name": "isPrivate", "type": "boolean"},
    {"name": "isPublished", "type": "boolean"},
    {"name": "order", "type": ["null", "int"], "default": None},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {
        "name": "settings",
        "type": get_avro_record_schema(name="setting", fields=SETTING_FIELDS),
    },
    {
        "name": "layout",
        "type": get_avro_record_schema(name="layout", fields=LAYOUT_FIELDS),
    },
    {
        "name": "measurementGroups",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="measurement_group", fields=MEASUREMENT_GROUP_FIELDS
            ),
        },
    },
]

OBSERVATION_GROUP_FIELDS = [
    *REF_FIELDS,
    {
        "name": "observers",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="observer", fields=USER_REF_FIELDS),
        },
    },
    {
        "name": "observees",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="observee", fields=USER_REF_FIELDS),
        },
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
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="non_instructional_admin", fields=USER_REF_FIELDS
            ),
        },
    },
    {
        "name": "admins",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="admin", fields=USER_REF_FIELDS),
        },
    },
    {
        "name": "assistantAdmins",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="assistant_admin", fields=USER_REF_FIELDS
            ),
        },
    },
    {
        "name": "observationGroups",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="observation_group", fields=OBSERVATION_GROUP_FIELDS
            ),
        },
    },
]

VIDEO_FIELDS = [
    *CORE_FIELDS,
    {"name": "url", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "style", "type": "string"},
    {"name": "observations", "type": {"type": "array", "items": "string"}},
    {"name": "comments", "type": {"type": "array", "items": "null"}},
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=REF_FIELDS),
    },
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
        "name": "users",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="user",
                fields=[
                    {"name": "user", "type": "string"},
                    {"name": "role", "type": "string"},
                    {"name": "_id", "type": ["null", "string"], "default": None},
                    {
                        "name": "sharedAt",
                        "type": [
                            "null",
                            {"type": "string", "logicalType": "timestamp-millis"},
                        ],
                        "default": None,
                    },
                ],
            ),
        },
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
        "type": [
            "null",
            {"type": "string", "logicalType": "timestamp-millis"},
        ],
        "default": None,
    },
    {
        "name": "endDate",
        "type": [
            "null",
            {"type": "string", "logicalType": "timestamp-millis"},
        ],
        "default": None,
    },
]

USER_TYPE_FIELDS = [
    {"name": "__v", "type": "int"},
    {"name": "_id", "type": "string"},
    {"name": "abbreviation", "type": "string"},
    {"name": "creator", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "archivedAt", "type": "null"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
]

DISTRICT_DATA_FIELDS = [
    {"name": "district", "type": "string"},
    {"name": "showOnDashboards", "type": "boolean"},
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
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
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
                        "type": get_avro_record_schema(
                            name="expectation",
                            namespace="district_data",
                            fields=[
                                {"name": "meeting", "type": "int"},
                                {"name": "exceeding", "type": "int"},
                                {"name": "meetingAggregate", "type": "int"},
                                {"name": "exceedingAggregate", "type": "int"},
                                {"name": "summary", "type": "null"},
                            ],
                        ),
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
                fields=[{"name": "hidden", "type": {"type": "array", "items": "null"}}],
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
                    {"name": "shortcuts", "type": {"type": "array", "items": "string"}}
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
                    {"name": "panelWidth", "type": "string"},
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
    {"name": "districts", "type": {"type": "array", "items": "string"}},
    {"name": "internalId", "type": ["null", "string"]},
    {"name": "accountingId", "type": ["null", "string"]},
    {"name": "powerSchoolId", "type": ["null", "string"]},
    {"name": "canvasId", "type": ["null", "string"]},
    {"name": "first", "type": ["null", "string"]},
    {"name": "last", "type": ["null", "string"]},
    {"name": "endOfYearVisible", "type": ["null", "boolean"]},
    {"name": "inactive", "type": ["null", "boolean"]},
    {"name": "showOnDashboards", "type": "boolean"},
    {"name": "coach", "type": ["null", "string"]},
    {
        "name": "lastActivity",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "additionalEmails", "type": {"type": "array", "items": "string"}},
    {"name": "endOfYearLog", "type": ["null", {"type": "array", "items": "null"}]},
    {"name": "pastUserTypes", "type": ["null", {"type": "array", "items": "null"}]},
    {
        "name": "roles",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(name="role", fields=REF_FIELDS),
        },
    },
    {
        "name": "regionalAdminSchools",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="regional_admin_school", fields=REF_FIELDS
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
                        {"name": "id", "type": "string"},
                        {"name": "type", "type": "string"},
                    ],
                ),
            },
        ],
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
                        "type": get_avro_record_schema(
                            name="expectation",
                            namespace="usertype",
                            fields=[
                                {"name": "meeting", "type": "int"},
                                {"name": "exceeding", "type": "int"},
                                {"name": "meetingAggregate", "type": "int"},
                                {"name": "exceedingAggregate", "type": "int"},
                                {"name": "summary", "type": "null"},
                            ],
                        ),
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
    {"name": "excludeFromBank", "type": "boolean"},
    {"name": "locked", "type": "boolean"},
    {"name": "private", "type": "boolean"},
    {"name": "coachingActivity", "type": "boolean"},
    {"name": "type", "type": "string"},
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
                {"name": "_id", "type": ["null", "string"], "default": None},
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
                    *REF_FIELDS,
                    {"name": "url", "type": ["null", "string"], "default": None},
                ],
            ),
        },
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
    {"name": "measurement", "type": "string"},
    {"name": "measurementGroup", "type": "string"},
    {"name": "valueText", "type": ["null", "string"]},
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
                    {"name": "value", "type": ["null", "boolean"], "default": None},
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
    {"name": "id", "type": "string"},
    {"name": "file", "type": "string"},
    {"name": "private", "type": "boolean"},
    {"name": "creator", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
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
    {"name": "_id", "type": "string"},
    {"name": "text", "type": "string"},
    {"name": "shared", "type": "boolean"},
    {"name": "created", "type": {"type": "string", "logicalType": "timestamp-millis"}},
    {"name": "column", "type": ["null"], "default": None},
]

VIDEO_NOTE_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "text", "type": "string"},
    {"name": "timestamp", "type": "string"},
    {"name": "creator", "type": "string"},
    {"name": "shared", "type": "boolean"},
]

OBSERVATION_FIELDS = [
    *CORE_FIELDS,
    {"name": "isPrivate", "type": ["null", "boolean"]},
    {"name": "isPublished", "type": "boolean"},
    {"name": "locked", "type": ["null", "boolean"]},
    {
        "name": "observedAt",
        "type": {"type": "string", "logicalType": "timestamp-millis"},
    },
    {
        "name": "firstPublished",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "meetings", "type": {"type": "array", "items": ["null", "string"]}},
    {"name": "tags", "type": {"type": "array", "items": "string"}},
    {
        "name": "rubric",
        "type": get_avro_record_schema(name="rubric", fields=REF_FIELDS),
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
        "name": "observationScores",
        "type": {
            "type": "array",
            "items": get_avro_record_schema(
                name="observation_score", fields=OBSERVATION_SCORE_FIELDS
            ),
        },
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
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
    {
        "name": "viewedByTeacher",
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
        ],
        "default": None,
    },
    {
        "name": "videoNotes",
        "type": [
            "null",
            {
                "type": "array",
                "items": [
                    "null",
                    get_avro_record_schema(name="video_note", fields=VIDEO_NOTE_FIELDS),
                ],
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
                "items": [
                    "null",
                    get_avro_record_schema(name="attachment", fields=ATTACHMENT_FIELDS),
                ],
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
