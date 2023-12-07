from teamster.core.utils.functions import get_avro_record_schema

TIMESTAMP_FIELDS = {
    "v1": [
        {"name": "timezone_type", "type": ["null", "int"], "default": None},
        {"name": "timezone", "type": ["null", "string"], "default": None},
        {
            "name": "date",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ]
}

BEHAVIOR_FIELDS = {
    "beta": [
        {"name": "Assignment", "type": ["null", "string"], "default": None},
        {"name": "Behavior", "type": ["null", "string"], "default": None},
        {"name": "BehaviorCategory", "type": ["null", "string"], "default": None},
        {"name": "BehaviorID", "type": ["null", "string"], "default": None},
        {"name": "DLOrganizationID", "type": ["null", "string"], "default": None},
        {"name": "DLSAID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
        {"name": "Notes", "type": ["null", "string"], "default": None},
        {"name": "PointValue", "type": ["null", "string"], "default": None},
        {"name": "Roster", "type": ["null", "string"], "default": None},
        {"name": "RosterID", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
        {"name": "SourceProcedure", "type": ["null", "string"], "default": None},
        {"name": "SourceType", "type": ["null", "string"], "default": None},
        {"name": "StaffFirstName", "type": ["null", "string"], "default": None},
        {"name": "StaffLastName", "type": ["null", "string"], "default": None},
        {"name": "StaffMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "StaffTitle", "type": ["null", "string"], "default": None},
        {"name": "StudentFirstName", "type": ["null", "string"], "default": None},
        {"name": "StudentLastName", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "Weight", "type": ["null", "string"], "default": None},
        {
            "name": "BehaviorDate",
            "type": ["null", "string"],
            "logicalType": "date",
            "default": None,
        },
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ],
    "v1": [
        {"name": "Assignment", "type": ["null", "string"], "default": None},
        {"name": "Behavior", "type": ["null", "string"], "default": None},
        {"name": "BehaviorCategory", "type": ["null", "string"], "default": None},
        {"name": "BehaviorID", "type": ["null", "string"], "default": None},
        {"name": "DLOrganizationID", "type": ["null", "string"], "default": None},
        {"name": "DLSAID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
        {"name": "Notes", "type": ["null", "string"], "default": None},
        {"name": "PointValue", "type": ["null", "string"], "default": None},
        {"name": "Roster", "type": ["null", "string"], "default": None},
        {"name": "RosterID", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
        {"name": "SourceProcedure", "type": ["null", "string"], "default": None},
        {"name": "SourceType", "type": ["null", "string"], "default": None},
        {"name": "StaffFirstName", "type": ["null", "string"], "default": None},
        {"name": "StaffLastName", "type": ["null", "string"], "default": None},
        {"name": "StaffMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "StaffTitle", "type": ["null", "string"], "default": None},
        {"name": "StudentFirstName", "type": ["null", "string"], "default": None},
        {"name": "StudentLastName", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "Weight", "type": ["null", "string"], "default": None},
        {
            "name": "BehaviorDate",
            "type": ["null", "string"],
            "logicalType": "date",
            "default": None,
        },
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ],
}

HOMEWORK_FIELDS = {
    "beta": [
        {"name": "Assignment", "type": ["null", "string"], "default": None},
        {"name": "Behavior", "type": ["null", "string"], "default": None},
        {"name": "BehaviorCategory", "type": ["null", "string"], "default": None},
        {"name": "BehaviorDate", "type": ["null", "string"], "default": None},
        {"name": "BehaviorID", "type": ["null", "string"], "default": None},
        {"name": "DLOrganizationID", "type": ["null", "string"], "default": None},
        {"name": "DLSAID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
        {"name": "Notes", "type": ["null", "string"], "default": None},
        {"name": "PointValue", "type": ["null", "string"], "default": None},
        {"name": "Roster", "type": ["null", "string"], "default": None},
        {"name": "RosterID", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "StaffFirstName", "type": ["null", "string"], "default": None},
        {"name": "StaffLastName", "type": ["null", "string"], "default": None},
        {"name": "StaffMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "StaffTitle", "type": ["null", "string"], "default": None},
        {"name": "StudentFirstName", "type": ["null", "string"], "default": None},
        {"name": "StudentLastName", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "Weight", "type": ["null", "string"], "default": None},
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ],
    "v1": [
        {"name": "Assignment", "type": ["null", "string"], "default": None},
        {"name": "Behavior", "type": ["null", "string"], "default": None},
        {"name": "BehaviorCategory", "type": ["null", "string"], "default": None},
        {"name": "BehaviorDate", "type": ["null", "string"], "default": None},
        {"name": "BehaviorID", "type": ["null", "string"], "default": None},
        {"name": "DLOrganizationID", "type": ["null", "string"], "default": None},
        {"name": "DLSAID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "is_deleted", "type": ["null", "boolean"], "default": None},
        {"name": "Notes", "type": ["null", "string"], "default": None},
        {"name": "PointValue", "type": ["null", "string"], "default": None},
        {"name": "Roster", "type": ["null", "string"], "default": None},
        {"name": "RosterID", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "StaffFirstName", "type": ["null", "string"], "default": None},
        {"name": "StaffLastName", "type": ["null", "string"], "default": None},
        {"name": "StaffMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "StaffTitle", "type": ["null", "string"], "default": None},
        {"name": "StudentFirstName", "type": ["null", "string"], "default": None},
        {"name": "StudentLastName", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "Weight", "type": ["null", "string"], "default": None},
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ],
}

FOLLOWUP_FIELDS = {
    "v1": [
        {"name": "cFirst", "type": ["null", "string"], "default": None},
        {"name": "cLast", "type": ["null", "string"], "default": None},
        {"name": "CloseBy", "type": ["null", "string"], "default": None},
        {"name": "cMiddle", "type": ["null", "string"], "default": None},
        {"name": "cTitle", "type": ["null", "string"], "default": None},
        {"name": "ExtStatus", "type": ["null", "string"], "default": None},
        {"name": "FirstName", "type": ["null", "string"], "default": None},
        {"name": "FollowupID", "type": ["null", "string"], "default": None},
        {"name": "FollowupNotes", "type": ["null", "string"], "default": None},
        {"name": "FollowupType", "type": ["null", "string"], "default": None},
        {"name": "GradeLevelShort", "type": ["null", "string"], "default": None},
        {"name": "iFirst", "type": ["null", "string"], "default": None},
        {"name": "iLast", "type": ["null", "string"], "default": None},
        {"name": "iMiddle", "type": ["null", "string"], "default": None},
        {"name": "InitBy", "type": ["null", "string"], "default": None},
        {"name": "InitNotes", "type": ["null", "string"], "default": None},
        {"name": "iTitle", "type": ["null", "string"], "default": None},
        {"name": "LastName", "type": ["null", "string"], "default": None},
        {"name": "LongType", "type": ["null", "string"], "default": None},
        {"name": "MiddleName", "type": ["null", "string"], "default": None},
        {"name": "Outstanding", "type": ["null", "string"], "default": None},
        {"name": "ResponseID", "type": ["null", "string"], "default": None},
        {"name": "ResponseType", "type": ["null", "string"], "default": None},
        {"name": "SchoolID", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
        {"name": "StudentID", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "TicketStatus", "type": ["null", "string"], "default": None},
        {"name": "TicketType", "type": ["null", "string"], "default": None},
        {"name": "TicketTypeID", "type": ["null", "string"], "default": None},
        {"name": "URL", "type": ["null", "string"], "default": None},
        {
            "name": "InitTS",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
        {
            "name": "CloseTS",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
        {
            "name": "OpenTS",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ]
}

STUDENT_FIELDS = {
    "v1": [
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "StudentFirstName", "type": ["null", "string"], "default": None},
        {"name": "StudentID", "type": ["null", "string"], "default": None},
        {"name": "StudentLastName", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddleName", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
    ]
}

COMMUNICATION_FIELDS = {
    "beta": [
        {"name": "CallStatus", "type": ["null", "string"], "default": None},
        {"name": "CallTopic", "type": ["null", "string"], "default": None},
        {"name": "CallType", "type": ["null", "string"], "default": None},
        {"name": "CommWith", "type": ["null", "string"], "default": None},
        {"name": "DLCallLogID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "Email", "type": ["null", "string"], "default": None},
        {"name": "FollowupBy", "type": ["null", "string"], "default": None},
        {"name": "FollowupCloseTS", "type": ["null", "string"], "default": None},
        {"name": "FollowupID", "type": ["null", "string"], "default": None},
        {"name": "FollowupInitTS", "type": ["null", "string"], "default": None},
        {"name": "FollowupOutstanding", "type": ["null", "string"], "default": None},
        {"name": "FollowupRequest", "type": ["null", "string"], "default": None},
        {"name": "FollowupResponse", "type": ["null", "string"], "default": None},
        {"name": "IsActive", "type": ["null", "string"], "default": None},
        {"name": "MailingAddress", "type": ["null", "string"], "default": None},
        {"name": "PersonContacted", "type": ["null", "string"], "default": None},
        {"name": "PhoneNumber", "type": ["null", "string"], "default": None},
        {"name": "Reason", "type": ["null", "string"], "default": None},
        {"name": "Relationship", "type": ["null", "string"], "default": None},
        {"name": "Response", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
        {"name": "SourceType", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "ThirdParty", "type": ["null", "string"], "default": None},
        {"name": "UserFirstName", "type": ["null", "string"], "default": None},
        {"name": "UserLastName", "type": ["null", "string"], "default": None},
        {"name": "UserSchoolID", "type": ["null", "string"], "default": None},
        {
            "name": "CallDateTime",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
        {
            "name": "DL_LASTUPDATE",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ],
    "v1": [
        {"name": "CallStatus", "type": ["null", "string"], "default": None},
        {"name": "CallStatusID", "type": ["null", "int"], "default": None},
        {"name": "CallType", "type": ["null", "string"], "default": None},
        {"name": "EducatorName", "type": ["null", "string"], "default": None},
        {"name": "Email", "type": ["null", "string"], "default": None},
        {"name": "IsDraft", "type": ["null", "boolean"], "default": None},
        {"name": "MailingAddress", "type": ["null", "string"], "default": None},
        {"name": "PhoneNumber", "type": ["null", "string"], "default": None},
        {"name": "Reason", "type": ["null", "string"], "default": None},
        {"name": "ReasonID", "type": ["null", "int"], "default": None},
        {"name": "RecordID", "type": ["null", "int"], "default": None},
        {"name": "RecordType", "type": ["null", "string"], "default": None},
        {"name": "Response", "type": ["null", "string"], "default": None},
        {"name": "Topic", "type": ["null", "string"], "default": None},
        {"name": "UserID", "type": ["null", "int"], "default": None},
        {
            "name": "CallDateTime",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
        {
            "name": "Followups",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="followup", fields=FOLLOWUP_FIELDS["v1"]
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "Student",
            "type": [
                "null",
                get_avro_record_schema(name="student", fields=STUDENT_FIELDS["v1"]),
            ],
            "default": None,
        },
    ],
}

USER_FIELDS = {
    "beta": [
        {"name": "AccountID", "type": ["null", "string"], "default": None},
        {"name": "Active", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "Email", "type": ["null", "string"], "default": None},
        {"name": "FirstName", "type": ["null", "string"], "default": None},
        {"name": "GroupName", "type": ["null", "string"], "default": None},
        {"name": "LastName", "type": ["null", "string"], "default": None},
        {"name": "MiddleName", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "StaffRole", "type": ["null", "string"], "default": None},
        {"name": "Title", "type": ["null", "string"], "default": None},
        {"name": "Username", "type": ["null", "string"], "default": None},
        {"name": "UserSchoolID", "type": ["null", "string"], "default": None},
        {"name": "UserStateID", "type": ["null", "string"], "default": None},
    ],
    "v1": [
        {"name": "AccountID", "type": ["null", "string"], "default": None},
        {"name": "Active", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLUserID", "type": ["null", "string"], "default": None},
        {"name": "Email", "type": ["null", "string"], "default": None},
        {"name": "FirstName", "type": ["null", "string"], "default": None},
        {"name": "GroupName", "type": ["null", "string"], "default": None},
        {"name": "LastName", "type": ["null", "string"], "default": None},
        {"name": "MiddleName", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "StaffRole", "type": ["null", "string"], "default": None},
        {"name": "Title", "type": ["null", "string"], "default": None},
        {"name": "Username", "type": ["null", "string"], "default": None},
        {"name": "UserSchoolID", "type": ["null", "string"], "default": None},
        {"name": "UserStateID", "type": ["null", "string"], "default": None},
    ],
}

ROSTER_ASSIGNMENT_FIELDS = {
    "beta": [
        {"name": "DLRosterID", "type": ["null", "string"], "default": None},
        {"name": "DLSchoolID", "type": ["null", "string"], "default": None},
        {"name": "DLStudentID", "type": ["null", "string"], "default": None},
        {"name": "FirstName", "type": ["null", "string"], "default": None},
        {"name": "GradeLevel", "type": ["null", "string"], "default": None},
        {"name": "IntegrationID", "type": ["null", "string"], "default": None},
        {"name": "LastName", "type": ["null", "string"], "default": None},
        {"name": "MiddleName", "type": ["null", "string"], "default": None},
        {"name": "RosterName", "type": ["null", "string"], "default": None},
        {"name": "SchoolName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"], "default": None},
        {"name": "SecondaryStudentID", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
    ]
}

PENALTY_FIELDS = {
    "v1": [
        {"name": "IncidentID", "type": ["null", "string"], "default": None},
        {"name": "IncidentPenaltyID", "type": ["null", "string"], "default": None},
        {"name": "IsReportable", "type": ["null", "boolean"], "default": None},
        {"name": "IsSuspension", "type": ["null", "boolean"], "default": None},
        {"name": "NumDays", "type": ["null", "float"], "default": None},
        {"name": "NumPeriods", "type": ["null", "string"], "default": None},
        {"name": "PenaltyID", "type": ["null", "string"], "default": None},
        {"name": "PenaltyName", "type": ["null", "string"], "default": None},
        {"name": "Print", "type": ["null", "boolean"], "default": None},
        {"name": "SAID", "type": ["null", "string"], "default": None},
        {"name": "SchoolID", "type": ["null", "string"], "default": None},
        {"name": "StudentID", "type": ["null", "string"], "default": None},
        {
            "name": "EndDate",
            "type": ["null", "string"],
            "logicalType": "date",
            "default": None,
        },
        {
            "name": "StartDate",
            "type": ["null", "string"],
            "logicalType": "date",
            "default": None,
        },
    ]
}

ACTION_FIELDS = {
    "v1": [
        {"name": "ActionID", "type": ["null", "string"], "default": None},
        {"name": "ActionName", "type": ["null", "string"], "default": None},
        {"name": "PointValue", "type": ["null", "string"], "default": None},
        {"name": "SAID", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
    ]
}

CUSTOM_FIELD_FIELDS = {
    "v1": [
        {"name": "CustomFieldID", "type": ["null", "string"], "default": None},
        {"name": "FieldCategory", "type": ["null", "string"], "default": None},
        {"name": "FieldKey", "type": ["null", "string"], "default": None},
        {"name": "FieldName", "type": ["null", "string"], "default": None},
        {"name": "FieldType", "type": ["null", "string"], "default": None},
        {"name": "InputHTML", "type": ["null", "string"], "default": None},
        {"name": "InputName", "type": ["null", "string"], "default": None},
        {"name": "IsFrontEnd", "type": ["null", "string"], "default": None},
        {"name": "IsRequired", "type": ["null", "string"], "default": None},
        {"name": "LabelHTML", "type": ["null", "string"], "default": None},
        {"name": "MinUserLevel", "type": ["null", "string"], "default": None},
        {"name": "NumValue", "type": ["null", "float"], "default": None},
        {"name": "Options", "type": ["null", "string"], "default": None},
        {"name": "SourceID", "type": ["null", "string"], "default": None},
        {"name": "SourceType", "type": ["null", "string"], "default": None},
        {"name": "StringValue", "type": ["null", "string"], "default": None},
        {"name": "Value", "type": ["null", "string"], "default": None},
        {
            "name": "SelectedOptions",
            "type": ["null", {"type": "array", "items": "string", "default": []}],
            "default": None,
        },
    ]
}

INCIDENT_FIELDS = {
    "v1": [
        {"name": "AddlReqs", "type": ["null", "string"], "default": None},
        {"name": "AdminSummary", "type": ["null", "string"], "default": None},
        {"name": "Category", "type": ["null", "string"], "default": None},
        {"name": "CategoryID", "type": ["null", "string"], "default": None},
        {"name": "Context", "type": ["null", "string"], "default": None},
        {"name": "CreateBy", "type": ["null", "string"], "default": None},
        {"name": "CreateFirst", "type": ["null", "string"], "default": None},
        {"name": "CreateLast", "type": ["null", "string"], "default": None},
        {"name": "CreateMiddle", "type": ["null", "string"], "default": None},
        {"name": "CreateStaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "CreateTitle", "type": ["null", "string"], "default": None},
        {"name": "FamilyMeetingNotes", "type": ["null", "string"], "default": None},
        {"name": "FollowupNotes", "type": ["null", "string"], "default": None},
        {"name": "Gender", "type": ["null", "string"], "default": None},
        {"name": "GradeLevelShort", "type": ["null", "string"], "default": None},
        {"name": "HearingFlag", "type": ["null", "boolean"], "default": None},
        {"name": "HearingLocation", "type": ["null", "string"], "default": None},
        {"name": "HearingNotes", "type": ["null", "string"], "default": None},
        {"name": "HearingTime", "type": ["null", "string"], "default": None},
        {"name": "HomeroomName", "type": ["null", "string"], "default": None},
        {"name": "IncidentID", "type": ["null", "string"], "default": None},
        {"name": "Infraction", "type": ["null", "string"], "default": None},
        {"name": "InfractionTypeID", "type": ["null", "string"], "default": None},
        {"name": "IsActive", "type": ["null", "boolean"], "default": None},
        {"name": "IsReferral", "type": ["null", "boolean"], "default": None},
        {"name": "Location", "type": ["null", "string"], "default": None},
        {"name": "LocationID", "type": ["null", "string"], "default": None},
        {"name": "ReportedDetails", "type": ["null", "string"], "default": None},
        {"name": "ReportingIncidentID", "type": ["null", "string"], "default": None},
        {"name": "ReturnPeriod", "type": ["null", "string"], "default": None},
        {"name": "SchoolID", "type": ["null", "string"], "default": None},
        {"name": "SendAlert", "type": ["null", "boolean"], "default": None},
        {"name": "Status", "type": ["null", "string"], "default": None},
        {"name": "StatusID", "type": ["null", "string"], "default": None},
        {"name": "StudentFirst", "type": ["null", "string"], "default": None},
        {"name": "StudentID", "type": ["null", "string"], "default": None},
        {"name": "StudentLast", "type": ["null", "string"], "default": None},
        {"name": "StudentMiddle", "type": ["null", "string"], "default": None},
        {"name": "StudentSchoolID", "type": ["null", "string"], "default": None},
        {"name": "UpdateBy", "type": ["null", "string"], "default": None},
        {"name": "UpdateFirst", "type": ["null", "string"], "default": None},
        {"name": "UpdateLast", "type": ["null", "string"], "default": None},
        {"name": "UpdateMiddle", "type": ["null", "string"], "default": None},
        {"name": "UpdateStaffSchoolID", "type": ["null", "string"], "default": None},
        {"name": "UpdateTitle", "type": ["null", "string"], "default": None},
        {
            "name": "ReturnDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="ReturnDate", fields=TIMESTAMP_FIELDS["v1"]
                ),
            ],
            "default": None,
        },
        {
            "name": "HearingDate",
            "type": [
                "null",
                get_avro_record_schema(
                    name="HearingDate", fields=TIMESTAMP_FIELDS["v1"]
                ),
            ],
            "default": None,
        },
        {
            "name": "CreateTS",
            "type": [
                "null",
                get_avro_record_schema(name="CreateTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "UpdateTS",
            "type": [
                "null",
                get_avro_record_schema(name="UpdateTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "ReviewTS",
            "type": [
                "null",
                get_avro_record_schema(name="ReviewTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "IssueTS",
            "type": [
                "null",
                get_avro_record_schema(name="IssueTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "CloseTS",
            "type": [
                "null",
                get_avro_record_schema(name="CloseTS", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "DL_LASTUPDATE",
            "type": [
                "null",
                get_avro_record_schema(
                    name="DL_LASTUPDATE", fields=TIMESTAMP_FIELDS["v1"]
                ),
            ],
            "default": None,
        },
        {
            "name": "Penalties",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="penalty", fields=PENALTY_FIELDS["v1"]
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "Actions",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="action", fields=ACTION_FIELDS["v1"]
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "Custom_Fields",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="custom_field", fields=CUSTOM_FIELD_FIELDS["v1"]
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
    ]
}

LIST_FIELDS = {
    "v1": [
        {"name": "IsDated", "type": ["null", "boolean"], "default": None},
        {"name": "ListID", "type": ["null", "string"], "default": None},
        {"name": "ListName", "type": ["null", "string"], "default": None},
        {"name": "Show", "type": ["null", "boolean"], "default": None},
        {"name": "IsAccumulation", "type": ["null", "boolean"], "default": None},
        {"name": "Sort", "type": ["null", "string"], "default": None},
        {"name": "IsClearable", "type": ["null", "boolean"], "default": None},
        {"name": "IsSystem", "type": ["null", "boolean"], "default": None},
    ]
}

TERM_FIELDS = {
    "v1": [
        {"name": "AcademicYearID", "type": ["null", "string"], "default": None},
        {"name": "AcademicYearName", "type": ["null", "string"], "default": None},
        {"name": "Days", "type": ["null", "string"], "default": None},
        {"name": "GradeKey", "type": ["null", "string"], "default": None},
        {"name": "IntegrationID", "type": ["null", "string"], "default": None},
        {"name": "SchoolID", "type": ["null", "string"], "default": None},
        {"name": "SecondaryGradeKey", "type": ["null", "string"], "default": None},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"], "default": None},
        {"name": "StoredGrades", "type": ["null", "boolean"], "default": None},
        {"name": "TermID", "type": ["null", "string"], "default": None},
        {"name": "TermName", "type": ["null", "string"], "default": None},
        {"name": "TermType", "type": ["null", "string"], "default": None},
        {"name": "TermTypeID", "type": ["null", "string"], "default": None},
        {
            "name": "StartDate",
            "type": [
                "null",
                get_avro_record_schema(name="StartDate", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
        {
            "name": "EndDate",
            "type": [
                "null",
                get_avro_record_schema(name="EndDate", fields=TIMESTAMP_FIELDS["v1"]),
            ],
            "default": None,
        },
    ]
}

ROSTER_FIELDS = {
    "v1": [
        {"name": "Active", "type": ["null", "string"], "default": None},
        {"name": "CollectHW", "type": ["null", "string"], "default": None},
        {"name": "CourseNumber", "type": ["null", "string"], "default": None},
        {"name": "GradeLevels", "type": ["null", "string"], "default": None},
        {"name": "MarkerColor", "type": ["null", "string"], "default": None},
        {"name": "MasterID", "type": ["null", "string"], "default": None},
        {"name": "MasterName", "type": ["null", "string"], "default": None},
        {"name": "MeetingDays", "type": ["null", "string"], "default": None},
        {"name": "Period", "type": ["null", "string"], "default": None},
        {"name": "Room", "type": ["null", "string"], "default": None},
        {"name": "RosterID", "type": ["null", "string"], "default": None},
        {"name": "RosterName", "type": ["null", "string"], "default": None},
        {"name": "RosterType", "type": ["null", "string"], "default": None},
        {"name": "RosterTypeID", "type": ["null", "string"], "default": None},
        {"name": "RTIFocusID", "type": ["null", "string"], "default": None},
        {"name": "RTITier", "type": ["null", "string"], "default": None},
        {"name": "SchoolID", "type": ["null", "string"], "default": None},
        {"name": "ScreenSetID", "type": ["null", "string"], "default": None},
        {"name": "ScreenSetName", "type": ["null", "string"], "default": None},
        {"name": "SecondaryIntegrationID", "type": ["null", "string"], "default": None},
        {"name": "SectionNumber", "type": ["null", "string"], "default": None},
        {"name": "ShowRoster", "type": ["null", "string"], "default": None},
        {"name": "SISExpression", "type": ["null", "string"], "default": None},
        {"name": "SISGradebookName", "type": ["null", "string"], "default": None},
        {"name": "SISKey", "type": ["null", "string"], "default": None},
        {"name": "StudentCount", "type": ["null", "string"], "default": None},
        {"name": "SubjectID", "type": ["null", "string"], "default": None},
        {"name": "SubjectName", "type": ["null", "string"], "default": None},
        {"name": "TakeAttendance", "type": ["null", "string"], "default": None},
        {"name": "TakeClassAttendance", "type": ["null", "string"], "default": None},
        {"name": "StudentIDs", "type": ["null", "string"], "default": None},
        {
            "name": "LastSynced",
            "type": ["null", "string"],
            "logicalType": "timestamp-micros",
            "default": None,
        },
    ]
}

ASSET_FIELDS = {
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
