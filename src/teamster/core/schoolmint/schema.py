def get_avro_record_schema(name, fields):
    return {
        "type": "record",
        "name": f"{name.replace('-', '_')}_record",
        "fields": fields,
    }


ASSIGNMENT_FIELDS = [
    {
        "_id": "string",
        "excludeFromBank": "boolean",
        "locked": "boolean",
        "private": "boolean",
        "coachingActivity": "boolean",
        "name": "string",
        "type": "string",
        "parent": None,
        "grade": None,
        "course": None,
        "creator": {"_id": "string", "name": "string"},
        "user": {"_id": "string", "name": "string"},
        "created": "2019-08-28T15:20:38.027Z",
        "lastModified": "2019-08-28T15:20:38.028Z",
        "tags": [{"_id": "string", "name": "string", "url": "string"}],
        "progress": {
            "percent": "int",
            "assigner": None,
            "justification": None,
            "date": None,
        },
    }
]

GENERIC_TAG_TYPE_FIELDS = [
    {
        "showOnDash": "boolean",
        "_id": "590763379223a8000c301519",
        "created": "2017-05-01T16:32:55.882Z",
        "abbreviation": "FF",
        "color": "#ff0000",
        "parent": None,
        "creator": None,
        "name": "Formal",
        "order": 6,
        "tags": [],
        "district": "5ba264d5cd5f35424ee05d54",
        "lastModified": "2019-04-17T07:28:42.289Z",
    }
]

INFORMAL_FIELDS = [
    {"name": "shared", "type": ["string"]},
    {"name": "private", "type": ["string"]},
    {"name": "user", "type": ["string"]},
    {"name": "creator", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "_id", "type": ["string"]},
    {"name": "created", "type": ["2019-10-18T20:15:47.055Z"]},
    {"name": "lastModified", "type": ["2019-10-18T20:15:47.484Z"]},
    {"name": "tags", "type": [["string"]]},
]

LESSON_PLAN_FORM_FIELDS = [
    {
        "_id": "string",
        "archivedAt": None,
        "fieldGroups": [
            {
                "_id": "string",
                "description": "",
                "fields": [
                    {
                        "_id": "string",
                        "name": "string",
                        "description": "string",
                        "isPrivate": "boolean",
                        "content": None,
                        "type": "string",
                    },
                ],
                "name": "string",
            }
        ],
        "creator": {"_id": "string", "name": "string", "email": "string"},
        "district": "string",
        "order": "int",
        "name": "string",
        "created": "2020-10-21T19:01:31.811Z",
        "lastModified": "2020-10-21T19:05:49.129Z",
        "settings": {},
    }
]

LESSON_PLAN_GROUP_FIELDS = [
    {
        "_id": "string",
        "archivedAt": None,
        "objective": None,
        "documents": ["string"],
        "reviews": [{"_id": "string", "status": "string"}],
        "course": {"_id": "string", "name": "string"},
        "grade": {"_id": "string", "name": "string"},
        "school": {"_id": "string", "name": "string"},
        "standard": {"_id": "string", "name": "string"},
        "teachDate": "2020-11-13T05:00:00.319Z",
        "name": "string",
        "creator": {"_id": "string", "email": "string", "name": "string"},
        "district": "string",
        "created": "2020-11-02T18:02:42.706Z",
        "lastModified": "2020-11-02T18:03:29.606Z",
        "status": "string",
    }
]

LESSON_PLAN_REVIEW_FIELDS = [
    {
        "_id": "string",
        "archivedAt": None,
        "submitDate": None,
        "submitNote": None,
        "teacherNote": None,
        "needsResubmit": "boolean",
        "attachments": [],
        "fieldGroups": [
            {
                "_id": "string",
                "description": "",
                "fields": [
                    {
                        "_id": "string",
                        "name": "string",
                        "description": None,
                        "isPrivate": "boolean",
                        "content": None,
                        "type": "string",
                    },
                ],
                "name": "string",
            },
        ],
        "creator": {"_id": "string", "name": "string", "email": "string"},
        "district": "string",
        "group": {"_id": "string", "name": "string"},
        "document": "string",
        "status": "string",
        "created": "2020-10-30T18:04:36.547Z",
        "lastModified": "2020-10-30T18:04:44.882Z",
        "form": {"_id": "string", "name": "string"},
    }
]

MEASUREMENT_FIELDS = [
    {
        "_id": "string",
        "textBoxes": ["string"],
        "name": "string",
        "sortId": "string",
        "description": "string",
        "measurementType": None,
        "isPercentage": "boolean",
        "created": "2019-10-08T18:53:38.080Z",
        "measurementOptions": [
            {
                "_id": "string",
                "value": "int",
                "label": "string",
                "description": "string",
                "created": "2019-10-08T18:53:38.081Z",
                "percentage": "int",
            },
        ],
        "measurementGroups": [],
        "district": "string",
        "scaleMin": "int",
        "scaleMax": "int",
        "lastModified": "2019-10-08T18:53:38.092Z",
        "rowStyle": "string",
    }
]

