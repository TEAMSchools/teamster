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

USER_REF_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": "string"},
]

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
    # {"name": "showOnDash", "type": "boolean"},
    # {"name": "color", "type": "string"},
    # {"name": "parent", "type": "null"},
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
    {"name": "description", "type": "string"},
    {"name": "district", "type": "string"},
    {"name": "scaleMin", "type": ["null", "int"], "default": None},
    {"name": "scaleMax", "type": ["null", "int"], "default": None},
    {"name": "rowStyle", "type": "string"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
        "default": None,
    },
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
    # {"name": "sortId", "type": "string"},
    # {"name": "isPercentage", "type": "boolean"},
    # {"name": "measurementType", "type": "null"},
    # {"name": "measurementGroups", "type": {"type": "array", "items": "null"}},
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
        "type": ["null", {"type": "array", "items": "null", "default": []}],
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
                            "type": ["null", "string"],
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
                {
                    "name": "hiddenFeatures",
                    "type": ["null", {"type": "array", "items": "string"}],
                },
                {"name": "hideFromLists", "type": "boolean"},
                {"name": "hideOverallScore", "type": "boolean"},
                {"name": "isPrivate", "type": "boolean"},
                {"name": "isScorePrivate", "type": "boolean"},
                {"name": "lockScoreAfterDays", "type": ["int", "string"]},
                {"name": "notification", "type": "boolean"},
                {"name": "obsTypeFinalize", "type": "boolean"},
                {"name": "prepopulateActionStep", "type": "null"},
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
                    {"name": "_id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "key", "type": "string"},
                    {
                        "name": "measurements",
                        "type": {
                            "type": "array",
                            "items": get_avro_record_schema(
                                name="measurement",
                                fields=[
                                    {"name": "_id", "type": "string"},
                                    {"name": "isPrivate", "type": "boolean"},
                                    {"name": "measurement", "type": ["null", "string"]},
                                    {"name": "require", "type": "boolean"},
                                    {"name": "weight", "type": "int"},
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
                                    {
                                        "name": "key",
                                        "type": ["null", "string"],
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
    # {"name": "scoringMethod", "type": "string"},
    # {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    # {"name": "_measurementGroups", "type": "null"},
    # {"name": "measurements", "type": "array", "items": "string"},
]

{
    "actionStep": False,
    "actionStepCreate": True,
    "actionStepWorkflow": False,
    "allowCoTeacher": False,
    "allowTakeOverObservation": True,
    "cloneable": False,
    "coachActionStep": False,
    "coachingEvalType": "coaching",
    "dashHidden": False,
    "debrief": False,
    "defaultObsModule": None,
    "defaultObsTag1": None,
    "defaultObsTag2": None,
    "defaultObsTag3": None,
    "defaultObsTag4": None,
    "defaultObsType": None,
    "descriptionsInEditor": False,
    "disableMeetingsTab": False,
    "displayLabels": True,
    "displayNumbers": True,
    "dontRequireTextboxesOnLikertRows": False,
    "enablePointClick": True,
    "filters": False,
    "goalCreate": False,
    "goals": False,
    "hasCompletionMarks": False,
    "hasRowDescriptions": False,
    "hiddenFeatures": None,
    "hideEmptyRows": False,
    "hideEmptyTextRows": False,
    "hideFromLists": False,
    "hideOverallScore": False,
    "isHolisticDefault": False,
    "isPeerRubric": False,
    "isPrivate": False,
    "isScorePrivate": False,
    "locked": False,
    "lockScoreAfterDays": "365",
    "meetingTypesExcludedFromScheduling": None,
    "notification": True,
    "observationTypesHidden": None,
    "obsShowEndDate": False,
    "obsTypeFinalize": False,
    "prepopulateActionStep": None,
    "quickHits": None,
    "requireActionStepBeforeFinalize": False,
    "requireAll": False,
    "requireGoal": False,
    "requireOnlyScores": False,
    "resources": None,
    "rolesExcluded": ["5eed577a2bdac8bef766773b", "5eed577a2bdac8bef766791d"],
    "rubrictag1": "5f2ab49d10be6f0011fd3037",
    "schoolsExcluded": [],
    "scoreOnForm": False,
    "scoreOverride": False,
    "scripting": False,
    "sendEmailOnSignature": False,
    "showAllTextOnOpts": False,
    "showAvgByStrand": False,
    "showObservationLabels": False,
    "showObservationModule": False,
    "showObservationTag1": False,
    "showObservationTag2": False,
    "showObservationTag3": False,
    "showObservationTag4": False,
    "showObservationType": True,
    "showOnDataReports": True,
    "showStrandScores": False,
    "signature": False,
    "signatureOnByDefault": False,
    "transferDescriptionToTextbox": False,
    "video": False,
    "videoForm": True,
    "enableClickToFill": True,
    "isSiteVisit": False,
    "isAlwaysFocus": False,
    "hideFromTeachers": True,
    "hideFromCoaches": True,
    "hideFromRegionalCoaches": False,
    "hideFromSchoolAdmins": True,
    "hideFromSchoolAssistantAdmins": True,
    "isCoachingStartForm": False,
    "meetingQuickCreate": False,
    "customHtmlTitle": "",
    "customHtml": "",
    "defaultUsertype": None,
    "defaultCourse": None,
    "useStrandWeights": False,
    "isCompetencyRubric": False,
    "useAdditiveScoring": False,
    "nameAndSignatureDisplay": False,
    "privateRows": ["5ebb10c1f721a6001c3bbe66"],
    "featureInstructions": [
        {
            "hideOnDraft": True,
            "hideOnFinalized": False,
            "includeOnEmails": False,
            "_id": "5ebb136a8699620016778d9f",
            "section": "assign-action",
            "text": "",
            "titleOverride": "Notes and Next Steps (Shared)",
        }
    ],
}

SCHOOL_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "abbreviation", "type": "string"},
    {"name": "name", "type": "string"},
    {
        "name": "archivedAt",
        "type": ["null", {"type": "string", "logicalType": "timestamp-millis"}],
    },
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "nonInstructionalAdmins", "type": {"type": "array", "items": "null"}},
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
                    {"name": "_id", "type": ["string"]},
                    {"name": "locked", "type": ["boolean"]},
                    {"name": "name", "type": ["string"]},
                    {
                        "name": "lastModified",
                        "type": "string",
                        "logicalType": "timestamp-millis",
                    },
                    {"name": "admins", "type": {"type": "array", "items": "null"}},
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
    # {"name": "address", "type": "string"},
    # {"name": "city", "type": "string"},
    # {"name": "cluster", "type": "string"},
    # {"name": "district", "type": "string"},
    # {"name": "gradeSpan", "type": "string"},
    # {"name": "highGrade", "type": "string"},
    # {"name": "internalId", "type": "string"},
    # {"name": "lowGrade", "type": "string"},
    # {"name": "phone", "type": "string"},
    # {"name": "principal", "type": "string"},
    # {"name": "region", "type": "string"},
    # {"name": "state", "type": "string"},
    # {"name": "ward", "type": "string"},
    # {"name": "zip", "type": "string"},
]

ASSIGNMENT_FIELDS = [
    {"name": "_id", "type": "string"},
    {"name": "excludeFromBank", "type": "boolean"},
    {"name": "locked", "type": "boolean"},
    {"name": "private", "type": "boolean"},
    {"name": "coachingActivity", "type": "boolean"},
    {"name": "name", "type": "string"},
    {"name": "type", "type": "string"},
    {"name": "created", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "lastModified", "type": "string", "logicalType": "timestamp-millis"},
    {"name": "parent", "type": "null"},
    {"name": "grade", "type": "null"},
    {"name": "course", "type": "null"},
    {
        "name": "creator",
        "type": get_avro_record_schema(name="creator", fields=GENERIC_REF_FIELDS),
    },
    {
        "name": "user",
        "type": get_avro_record_schema(name="user", fields=GENERIC_REF_FIELDS),
    },
    {
        "name": "progress",
        "type": get_avro_record_schema(
            name="progress",
            fields=[
                {"name": "percent", "type": ["int"]},
                {"name": "assigner", "type": ["null"]},
                {"name": "justification", "type": ["null"]},
                {"name": "date", "type": ["null"]},
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
                    {"name": "_id", "type": ["string"]},
                    {"name": "name", "type": ["string"]},
                    {"name": "url", "type": ["string"]},
                ],
            ),
        },
    },
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
    {"name": "observedUntil", "type": ["null"]},
    {"name": "viewedByTeacher", "type": ["null"]},
    {"name": "archivedAt", "type": ["null"]},
    {"name": "observationModule", "type": ["null"]},
    {"name": "observationtag1", "type": ["null"]},
    {"name": "observationtag2", "type": ["null"]},
    {"name": "observationtag3", "type": ["null"]},
    {"name": "files", "type": [{"type": "array", "items": "null"}]},
    {"name": "meetings", "type": [{"type": "array", "items": "null"}]},
    {"name": "tags", "type": [{"type": "array", "items": "null"}]},
    {
        "name": "observationScores",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="observation_score",
                    fields=[
                        {"name": "measurement", "type": ["string"]},
                        {"name": "measurementGroup", "type": ["string"]},
                        {"name": "valueScore", "type": ["int"]},
                        {"name": "valueText", "type": ["null"]},
                        {"name": "percentage", "type": ["null"]},
                        {
                            "name": "lastModified",
                            "type": [
                                {"type": "string", "logicalType": "timestamp-millis"}
                            ],
                        },
                        {
                            "name": "checkboxes",
                            "type": [
                                {
                                    "type": "array",
                                    "items": {"label": "string", "value": "boolean"},
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
                    ],
                ),
            }
        ],
    },
    {
        "name": "magicNotes",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="magic_note",
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
            }
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
    {"name": "canvasId", "type": ["null"]},
    {"name": "coach", "type": ["null"]},
    {"name": "districts", "type": [{"type": "array", "items": "string"}]},
    {"name": "additionalEmails", "type": [{"type": "array", "items": "null"}]},
    {"name": "endOfYearLog", "type": [{"type": "array", "items": "null"}]},
    {"name": "pastUserTypes", "type": [{"type": "array", "items": "null"}]},
    {"name": "regionalAdminSchools", "type": [{"type": "array", "items": "null"}]},
    {"name": "externalIntegrations", "type": [{"type": "array", "items": "null"}]},
    {
        "name": "roles",
        "type": [
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="role",
                    fields=[
                        {"name": "role", "type": ["string"]},
                        {
                            "name": "districts",
                            "type": [{"type": "array", "items": "string"}],
                        },
                    ],
                ),
            },
        ],
    },
    {
        "name": "defaultInformation",
        "type": [
            get_avro_record_schema(
                name="default_information",
                fields=[
                    {"name": "period", "type": ["null"]},
                    {
                        "name": "gradeLevel",
                        "type": [
                            get_avro_record_schema(
                                name="grade_level", fields=GENERIC_REF_FIELDS
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
                        "type": [{"type": "array", "items": "null"}],
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
    {"name": "users", "type": [{"type": "array", "items": "null"}]},
    {"name": "observations", "type": [{"type": "array", "items": "null"}]},
    {"name": "comments", "type": [{"type": "array", "items": "null"}]},
    {"name": "videoNotes", "type": [{"type": "array", "items": "null"}]},
]

ENDPOINT_FIELDS = {
    "generic-tags/assignmentpresets": GENERIC_TAG_TYPE_FIELDS,
    "informals": INFORMAL_FIELDS,
    "measurements": MEASUREMENT_FIELDS,
    "meetings": MEETING_FIELDS,
    "roles": ROLE_FIELDS,
    "rubrics": RUBRIC_FIELDS,
    "schools": SCHOOL_FIELDS,
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
