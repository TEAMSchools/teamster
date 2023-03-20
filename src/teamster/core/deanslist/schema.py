def get_avro_record_schema(name, fields, version):
    return {
        "type": "record",
        "name": f"{name.replace('-', '_')}_record",
        "fields": fields[version],
    }


TIMESTAMP_FIELDS = {
    "v1": [
        {"name": "date", "type": "string", "logicalType": "timestamp-micros"},
        {"name": "timezone_type", "type": "int"},
        {"name": "timezone", "type": "string"},
    ]
}

BEHAVIOR_FIELDS = {
    "beta": [
        {"name": "DLOrganizationID", "type": ["string", "null"]},
        {"name": "DLSchoolID", "type": ["string", "null"]},
        {"name": "SchoolName", "type": ["string", "null"]},
        {"name": "DLStudentID", "type": ["string", "null"]},
        {"name": "StudentSchoolID", "type": ["string", "null"]},
        {"name": "SecondaryStudentID", "type": ["string", "null"]},
        {"name": "StudentFirstName", "type": ["string", "null"]},
        {"name": "StudentMiddleName", "type": ["string", "null"]},
        {"name": "StudentLastName", "type": ["string", "null"]},
        {"name": "DLSAID", "type": ["string", "null"]},
        {
            "name": "BehaviorDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
        {"name": "Behavior", "type": ["string", "null"]},
        {"name": "BehaviorID", "type": ["string", "null"]},
        {"name": "Weight", "type": ["string", "null"]},
        {"name": "BehaviorCategory", "type": ["string", "null"]},
        {"name": "PointValue", "type": ["string", "null"]},
        {"name": "DLUserID", "type": ["string", "null"]},
        {"name": "StaffSchoolID", "type": ["string", "null"]},
        {"name": "StaffTitle", "type": ["string", "null"]},
        {"name": "StaffFirstName", "type": ["string", "null"]},
        {"name": "StaffMiddleName", "type": ["string", "null"]},
        {"name": "StaffLastName", "type": ["string", "null"]},
        {"name": "Roster", "type": ["string", "null"]},
        {"name": "RosterID", "type": ["string", "null"]},
        {"name": "SourceType", "type": ["string", "null"]},
        {"name": "SourceID", "type": ["string", "null"]},
        {"name": "SourceProcedure", "type": ["string", "null"]},
        {"name": "Notes", "type": ["string", "null"]},
        {"name": "Assignment", "type": ["string", "null"]},
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
    "v1": [
        {"name": "DLOrganizationID", "type": ["string", "null"]},
        {"name": "DLSchoolID", "type": ["string", "null"]},
        {"name": "SchoolName", "type": ["string", "null"]},
        {"name": "DLStudentID", "type": ["string", "null"]},
        {"name": "StudentSchoolID", "type": ["string", "null"]},
        {"name": "SecondaryStudentID", "type": ["string", "null"]},
        {"name": "StudentFirstName", "type": ["string", "null"]},
        {"name": "StudentMiddleName", "type": ["string", "null"]},
        {"name": "StudentLastName", "type": ["string", "null"]},
        {"name": "DLSAID", "type": ["string", "null"]},
        {
            "name": "BehaviorDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
        {"name": "Behavior", "type": ["string", "null"]},
        {"name": "BehaviorID", "type": ["string", "null"]},
        {"name": "Weight", "type": ["string", "null"]},
        {"name": "BehaviorCategory", "type": ["string", "null"]},
        {"name": "PointValue", "type": ["string", "null"]},
        {"name": "DLUserID", "type": ["string", "null"]},
        {"name": "StaffSchoolID", "type": ["string", "null"]},
        {"name": "StaffTitle", "type": ["string", "null"]},
        {"name": "StaffFirstName", "type": ["string", "null"]},
        {"name": "StaffMiddleName", "type": ["string", "null"]},
        {"name": "StaffLastName", "type": ["string", "null"]},
        {"name": "Roster", "type": ["string", "null"]},
        {"name": "RosterID", "type": ["string", "null"]},
        {"name": "SourceType", "type": ["string", "null"]},
        {"name": "SourceID", "type": ["string", "null"]},
        {"name": "SourceProcedure", "type": ["string", "null"]},
        {"name": "Notes", "type": ["string", "null"]},
        {"name": "Assignment", "type": ["string", "null"]},
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
}

HOMEWORK_FIELDS = {
    "beta": [
        {"name": "DLOrganizationID", "type": ["null", "string"]},
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLStudentID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "SecondaryStudentID", "type": ["null", "string"]},
        {"name": "StudentFirstName", "type": ["null", "string"]},
        {"name": "StudentMiddleName", "type": ["null", "string"]},
        {"name": "StudentLastName", "type": ["null", "string"]},
        {"name": "DLSAID", "type": ["null", "string"]},
        {"name": "BehaviorDate", "type": ["null", "string"]},
        {"name": "Behavior", "type": ["null", "string"]},
        {"name": "BehaviorCategory", "type": ["null", "string"]},
        {"name": "PointValue", "type": ["null", "string"]},
        {"name": "DLUserID", "type": ["null", "string"]},
        {"name": "StaffSchoolID", "type": ["null", "string"]},
        {"name": "StaffTitle", "type": ["null", "string"]},
        {"name": "StaffFirstName", "type": ["null", "string"]},
        {"name": "StaffMiddleName", "type": ["null", "string"]},
        {"name": "StaffLastName", "type": ["null", "string"]},
        {"name": "RosterID", "type": ["null", "string"]},
        {"name": "Roster", "type": ["null", "string"]},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
    "v1": [
        {"name": "DLOrganizationID", "type": ["null", "string"]},
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLStudentID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "SecondaryStudentID", "type": ["null", "string"]},
        {"name": "StudentFirstName", "type": ["null", "string"]},
        {"name": "StudentMiddleName", "type": ["null", "string"]},
        {"name": "StudentLastName", "type": ["null", "string"]},
        {"name": "DLSAID", "type": ["null", "string"]},
        {"name": "BehaviorDate", "type": ["null", "string"]},
        {"name": "Behavior", "type": ["null", "string"]},
        {"name": "BehaviorCategory", "type": ["null", "string"]},
        {"name": "PointValue", "type": ["null", "string"]},
        {"name": "DLUserID", "type": ["null", "string"]},
        {"name": "StaffSchoolID", "type": ["null", "string"]},
        {"name": "StaffTitle", "type": ["null", "string"]},
        {"name": "StaffFirstName", "type": ["null", "string"]},
        {"name": "StaffMiddleName", "type": ["null", "string"]},
        {"name": "StaffLastName", "type": ["null", "string"]},
        {"name": "RosterID", "type": ["null", "string"]},
        {"name": "Roster", "type": ["null", "string"]},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
    ],
}

FOLLOWUP_FIELDS = {
    "v1": [
        {"name": "FollowupID", "type": ["null", "string"]},
        {"name": "SchoolID", "type": ["null", "string"]},
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "FollowupType", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "GradeLevelShort", "type": ["null", "string"]},
        {"name": "InitBy", "type": ["null", "string"]},
        {"name": "iFirst", "type": ["null", "string"]},
        {"name": "iMiddle", "type": ["null", "string"]},
        {"name": "iLast", "type": ["null", "string"]},
        {"name": "iTitle", "type": ["null", "string"]},
        {"name": "CloseBy", "type": ["null", "string"]},
        {"name": "cFirst", "type": ["null", "string"]},
        {"name": "cMiddle", "type": ["null", "string"]},
        {"name": "cLast", "type": ["null", "string"]},
        {"name": "cTitle", "type": ["null", "string"]},
        {
            "name": "InitTS",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {
            "name": "OpenTS",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {
            "name": "CloseTS",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {"name": "InitNotes", "type": ["null", "string"]},
        {"name": "Outstanding", "type": ["null", "string"]},
        {"name": "FollowupNotes", "type": ["null", "string"]},
        {"name": "TicketTypeID", "type": ["null", "string"]},
        {"name": "ExtStatus", "type": ["null", "string"]},
        {"name": "TicketStatus", "type": ["null", "string"]},
        {"name": "TicketType", "type": ["null", "string"]},
        {"name": "ResponseType", "type": ["null", "string"]},
        {"name": "ResponseID", "type": ["null", "string"]},
        {"name": "LongType", "type": ["null", "string"]},
        {"name": "URL", "type": ["null", "string"]},
    ]
}

COMMUNICATION_FIELDS = {
    "beta": [
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLCallLogID", "type": ["null", "string"]},
        {"name": "DLStudentID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "SecondaryStudentID", "type": ["null", "string"]},
        {"name": "DLUserID", "type": ["null", "string"]},
        {"name": "UserSchoolID", "type": ["null", "string"]},
        {"name": "CommWith", "type": ["null", "string"]},
        {"name": "CallType", "type": ["null", "string"]},
        {"name": "CallStatus", "type": ["null", "string"]},
        {"name": "Reason", "type": ["null", "string"]},
        {"name": "PersonContacted", "type": ["null", "string"]},
        {"name": "Relationship", "type": ["null", "string"]},
        {"name": "PhoneNumber", "type": ["null", "string"]},
        {"name": "MailingAddress", "type": ["null", "string"]},
        {"name": "ThirdParty", "type": ["null", "string"]},
        {"name": "Email", "type": ["null", "string"]},
        {
            "name": "CallDateTime",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {"name": "CallTopic", "type": ["null", "string"]},
        {"name": "Response", "type": ["null", "string"]},
        {"name": "FollowupID", "type": ["null", "string"]},
        {"name": "FollowupBy", "type": ["null", "string"]},
        {"name": "FollowupInitTS", "type": ["null", "string"]},
        {"name": "FollowupRequest", "type": ["null", "string"]},
        {"name": "FollowupCloseTS", "type": ["null", "string"]},
        {"name": "FollowupOutstanding", "type": ["null", "string"]},
        {"name": "FollowupResponse", "type": ["null", "string"]},
        {"name": "IsActive", "type": ["null", "string"]},
        {"name": "UserFirstName", "type": ["null", "string"]},
        {"name": "UserLastName", "type": ["null", "string"]},
        {"name": "SourceType", "type": ["null", "string"]},
        {"name": "SourceID", "type": ["null", "string"]},
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
    ],
    "v1": [
        {"name": "RecordID", "type": ["null", "int"]},
        {"name": "RecordType", "type": ["null", "string"]},
        {"name": "UserID", "type": ["null", "int"]},
        {"name": "EducatorName", "type": ["null", "string"]},
        {"name": "CallType", "type": ["null", "string"]},
        {"name": "CallStatusID", "type": ["null", "int"]},
        {"name": "CallStatus", "type": ["null", "string"]},
        {"name": "Email", "type": ["null", "string"]},
        {
            "name": "CallDateTime",
            "type": ["null", {"type": "string", "logicalType": "timestamp-micros"}],
        },
        {"name": "Topic", "type": ["null", "string"]},
        {"name": "Response", "type": ["null", "string"]},
        {"name": "MailingAddress", "type": ["null", "string"]},
        {"name": "ReasonID", "type": ["null", "int"]},
        {"name": "Reason", "type": ["null", "string"]},
        {"name": "IsDraft", "type": ["null", "boolean"]},
        {"name": "PhoneNumber", "type": ["null", "string"]},
        {
            "name": "Student",
            "type": {
                "type": "record",
                "name": "student_record",
                "fields": [
                    {"name": "StudentID", "type": ["null", "string"]},
                    {"name": "StudentSchoolID", "type": ["null", "string"]},
                    {"name": "SecondaryStudentID", "type": ["null", "string"]},
                    {"name": "StudentFirstName", "type": ["null", "string"]},
                    {"name": "StudentMiddleName", "type": ["null", "string"]},
                    {"name": "StudentLastName", "type": ["null", "string"]},
                ],
            },
        },
        {
            "name": "Followups",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="followup", fields=FOLLOWUP_FIELDS, version="v1"
                    ),
                },
            ],
        },
    ],
}

USER_FIELDS = {
    "beta": [
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLUserID", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "Title", "type": ["null", "string"]},
        {"name": "UserSchoolID", "type": ["null", "string"]},
        {"name": "UserStateID", "type": ["null", "string"]},
        {"name": "StaffRole", "type": ["null", "string"]},
        {"name": "Username", "type": ["null", "string"]},
        {"name": "Email", "type": ["null", "string"]},
        {"name": "AccountID", "type": ["null", "string"]},
        {"name": "GroupName", "type": ["null", "string"]},
        {"name": "Active", "type": ["null", "string"]},
    ],
    "v1": [
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLUserID", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "Title", "type": ["null", "string"]},
        {"name": "UserSchoolID", "type": ["null", "string"]},
        {"name": "UserStateID", "type": ["null", "string"]},
        {"name": "StaffRole", "type": ["null", "string"]},
        {"name": "Username", "type": ["null", "string"]},
        {"name": "Email", "type": ["null", "string"]},
        {"name": "AccountID", "type": ["null", "string"]},
        {"name": "GroupName", "type": ["null", "string"]},
        {"name": "Active", "type": ["null", "string"]},
    ],
}

ROSTER_ASSIGNMENT_FIELDS = {
    "beta": [
        {"name": "DLSchoolID", "type": ["null", "string"]},
        {"name": "SchoolName", "type": ["null", "string"]},
        {"name": "DLStudentID", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "SecondaryStudentID", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "GradeLevel", "type": ["null", "string"]},
        {"name": "DLRosterID", "type": ["null", "string"]},
        {"name": "RosterName", "type": ["null", "string"]},
        {"name": "IntegrationID", "type": ["null", "string"]},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"]},
    ]
}

PENALTY_FIELDS = {
    "v1": [
        {"name": "IncidentID", "type": ["null", "string"]},
        {"name": "IncidentPenaltyID", "type": ["null", "string"]},
        {"name": "SchoolID", "type": ["null", "string"]},
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "PenaltyID", "type": ["null", "string"]},
        {"name": "PenaltyName", "type": ["null", "string"]},
        {
            "name": "StartDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
        {
            "name": "EndDate",
            "type": ["null", {"type": "string", "logicalType": "date"}],
        },
        {"name": "NumDays", "type": ["null", "float"]},
        {"name": "NumPeriods", "type": ["null", "string"]},
        {"name": "IsSuspension", "type": ["null", "boolean"]},
        {"name": "SAID", "type": ["null", "string"]},
        {"name": "Print", "type": ["null", "boolean"]},
        {"name": "IsReportable", "type": ["null", "boolean"]},
    ]
}

ACTION_FIELDS = {
    "v1": [
        {"name": "SAID", "type": ["null", "string"]},
        {"name": "ActionID", "type": ["null", "string"]},
        {"name": "ActionName", "type": ["null", "string"]},
    ]
}

CUSTOM_FIELD_FIELDS = {
    "v1": [
        {"name": "CustomFieldID", "type": ["null", "string"]},
        {"name": "FieldCategory", "type": ["null", "string"]},
        {"name": "FieldKey", "type": ["null", "string"]},
        {"name": "FieldName", "type": ["null", "string"]},
        {"name": "FieldType", "type": ["null", "string"]},
        {"name": "InputHTML", "type": ["null", "string"]},
        {"name": "InputName", "type": ["null", "string"]},
        {"name": "IsFrontEnd", "type": ["null", "string"]},
        {"name": "LabelHTML", "type": ["null", "string"]},
        {"name": "MinUserLevel", "type": ["null", "string"]},
        {"name": "NumValue", "type": ["null", "float"]},
        {"name": "Options", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"]},
        {"name": "SourceType", "type": ["null", "string"]},
        {"name": "StringValue", "type": ["null", "string"]},
        {"name": "IsRequired", "type": ["null", "string"]},
        {"name": "Value", "type": ["null", "string"]},
    ]
}

INCIDENT_FIELDS = {
    "v1": [
        {"name": "IncidentID", "type": ["null", "string"]},
        {"name": "ReportingIncidentID", "type": ["null", "string"]},
        {"name": "SchoolID", "type": ["null", "string"]},
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "StudentFirst", "type": ["null", "string"]},
        {"name": "StudentMiddle", "type": ["null", "string"]},
        {"name": "StudentLast", "type": ["null", "string"]},
        {"name": "Gender", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "GradeLevelShort", "type": ["null", "string"]},
        {"name": "HomeroomName", "type": ["null", "string"]},
        {"name": "InfractionTypeID", "type": ["null", "string"]},
        {"name": "Infraction", "type": ["null", "string"]},
        {
            "name": "IssueTS",
            "type": [
                "null",
                get_avro_record_schema(
                    name="IssueTS", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "LocationID", "type": ["null", "string"]},
        {"name": "Location", "type": ["null", "string"]},
        {"name": "CategoryID", "type": ["null", "string"]},
        {"name": "Category", "type": ["null", "string"]},
        {"name": "ReportedDetails", "type": ["null", "string"]},
        {"name": "AdminSummary", "type": ["null", "string"]},
        {
            "name": "ReturnDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="ReturnDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "ReturnPeriod", "type": ["null", "string"]},
        {"name": "Context", "type": ["null", "string"]},
        {"name": "AddlReqs", "type": ["null", "string"]},
        {"name": "StatusID", "type": ["null", "string"]},
        {"name": "Status", "type": ["null", "string"]},
        {"name": "FamilyMeetingNotes", "type": ["null", "string"]},
        {"name": "FollowupNotes", "type": ["null", "string"]},
        {"name": "HearingFlag", "type": ["null", "boolean"]},
        {"name": "HearingDate", "type": ["null", "string"]},
        {"name": "HearingTime", "type": ["null", "string"]},
        {"name": "HearingLocation", "type": ["null", "string"]},
        {"name": "HearingNotes", "type": ["null", "string"]},
        {"name": "CreateBy", "type": ["null", "string"]},
        {
            "name": "CreateTS",
            "type": [
                "null",
                get_avro_record_schema(
                    name="CreateTS", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "CreateFirst", "type": ["null", "string"]},
        {"name": "CreateMiddle", "type": ["null", "string"]},
        {"name": "CreateLast", "type": ["null", "string"]},
        {"name": "CreateStaffSchoolID", "type": ["null", "string"]},
        {
            "name": "UpdateTS",
            "type": [
                "null",
                get_avro_record_schema(
                    name="UpdateTS", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "UpdateBy", "type": ["null", "string"]},
        {"name": "UpdateFirst", "type": ["null", "string"]},
        {"name": "UpdateMiddle", "type": ["null", "string"]},
        {"name": "UpdateLast", "type": ["null", "string"]},
        {"name": "UpdateTitle", "type": ["null", "string"]},
        {"name": "UpdateStaffSchoolID", "type": ["null", "string"]},
        {
            "name": "Penalties",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="penalty", fields=PENALTY_FIELDS, version="v1"
                    ),
                },
            ],
        },
        {
            "name": "Actions",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="action", fields=ACTION_FIELDS, version="v1"
                    ),
                },
            ],
        },
        {"name": "IsReferral", "type": ["null", "boolean"]},
        {
            "name": "ReviewTS",
            "type": [
                "null",
                get_avro_record_schema(
                    name="ReviewTS", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {
            "name": "CloseTS",
            "type": [
                "null",
                get_avro_record_schema(
                    name="CloseTS", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "IsActive", "type": ["null", "boolean"]},
        {
            "name": "DL_LASTUPDATE",
            "type": [
                "null",
                get_avro_record_schema(
                    name="DL_LASTUPDATE", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "CreateTitle", "type": ["null", "string"]},
        {"name": "SendAlert", "type": ["null", "boolean"]},
        {
            "name": "Custom_Fields",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="custom_field", fields=CUSTOM_FIELD_FIELDS, version="v1"
                    ),
                },
            ],
        },
    ]
}

LIST_FIELDS = {
    "v1": [
        {"name": "ListID", "type": ["null", "string"]},
        {"name": "ListName", "type": ["null", "string"]},
        {"name": "IsDated", "type": ["null", "boolean"]},
    ]
}

TERM_FIELDS = {
    "v1": [
        {"name": "TermID", "type": ["null", "string"]},
        {"name": "AcademicYearID", "type": ["null", "string"]},
        {"name": "AcademicYearName", "type": ["null", "string"]},
        {"name": "SchoolID", "type": ["null", "string"]},
        {"name": "TermTypeID", "type": ["null", "string"]},
        {"name": "TermType", "type": ["null", "string"]},
        {"name": "TermName", "type": ["null", "string"]},
        {
            "name": "StartDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="StartDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {
            "name": "EndDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="EndDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
    ]
}

ROSTER_FIELDS = {
    "v1": [
        {"name": "RosterID", "type": ["null", "string"]},
        {"name": "RosterName", "type": ["null", "string"]},
        {"name": "RosterTypeID", "type": ["null", "string"]},
        {"name": "RosterType", "type": ["null", "string"]},
        {"name": "MasterID", "type": ["null", "string"]},
        {"name": "MasterName", "type": ["null", "string"]},
        {"name": "TakeAttendance", "type": ["null", "string"]},
        {"name": "TakeClassAttendance", "type": ["null", "string"]},
        {"name": "CollectHW", "type": ["null", "string"]},
        {"name": "MarkerColor", "type": ["null", "string"]},
        {"name": "SISKey", "type": ["null", "string"]},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"]},
        {"name": "ScreenSetID", "type": ["null", "string"]},
        {"name": "StudentCount", "type": ["null", "string"]},
    ]
}

ENROLLMENT_FIELDS = {
    "v1": [
        {"name": "EnrollmentID", "type": ["null", "string"]},
        {"name": "AcademicYearID", "type": ["null", "string"]},
        {"name": "YearName", "type": ["null", "string"]},
        {
            "name": "StartDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="StartDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {
            "name": "EndDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="EndDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "GradeLevelID", "type": ["null", "string"]},
        {"name": "GradeLevelName", "type": ["null", "string"]},
        {"name": "DepartmentID", "type": ["null", "string"]},
        {"name": "DepartmentName", "type": ["null", "string"]},
        {"name": "BehaviorPlanID", "type": ["null", "string"]},
        {"name": "BehaviorPlanName", "type": ["null", "string"]},
        {"name": "CreateByName", "type": ["null", "string"]},
        {
            "name": "CreateDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="CreateDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "TermByName", "type": ["null", "string"]},
        {
            "name": "TermDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="TermDate", fields=TIMESTAMP_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "GradeLevelKey", "type": ["null", "string"]},
    ],
}

STUDENT_FIELDS = {
    "v1": [
        {"name": "StudentID", "type": ["null", "string"]},
        {"name": "DepartmentID", "type": ["null", "string"]},
        {"name": "Department", "type": ["null", "string"]},
        {"name": "GradeLevelID", "type": ["null", "string"]},
        {"name": "GradeLevel", "type": ["null", "string"]},
        {"name": "GradeLevelKey", "type": ["null", "string"]},
        {"name": "FirstName", "type": ["null", "string"]},
        {"name": "MiddleName", "type": ["null", "string"]},
        {"name": "LastName", "type": ["null", "string"]},
        {"name": "StudentSchoolID", "type": ["null", "string"]},
        {"name": "IntegrationID", "type": ["null", "string"]},
        {"name": "EnrollmentStatus", "type": ["null", "string"]},
        {"name": "BehaviorPlan", "type": ["null", "string"]},
        {
            "name": "BirthDate",
            "type": ["string", {"type": "long", "logicalType": "timestamp-micros"}],
        },
        {
            "name": "Enrollment",
            "type": [
                "null",
                get_avro_record_schema(
                    name="enrollment", fields=ENROLLMENT_FIELDS, version="v1"
                ),
            ],
        },
        {"name": "HomeLanguageID", "type": ["null", "string"]},
        {"name": "HomeLanguage", "type": ["null", "string"]},
        {"name": "HomeroomID", "type": ["null", "string"]},
        {"name": "Homeroom", "type": ["null", "string"]},
        {"name": "IsNSLP", "type": ["null", "string"]},
        {"name": "Gender", "type": ["null", "string"]},
        {"name": "StreetAddress1", "type": ["null", "string"]},
        {"name": "StreetAddress2", "type": ["null", "string"]},
        {"name": "City", "type": ["null", "string"]},
        {"name": "State", "type": ["null", "string"]},
        {"name": "ZipCode", "type": ["null", "string"]},
        {"name": "PhotoFile", "type": ["null", "string"]},
        {"name": "DLPS_ValidationCode", "type": ["null", "string"]},
        {"name": "Parents", "type": ["null", {"type": "array", "items": "string"}]},
        {"name": "Notes", "type": ["null", {"type": "array", "items": "string"}]},
    ]
}

ENDPOINT_FIELDS = {
    "behavior": BEHAVIOR_FIELDS,
    "homework": HOMEWORK_FIELDS,
    "comm": COMMUNICATION_FIELDS,
    "comm-log": COMMUNICATION_FIELDS,
    "users": USER_FIELDS,
    "roster-assignments": ROSTER_ASSIGNMENT_FIELDS,
    "incidents": INCIDENT_FIELDS,
    "followups": FOLLOWUP_FIELDS,
    "lists": LIST_FIELDS,
    "terms": TERM_FIELDS,
    "rosters": ROSTER_FIELDS,
    "students": STUDENT_FIELDS,
}