MEETING_FIELDS = [
    {
        "_id": "string",
        "actionSteps": [],
        "locked": "boolean",
        "observations": ["string"],
        "private": "boolean",
        "signatureRequired": "boolean",
        "onleave": [],
        "offweek": [],
        "unable": [],
        "additionalFields": [],
        "course": None,
        "date": "2020-01-03T19:30:51.052Z",
        "grade": None,
        "school": None,
        "title": "string",
        "type": "string",
        "participants": [],
        "creator": "string",
        "district": "string",
        "created": "2020-01-03T19:30:51.059Z",
        "lastModified": "2020-01-03T19:34:17.826Z",
    }
]

OBSERVATION_FIELDS = [
    {
        "_id": "string",
        "observedAt": "2020-03-11T15:47:51.996Z",
        "observedUntil": None,
        "firstPublished": "2020-03-11T16:05:17.440Z",
        "lastPublished": "2020-03-11T16:05:17.440Z",
        "viewedByTeacher": None,
        "tags": [],
        "isPublished": "boolean",
        "sendEmail": "boolean",
        "archivedAt": None,
        "requireSignature": "boolean",
        "locked": "boolean",
        "isPrivate": "boolean",
        "files": [],
        "meetings": [],
        "signed": "boolean",
        "observer": "string",
        "rubric": "string",
        "teacher": "string",
        "district": "string",
        "observationType": "string",
        "observationModule": None,
        "observationtag1": None,
        "observationtag2": None,
        "observationtag3": None,
        "observationScores": [
            {
                "measurement": "string",
                "measurementGroup": "string",
                "valueScore": "int",
                "valueText": None,
                "checkboxes": [{"label": "string", "value": "boolean"}],
                "percentage": None,
                "textBoxes": [{"label": "string", "text": "string"}],
                "lastModified": "2020-03-11T16:05:17.374Z",
            },
        ],
        "created": "2020-03-11T15:51:01.265Z",
        "lastModified": "2020-03-11T16:05:17.441Z",
        "quickHits": "string",
        "score": "float",
        "scoreAveragedByStrand": "float",
        "magicNotes": [
            {
                "shared": "boolean",
                "created": "2020-03-11T16:03:57.753Z",
                "text": "string",
            },
        ],
    }
]

ROLE_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "category", "type": ["string"]},
]

RUBRIC_FIELDS = [
    {
        "_id": "string",
        "settings": {
            "enableClickToFill": "boolean",
            "actionStepCreate": "boolean",
            "signature": "boolean",
            "signatureOnByDefault": "boolean",
            "notification": "boolean",
            "debrief": "boolean",
            "isPrivate": "boolean",
            "isScorePrivate": "boolean",
            "isSiteVisit": "boolean",
            "requireAll": "boolean",
            "dontRequireTextboxesOnLikertRows": "boolean",
            "scoreOverride": "boolean",
            "scoreOnForm": "boolean",
            "hasCompletionMarks": "boolean",
            "isPeerRubric": "boolean",
            "isAlwaysFocus": "boolean",
            "showAllTextOnOpts": "boolean",
            "hideFromLists": "boolean",
            "hideFromTeachers": "boolean",
            "hideFromCoaches": "boolean",
            "hideFromRegionalCoaches": "boolean",
            "hideFromSchoolAdmins": "boolean",
            "hideFromSchoolAssistantAdmins": "boolean",
            "isCoachingStartForm": "boolean",
            "videoForm": "boolean",
            "meetingQuickCreate": "boolean",
            "displayNumbers": "boolean",
            "displayLabels": "boolean",
            "hasRowDescriptions": "boolean",
            "actionStepWorkflow": "boolean",
            "obsTypeFinalize": "boolean",
            "descriptionsInEditor": "boolean",
            "showObservationLabels": "boolean",
            "showObservationType": "boolean",
            "showObservationModule": "boolean",
            "showObservationTag1": "boolean",
            "showObservationTag2": "boolean",
            "showObservationTag3": "boolean",
            "hideEmptyRows": "boolean",
            "hideOverallScore": "boolean",
            "hideEmptyTextRows": "boolean",
            "sendEmailOnSignature": "boolean",
            "showStrandScores": "boolean",
            "showAvgByStrand": "boolean",
            "cloneable": "boolean",
            "customHtmlTitle": "string",
            "customHtml": "string",
            "lockScoreAfterDays": "string",
            "quickHits": "string",
            "prepopulateActionStep": None,
            "defaultObsType": None,
            "defaultObsModule": None,
            "defaultObsTag1": None,
            "defaultObsTag2": None,
            "defaultObsTag3": None,
            "defaultUsertype": None,
            "defaultCourse": None,
        },
        "measurements": ["string"],
        "scaleMin": "int",
        "scaleMax": "int",
        "isPrivate": "boolean",
        "name": "string",
        "_measurementGroups": None,
        "district": "string",
        "created": "2019-10-14T16:12:23.584Z",
        "scoringMethod": "string",
        "lastModified": "2020-01-09T19:46:57.000Z",
        "order": "int",
        "isPublished": "boolean",
        "layout": {
            "formLeft": [
                {
                    "hideOnDraft": "boolean",
                    "hideOnFinalized": "boolean",
                    "rubricMeasurement": None,
                    "widgetDescription": None,
                    "widgetKey": "string",
                    "widgetTitle": "string",
                },
            ],
            "formWide": [
                {
                    "hideOnDraft": "boolean",
                    "hideOnFinalized": "boolean",
                    "rubricMeasurement": "string",
                    "widgetDescription": None,
                    "widgetKey": "string",
                    "widgetTitle": "string",
                },
            ],
        },
        "measurementGroups": [
            {
                "measurements": [
                    {
                        "require": "boolean",
                        "isPrivate": "boolean",
                        "weight": "int",
                        "exclude": "boolean",
                        "measurement": "string",
                    }
                ],
                "_id": "string",
                "name": "string",
                "key": "string",
            },
        ],
    }
]

