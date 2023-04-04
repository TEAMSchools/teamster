from teamster.core.utils.functions import get_avro_record_schema

TIMESTAMP_FIELDS = {
    "v1": [
        {"name": "timezone_type", "type": "int"},
        {"name": "timezone", "type": "string"},
        {"name": "date", "type": "string", "logicalType": "timestamp-micros"},
    ]
}

BEHAVIOR_FIELDS = {
    "beta": [
        {"name": "Behavior", "type": "string"},
        {"name": "BehaviorCategory", "type": "string"},
        {"name": "BehaviorID", "type": "string"},
        {"name": "DLOrganizationID", "type": "string"},
        {"name": "DLSAID", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "PointValue", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "StaffFirstName", "type": "string"},
        {"name": "StaffLastName", "type": "string"},
        {"name": "StaffMiddleName", "type": "string"},
        {"name": "StaffTitle", "type": "string"},
        {"name": "StudentFirstName", "type": "string"},
        {"name": "StudentLastName", "type": "string"},
        {"name": "StudentMiddleName", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "Weight", "type": "string"},
        {"name": "Assignment", "type": ["null", "string"]},
        {"name": "Notes", "type": ["null", "string"]},
        {"name": "Roster", "type": ["null", "string"]},
        {"name": "RosterID", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "SourceProcedure", "type": ["null", "string"]},
        {"name": "SourceType", "type": ["null", "string"]},
        {"name": "StaffSchoolID", "type": ["null", "string"]},
        {"name": "BehaviorDate", "type": "string", "logicalType": "date"},
        {"name": "DL_LASTUPDATE", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
    "v1": [
        {"name": "DLOrganizationID", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "StudentFirstName", "type": "string"},
        {"name": "StudentMiddleName", "type": "string"},
        {"name": "StudentLastName", "type": "string"},
        {"name": "DLSAID", "type": "string"},
        {"name": "Behavior", "type": "string"},
        {"name": "BehaviorID", "type": "string"},
        {"name": "Weight", "type": "string"},
        {"name": "BehaviorCategory", "type": "string"},
        {"name": "PointValue", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "StaffTitle", "type": "string"},
        {"name": "StaffFirstName", "type": "string"},
        {"name": "StaffMiddleName", "type": "string"},
        {"name": "StaffLastName", "type": "string"},
        {"name": "Assignment", "type": ["null", "string"]},
        {"name": "Notes", "type": ["null", "string"]},
        {"name": "Roster", "type": ["null", "string"]},
        {"name": "RosterID", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "SourceProcedure", "type": ["null", "string"]},
        {"name": "SourceType", "type": ["null", "string"]},
        {"name": "StaffSchoolID", "type": ["null", "string"]},
        {"name": "BehaviorDate", "type": "string", "logicalType": "date"},
        {"name": "DL_LASTUPDATE", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
}

HOMEWORK_FIELDS = {
    "beta": [
        {"name": "Behavior", "type": "string"},
        {"name": "BehaviorCategory", "type": "string"},
        {"name": "BehaviorDate", "type": "string"},
        {"name": "BehaviorID", "type": "string"},
        {"name": "DLOrganizationID", "type": "string"},
        {"name": "DLSAID", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "Notes", "type": "string"},
        {"name": "PointValue", "type": "string"},
        {"name": "Roster", "type": "string"},
        {"name": "RosterID", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "StaffFirstName", "type": "string"},
        {"name": "StaffLastName", "type": "string"},
        {"name": "StaffMiddleName", "type": "string"},
        {"name": "StaffSchoolID", "type": "string"},
        {"name": "StaffTitle", "type": "string"},
        {"name": "StudentFirstName", "type": "string"},
        {"name": "StudentLastName", "type": "string"},
        {"name": "StudentMiddleName", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "Weight", "type": "string"},
        {"name": "DL_LASTUPDATE", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "Assignment", "type": ["null", "string"]},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
    "v1": [
        {"name": "Behavior", "type": "string"},
        {"name": "BehaviorCategory", "type": "string"},
        {"name": "BehaviorDate", "type": "string"},
        {"name": "BehaviorID", "type": "string"},
        {"name": "DLOrganizationID", "type": "string"},
        {"name": "DLSAID", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "Notes", "type": "string"},
        {"name": "PointValue", "type": "string"},
        {"name": "Roster", "type": "string"},
        {"name": "RosterID", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "StaffFirstName", "type": "string"},
        {"name": "StaffLastName", "type": "string"},
        {"name": "StaffMiddleName", "type": "string"},
        {"name": "StaffSchoolID", "type": "string"},
        {"name": "StaffTitle", "type": "string"},
        {"name": "StudentFirstName", "type": "string"},
        {"name": "StudentLastName", "type": "string"},
        {"name": "StudentMiddleName", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "Weight", "type": "string"},
        {"name": "DL_LASTUPDATE", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "Assignment", "type": ["null", "string"]},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
}

FOLLOWUP_FIELDS = {
    "v1": [
        {"name": "ExtStatus", "type": "string"},
        {"name": "FollowupID", "type": "string"},
        {"name": "FollowupType", "type": "string"},
        {"name": "iFirst", "type": "string"},
        {"name": "iLast", "type": "string"},
        {"name": "iMiddle", "type": "string"},
        {"name": "InitBy", "type": "string"},
        {"name": "InitNotes", "type": "string"},
        {"name": "iTitle", "type": "string"},
        {"name": "LongType", "type": "string"},
        {"name": "Outstanding", "type": "string"},
        {"name": "SchoolID", "type": "string"},
        {"name": "TicketStatus", "type": "string"},
        {"name": "cFirst", "type": ["null", "string"]},
        {"name": "cLast", "type": ["null", "string"]},
        {"name": "CloseBy", "type": ["null", "string"]},
        {"name": "cMiddle", "type": ["null", "string"]},
        {"name": "cTitle", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "FollowupNotes", "type": ["null", "string"]},
        {"name": "GradeLevelShort", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "ResponseID", "type": ["null", "string"]},
        {"name": "ResponseType", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "TicketType", "type": ["null", "string"]},
        {"name": "TicketTypeID", "type": ["null", "string"]},
        {"name": "URL", "type": ["null", "string"]},
        {"name": "InitTS", "type": "string", "logicalType": "timestamp-micros"},
        {
            "name": "CloseTS",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {
            "name": "OpenTS",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
    ]
}

COMMUNICATION_FIELDS = {
    "beta": [
        {"name": "CallTopic", "type": "string"},
        {"name": "CallType", "type": "string"},
        {"name": "CommWith", "type": "string"},
        {"name": "DLCallLogID", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "Email", "type": "string"},
        {"name": "IsActive", "type": "string"},
        {"name": "PersonContacted", "type": "string"},
        {"name": "PhoneNumber", "type": "string"},
        {"name": "Relationship", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "UserFirstName", "type": "string"},
        {"name": "UserLastName", "type": "string"},
        {"name": "CallDateTime", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "DL_LASTUPDATE", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "CallStatus", "type": ["null", "string"]},
        {"name": "FollowupBy", "type": ["null", "string"]},
        {"name": "FollowupCloseTS", "type": ["null", "string"]},
        {"name": "FollowupID", "type": ["null", "string"]},
        {"name": "FollowupInitTS", "type": ["null", "string"]},
        {"name": "FollowupOutstanding", "type": ["null", "string"]},
        {"name": "FollowupRequest", "type": ["null", "string"]},
        {"name": "FollowupResponse", "type": ["null", "string"]},
        {"name": "MailingAddress", "type": ["null", "string"]},
        {"name": "Reason", "type": ["null", "string"]},
        {"name": "Response", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "SourceType", "type": ["null", "string"]},
        {"name": "ThirdParty", "type": ["null", "string"]},
        {"name": "UserSchoolID", "type": ["null", "string"]},
    ],
    "v1": [
        {"name": "CallType", "type": "string"},
        {"name": "EducatorName", "type": "string"},
        {"name": "Email", "type": "string"},
        {"name": "IsDraft", "type": "boolean"},
        {"name": "PhoneNumber", "type": "string"},
        {"name": "RecordID", "type": "int"},
        {"name": "RecordType", "type": "string"},
        {"name": "Response", "type": "string"},
        {"name": "Topic", "type": "string"},
        {"name": "UserID", "type": "int"},
        {"name": "CallStatus", "type": ["null", "string"]},
        {"name": "CallStatusID", "type": ["null", "int"]},
        {"name": "MailingAddress", "type": ["null", "string"]},
        {"name": "Reason", "type": ["null", "string"]},
        {"name": "ReasonID", "type": ["null", "int"]},
        {"name": "CallDateTime", "type": "string", "logicalType": "timestamp-micros"},
        {
            "name": "Student",
            "type": get_avro_record_schema(
                name="student",
                fields=[
                    {"name": "StudentID", "type": "string"},
                    {"name": "StudentSchoolID", "type": "string"},
                    {"name": "SecondaryStudentID", "type": "string"},
                    {"name": "StudentFirstName", "type": "string"},
                    {"name": "StudentMiddleName", "type": "string"},
                    {"name": "StudentLastName", "type": "string"},
                ],
            ),
        },
        {
            "name": "Followups",
            "type": {
                "type": "array",
                "items": get_avro_record_schema(
                    name="followup", fields=FOLLOWUP_FIELDS["v1"]
                ),
            },
        },
    ],
}

USER_FIELDS = {
    "beta": [
        {"name": "AccountID", "type": ["null", "string"]},
        {"name": "Active", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "Email", "type": "string"},
        {"name": "FirstName", "type": "string"},
        {"name": "GroupName", "type": "string"},
        {"name": "LastName", "type": "string"},
        {"name": "MiddleName", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "StaffRole", "type": "string"},
        {"name": "Title", "type": "string"},
        {"name": "Username", "type": ["null", "string"]},
        {"name": "UserSchoolID", "type": "string"},
        {"name": "UserStateID", "type": ["null", "string"]},
    ],
    "v1": [
        {"name": "Active", "type": "string"},
        {"name": "DLSchoolID", "type": "string"},
        {"name": "DLUserID", "type": "string"},
        {"name": "Email", "type": "string"},
        {"name": "FirstName", "type": "string"},
        {"name": "GroupName", "type": "string"},
        {"name": "LastName", "type": "string"},
        {"name": "MiddleName", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "StaffRole", "type": "string"},
        {"name": "Title", "type": "string"},
        {"name": "UserSchoolID", "type": "string"},
        {"name": "AccountID", "type": ["null", "string"]},
        {"name": "UserStateID", "type": ["null", "string"]},
        {"name": "Username", "type": ["null", "string"]},
    ],
}

ROSTER_ASSIGNMENT_FIELDS = {
    "beta": [
        {"name": "DLSchoolID", "type": "string"},
        {"name": "SchoolName", "type": "string"},
        {"name": "DLStudentID", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "SecondaryStudentID", "type": "string"},
        {"name": "FirstName", "type": "string"},
        {"name": "MiddleName", "type": "string"},
        {"name": "LastName", "type": "string"},
        {"name": "GradeLevel", "type": "string"},
        {"name": "DLRosterID", "type": "string"},
        {"name": "RosterName", "type": "string"},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"]},
        {"name": "IntegrationID", "type": ["null", "string"]},
    ]
}

PENALTY_FIELDS = {
    "v1": [
        {"name": "IncidentID", "type": "string"},
        {"name": "IncidentPenaltyID", "type": "string"},
        {"name": "IsReportable", "type": "boolean"},
        {"name": "IsSuspension", "type": "boolean"},
        {"name": "NumPeriods", "type": "string"},
        {"name": "PenaltyID", "type": "string"},
        {"name": "PenaltyName", "type": "string"},
        {"name": "Print", "type": "boolean"},
        {"name": "SAID", "type": "string"},
        {"name": "SchoolID", "type": "string"},
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "NumDays", "type": ["null", "float"]},
        {
            "name": "EndDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
        {
            "name": "StartDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
    ]
}

ACTION_FIELDS = {
    "v1": [
        {"name": "ActionID", "type": "string"},
        {"name": "ActionName", "type": "string"},
        {"name": "SAID", "type": "string"},
        {"name": "PointValue", "type": "string"},
        {"name": "SourceID", "type": ["null", "string"]},
    ]
}

CUSTOM_FIELD_FIELDS = {
    "v1": [
        {"name": "CustomFieldID", "type": "string"},
        {"name": "FieldCategory", "type": ["null", "string"]},
        {"name": "FieldKey", "type": ["null", "string"]},
        {"name": "FieldName", "type": "string"},
        {"name": "FieldType", "type": "string"},
        {"name": "InputHTML", "type": ["null", "string"]},
        {"name": "InputName", "type": "string"},
        {"name": "IsFrontEnd", "type": "string"},
        {"name": "IsRequired", "type": "string"},
        {"name": "LabelHTML", "type": ["null", "string"]},
        {"name": "MinUserLevel", "type": "string"},
        {"name": "NumValue", "type": ["null", "float"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "SourceType", "type": "string"},
        {"name": "StringValue", "type": ["null", "string"]},
        {"name": "Value", "type": ["null", "string"]},
        {"name": "Options", "type": ["null", "string"], "default": None},
        {
            "name": "SelectedOptions",
            "type": ["null", {"type": "array", "items": "string"}],
            "default": None,
        },
    ]
}

INCIDENT_FIELDS = {
    "v1": [
        {"name": "AddlReqs", "type": "string"},
        {"name": "CategoryID", "type": "string"},
        {"name": "Context", "type": "string"},
        {"name": "CreateBy", "type": "string"},
        {"name": "CreateFirst", "type": "string"},
        {"name": "CreateLast", "type": "string"},
        {"name": "CreateMiddle", "type": "string"},
        {"name": "CreateTitle", "type": "string"},
        {"name": "FamilyMeetingNotes", "type": "string"},
        {"name": "FollowupNotes", "type": "string"},
        {"name": "Gender", "type": "string"},
        {"name": "GradeLevelShort", "type": "string"},
        {"name": "HearingFlag", "type": "boolean"},
        {"name": "IncidentID", "type": "string"},
        {"name": "InfractionTypeID", "type": "string"},
        {"name": "IsActive", "type": "boolean"},
        {"name": "IsReferral", "type": "boolean"},
        {"name": "ReportedDetails", "type": "string"},
        {"name": "ReportingIncidentID", "type": "string"},
        {"name": "SchoolID", "type": "string"},
        {"name": "Status", "type": "string"},
        {"name": "StatusID", "type": "string"},
        {"name": "StudentFirst", "type": "string"},
        {"name": "StudentID", "type": "string"},
        {"name": "StudentLast", "type": "string"},
        {"name": "StudentMiddle", "type": "string"},
        {"name": "StudentSchoolID", "type": "string"},
        {"name": "LocationID", "type": ["null", "string"]},
        {"name": "AdminSummary", "type": ["null", "string"]},
        {"name": "Category", "type": ["null", "string"]},
        {"name": "CreateStaffSchoolID", "type": ["null", "string"]},
        {"name": "HearingDate", "type": ["null", "string"]},
        {"name": "HearingLocation", "type": ["null", "string"]},
        {"name": "HearingNotes", "type": ["null", "string"]},
        {"name": "HearingTime", "type": ["null", "string"]},
        {"name": "HomeroomName", "type": ["null", "string"]},
        {"name": "Infraction", "type": ["null", "string"]},
        {"name": "Location", "type": ["null", "string"]},
        {"name": "ReturnPeriod", "type": ["null", "string"]},
        {"name": "SendAlert", "type": ["null", "boolean"]},
        {"name": "UpdateBy", "type": ["null", "string"]},
        {"name": "UpdateFirst", "type": ["null", "string"]},
        {"name": "UpdateLast", "type": ["null", "string"]},
        {"name": "UpdateMiddle", "type": ["null", "string"]},
        {"name": "UpdateStaffSchoolID", "type": ["null", "string"]},
        {"name": "UpdateTitle", "type": ["null", "string"]},
        {
            "name": "IssueTS",
            "type": get_avro_record_schema(
                name="IssueTS", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
        {
            "name": "ReturnDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="ReturnDate", fields=TIMESTAMP_FIELDS["v1"]
                ),
            ],
        },
        {
            "name": "CreateTS",
            "type": get_avro_record_schema(
                name="CreateTS", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
        {
            "name": "ReviewTS",
            "type": get_avro_record_schema(
                name="ReviewTS", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
        {
            "name": "DL_LASTUPDATE",
            "type": get_avro_record_schema(
                name="DL_LASTUPDATE", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
        {
            "name": "CloseTS",
            "type": [
                "null",
                get_avro_record_schema(name="CloseTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
        },
        {
            "name": "UpdateTS",
            "type": [
                "null",
                get_avro_record_schema(name="UpdateTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
        },
        {
            "name": "Penalties",
            "type": {
                "type": "array",
                "items": get_avro_record_schema(
                    name="penalty", fields=PENALTY_FIELDS["v1"]
                ),
            },
        },
        {
            "name": "Actions",
            "type": {
                "type": "array",
                "items": get_avro_record_schema(
                    name="action", fields=ACTION_FIELDS["v1"]
                ),
            },
        },
        {
            "name": "Custom_Fields",
            "type": {
                "type": "array",
                "items": get_avro_record_schema(
                    name="custom_field", fields=CUSTOM_FIELD_FIELDS["v1"]
                ),
            },
        },
    ]
}

LIST_FIELDS = {
    "v1": [
        {"name": "ListID", "type": "string"},
        {"name": "ListName", "type": "string"},
        {"name": "IsDated", "type": "boolean"},
    ]
}

TERM_FIELDS = {
    "v1": [
        {"name": "StoredGrades", "type": "boolean"},
        {"name": "TermID", "type": "string"},
        {"name": "AcademicYearID", "type": "string"},
        {"name": "AcademicYearName", "type": "string"},
        {"name": "SchoolID", "type": "string"},
        {"name": "TermTypeID", "type": "string"},
        {"name": "TermType", "type": "string"},
        {"name": "TermName", "type": "string"},
        {"name": "SecondaryGradeKey", "type": ["null", "string"]},
        {"name": "IntegrationID", "type": ["null", "string"]},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"]},
        {"name": "GradeKey", "type": ["null", "string"]},
        {"name": "Days", "type": ["null", "string"]},
        {
            "name": "StartDate",
            "type": get_avro_record_schema(
                name="StartDate", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
        {
            "name": "EndDate",
            "type": get_avro_record_schema(
                name="EndDate", fields=TIMESTAMP_FIELDS["v1"]
            ),
        },
    ]
}

ROSTER_FIELDS = {
    "v1": [
        {"name": "Active", "type": "string"},
        {"name": "CollectHW", "type": "string"},
        {"name": "RosterID", "type": "string"},
        {"name": "RosterName", "type": "string"},
        {"name": "RosterType", "type": "string"},
        {"name": "RosterTypeID", "type": "string"},
        {"name": "SchoolID", "type": "string"},
        {"name": "ShowRoster", "type": "string"},
        {"name": "StudentCount", "type": "string"},
        {"name": "TakeAttendance", "type": "string"},
        {"name": "TakeClassAttendance", "type": "string"},
        {"name": "CourseNumber", "type": ["null", "string"]},
        {"name": "GradeLevels", "type": ["null", "string"]},
        {"name": "MarkerColor", "type": ["null", "string"]},
        {"name": "MasterID", "type": ["null", "string"]},
        {"name": "MasterName", "type": ["null", "string"]},
        {"name": "MeetingDays", "type": ["null", "string"]},
        {"name": "Period", "type": ["null", "string"]},
        {"name": "Room", "type": ["null", "string"]},
        {"name": "RTIFocusID", "type": ["null", "string"]},
        {"name": "RTITier", "type": ["null", "string"]},
        {"name": "ScreenSetID", "type": ["null", "string"]},
        {"name": "ScreenSetName", "type": ["null", "string"]},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"]},
        {"name": "SectionNumber", "type": ["null", "string"]},
        {"name": "SISExpression", "type": ["null", "string"]},
        {"name": "SISGradebookName", "type": ["null", "string"]},
        {"name": "SISKey", "type": ["null", "string"]},
        {"name": "SubjectID", "type": ["null", "string"]},
        {"name": "SubjectName", "type": ["null", "string"]},
        {
            "name": "LastSynced",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
    ]
}

ENDPOINT_FIELDS = {
    "lists": LIST_FIELDS,
    "terms": TERM_FIELDS,
    "rosters": ROSTER_FIELDS,
    "users": USER_FIELDS,
    "roster-assignments": ROSTER_ASSIGNMENT_FIELDS,
    "behavior": BEHAVIOR_FIELDS,
    "homework": HOMEWORK_FIELDS,
    "comm": COMMUNICATION_FIELDS,
    "comm-log": COMMUNICATION_FIELDS,
    "incidents": INCIDENT_FIELDS,
    "followups": FOLLOWUP_FIELDS,
}