SCHOOL_FIELDS = [
    {
        "_id": "string",
        "name": "string",
        "assistantAdmins": [],
        "admins": [{"_id": "string", "name": "string"}],
        "archivedAt": None,
        "observationGroups": [
            {
                "admins": [],
                "observers": [],
                "observees": [{"_id": "string", "name": "string"}],
                "locked": "boolean",
                "_id": "string",
                "name": "string",
                "lastModified": "2019-09-05T21:16:59.978Z",
            }
        ],
        "nonInstructionalAdmins": [],
        "lastModified": "2019-09-05T21:16:59.979Z",
        "district": "string",
        "abbreviation": "",
        "address": "",
        "city": "",
        "cluster": "",
        "gradeSpan": "",
        "highGrade": "",
        "internalId": "",
        "lowGrade": "",
        "phone": "",
        "principal": "",
        "region": "",
        "state": "",
        "ward": "",
        "zip": "",
    },
    {
        "_id": "string",
        "archivedAt": None,
        "observationGroups": [
            {
                "observees": [{"_id": "string", "name": "string"}],
                "observers": [{"_id": "string", "name": "string"}],
                "_id": "string",
                "locked": "boolean",
                "name": "string",
                "lastModified": "2019-10-11T16:37:11.565Z",
            }
        ],
        "admins": [],
        "name": "string",
        "nonInstructionalAdmins": [],
        "assistantAdmins": [{"_id": "string", "name": "string"}],
        "lastModified": "2019-10-11T16:37:11.565Z",
        "abbreviation": "string",
        "address": "string",
        "city": "string",
        "cluster": "string",
        "gradeSpan": "string",
        "highGrade": "string",
        "internalId": "string",
        "lowGrade": "string",
        "phone": "string",
        "principal": "string",
        "region": "string",
        "state": "string",
        "ward": "string",
        "zip": "string",
        "district": "string",
    },
]

USER_FIELDS = [
    {
        "_id": "string",
        "additionalEmails": [],
        "archivedAt": "2018-03-06T22:20:52.343Z",
        "coach": None,
        "created": "2017-05-22T21:01:52.198Z",
        "defaultInformation": {
            "gradeLevel": {"_id": "string", "name": "string"},
            "period": None,
            "school": {"_id": "string", "name": "string"},
            "course": {"_id": "string", "name": "string"},
        },
        "districts": ["string"],
        "email": "string",
        "endOfYearLog": [],
        "endOfYearVisible": "boolean",
        "first": "string",
        "inactive": "boolean",
        "internalId": "string",
        "last": "string",
        "lastActivity": "2017-05-26T21:55:21.707Z",
        "lastModified": "2018-12-19T22:23:15.509Z",
        "name": "string",
        "pastUserTypes": [],
        "preferences": {
            "unsubscribedTo": [],
            "homepage": "string",
            "timezoneText": "string",
        },
        "regionalAdminSchools": [],
        "roles": [{"role": "string", "districts": ["string"]}],
        "showOnDashboards": "boolean",
        "externalIntegrations": [],
        "accountingId": "string",
        "canvasId": None,
        "powerSchoolId": "string",
    }
]

VIDEO_FIELDS = [
    {"name": "_id", "type": ["string"]},
    {"name": "observations", "type": [[]]},
    {"name": "users", "type": [[]]},
    {"name": "creator", "type": ["string"]},
    {"name": "district", "type": ["string"]},
    {"name": "url", "type": ["string"]},
    {"name": "thumbnail", "type": ["string"]},
    {"name": "name", "type": ["string"]},
    {"name": "fileName", "type": ["string"]},
    {"name": "zencoderJobId", "type": ["string"]},
    {"name": "status", "type": ["string"]},
    {"name": "style", "type": ["string"]},
    {"name": "comments", "type": [[]]},
    {"name": "videoNotes", "type": [[]]},
    {"name": "created", "type": ["2020-03-13T17:59:35.021Z"]},
    {"name": "lastModified", "type": ["2020-03-13T17:59:55.549Z"]},
]

ENDPOINT_FIELDS = {}
