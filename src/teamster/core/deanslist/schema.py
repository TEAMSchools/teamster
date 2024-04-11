import json

import py_avro_schema
from pydantic import BaseModel


class Date(BaseModel):
    date: str | None = None
    timezone_type: int | None = None
    timezone: str | None = None


class CustomField(BaseModel):
    CustomFieldID: str | None = None
    FieldCategory: str | None = None
    FieldKey: str | None = None
    FieldName: str | None = None
    FieldType: str | None = None
    InputHTML: str | None = None
    InputName: str | None = None
    IsFrontEnd: str | None = None
    IsRequired: str | None = None
    LabelHTML: str | None = None
    MinUserLevel: str | None = None
    Options: str | None = None
    SourceID: str | None = None
    SourceType: str | None = None
    StringValue: str | None = None
    Value: str | None = None

    NumValue: int | float | None = None

    SelectedOptions: list[str | None] | None = None


class Behavior(BaseModel):
    DLOrganizationID: str | None = None
    DLSchoolID: str | None = None
    SchoolName: str | None = None
    DLStudentID: str | None = None
    StudentSchoolID: str | None = None
    SecondaryStudentID: str | None = None
    StudentFirstName: str | None = None
    StudentMiddleName: str | None = None
    StudentLastName: str | None = None
    DLSAID: str | None = None
    BehaviorDate: str | None = None
    Behavior: str | None = None
    BehaviorID: str | None = None
    Weight: str | None = None
    BehaviorCategory: str | None = None
    PointValue: str | None = None
    DLUserID: str | None = None
    StaffSchoolID: str | None = None
    StaffTitle: str | None = None
    StaffFirstName: str | None = None
    StaffMiddleName: str | None = None
    StaffLastName: str | None = None
    Roster: str | None = None
    RosterID: str | None = None
    Notes: str | None = None
    DL_LASTUPDATE: str | None = None
    is_deleted: bool | None = None
    SourceType: str | None = None
    SourceID: str | None = None
    SourceProcedure: str | None = None
    Assignment: str | None = None


class StudentModel(BaseModel):
    StudentID: str | None = None
    StudentSchoolID: str | None = None
    SecondaryStudentID: str | None = None
    StudentFirstName: str | None = None
    StudentMiddleName: str | None = None
    StudentLastName: str | None = None


class CommLog(BaseModel):
    RecordID: int | None = None
    RecordType: str | None = None
    UserID: int | None = None
    EducatorName: str | None = None
    CallType: str | None = None
    CallStatusID: int | None = None
    CallStatus: str | None = None
    PersonContacted: str | None = None
    Relationship: str | None = None
    Email: str | None = None
    PhoneNumber: str | None = None
    CallDateTime: str | None = None
    Topic: str | None = None
    Response: str | None = None
    CommunicationWithID: int | None = None
    CommunicationWithType: str | None = None
    CommunicationWithName: str | None = None
    MailingAddress: str | None = None
    ReasonID: int | None = None
    Reason: str | None = None
    IsDraft: bool | None = None
    ThirdPartyName: str | None = None

    Student: StudentModel | None = None

    Followups: list[str | None] | None = None


class Followup(BaseModel):
    FollowupID: str | None = None
    SchoolID: str | None = None
    StudentID: str | None = None
    FollowupType: str | None = None
    SourceID: str | None = None
    StudentSchoolID: str | None = None
    FirstName: str | None = None
    MiddleName: str | None = None
    LastName: str | None = None
    GradeLevelShort: str | None = None
    InitBy: str | None = None
    iFirst: str | None = None
    iMiddle: str | None = None
    iLast: str | None = None
    iTitle: str | None = None
    CloseBy: str | None = None
    cFirst: str | None = None
    cMiddle: str | None = None
    cLast: str | None = None
    cTitle: str | None = None
    InitTS: str | None = None
    OpenTS: str | None = None
    CloseTS: str | None = None
    InitNotes: str | None = None
    Outstanding: str | None = None
    FollowupNotes: str | None = None
    ExtStatus: str | None = None
    TicketStatus: str | None = None
    ResponseType: str | None = None
    ResponseID: str | None = None
    LongType: str | None = None
    URL: str | None = None
    TicketTypeID: str | None = None
    TicketType: str | None = None


class Homework(BaseModel):
    DLOrganizationID: str | None = None
    DLSchoolID: str | None = None
    SchoolName: str | None = None
    DLStudentID: str | None = None
    StudentSchoolID: str | None = None
    SecondaryStudentID: str | None = None
    StudentFirstName: str | None = None
    StudentMiddleName: str | None = None
    StudentLastName: str | None = None
    DLSAID: str | None = None
    BehaviorDate: str | None = None
    BehaviorID: str | None = None
    Behavior: str | None = None
    Weight: str | None = None
    BehaviorCategory: str | None = None
    PointValue: str | None = None
    DLUserID: str | None = None
    StaffSchoolID: str | None = None
    StaffTitle: str | None = None
    StaffFirstName: str | None = None
    StaffMiddleName: str | None = None
    StaffLastName: str | None = None
    Roster: str | None = None
    RosterID: str | None = None
    Notes: str | None = None
    DL_LASTUPDATE: str | None = None
    is_deleted: bool | None = None
    Assignment: str | None = None


class Action(BaseModel):
    ActionID: str | None = None
    ActionName: str | None = None
    PointValue: str | None = None
    SAID: str | None = None
    SourceID: str | None = None


class Penalty(BaseModel):
    IncidentID: str | None = None
    IncidentPenaltyID: str | None = None
    SchoolID: str | None = None
    PenaltyID: str | None = None
    PenaltyName: str | None = None
    StartDate: str | None = None
    EndDate: str | None = None
    NumDays: int | None = None
    NumPeriods: str | None = None
    IsSuspension: bool | None = None
    IsReportable: bool | None = None
    SAID: str | None = None
    Print: bool | None = None
    StudentID: str | None = None


class Incident(BaseModel):
    IncidentID: str | None = None
    ReportingIncidentID: str | None = None
    SchoolID: str | None = None
    StudentID: str | None = None
    StudentFirst: str | None = None
    StudentMiddle: str | None = None
    StudentLast: str | None = None
    Gender: str | None = None
    StudentSchoolID: str | None = None
    GradeLevelShort: str | None = None
    HomeroomName: str | None = None
    InfractionTypeID: str | None = None
    LocationID: str | None = None
    Location: str | None = None
    CategoryID: str | None = None
    Category: str | None = None
    ReportedDetails: str | None = None
    AdminSummary: str | None = None
    Context: str | None = None
    AddlReqs: str | None = None
    StatusID: str | None = None
    Status: str | None = None
    FamilyMeetingNotes: str | None = None
    FollowupNotes: str | None = None
    HearingFlag: bool | None = None
    HearingLocation: str | None = None
    HearingNotes: str | None = None
    CreateBy: str | None = None
    CreateFirst: str | None = None
    CreateMiddle: str | None = None
    CreateLast: str | None = None
    CreateStaffSchoolID: str | None = None
    UpdateBy: str | None = None
    UpdateFirst: str | None = None
    UpdateMiddle: str | None = None
    UpdateLast: str | None = None
    UpdateTitle: str | None = None
    IsReferral: bool | None = None
    IsActive: bool | None = None
    CreateTitle: str | None = None
    SendAlert: bool | None = None
    Infraction: str | None = None
    ReturnPeriod: str | None = None
    HearingDate: str | None = None
    HearingTime: str | None = None
    UpdateStaffSchoolID: str | None = None

    IssueTS: Date | None = None
    ReturnDate: Date | None = None
    CreateTS: Date | None = None
    UpdateTS: Date | None = None
    ReviewTS: Date | None = None
    CloseTS: Date | None = None
    DL_LASTUPDATE: Date | None = None

    Actions: list[Action | None] | None = None
    Penalties: list[Penalty | None] | None = None
    Custom_Fields: list[CustomField | None] | None = None


class ListModel(BaseModel):
    ListID: str | None = None
    ListName: str | None = None
    IsDated: bool | None = None
    IsAccumulation: bool | None = None
    IsSystem: bool | None = None
    IsClearable: bool | None = None
    Show: bool | None = None
    Sort: str | None = None


class RosterAssignment(BaseModel):
    DLSchoolID: str | None = None
    SchoolName: str | None = None
    DLStudentID: str | None = None
    StudentSchoolID: str | None = None
    SecondaryStudentID: str | None = None
    FirstName: str | None = None
    MiddleName: str | None = None
    LastName: str | None = None
    GradeLevel: str | None = None
    DLRosterID: str | None = None
    RosterName: str | None = None
    IntegrationID: str | None = None
    SecondaryIntegrationID: str | None = None


class Roster(BaseModel):
    SchoolID: str | None = None
    RosterID: str | None = None
    RosterName: str | None = None
    RosterTypeID: str | None = None
    RosterType: str | None = None
    MasterID: str | None = None
    MasterName: str | None = None
    TakeAttendance: str | None = None
    TakeClassAttendance: str | None = None
    CollectHW: str | None = None
    SISKey: str | None = None
    SecondaryIntegrationID: str | None = None
    CourseNumber: str | None = None
    SectionNumber: str | None = None
    ShowRoster: str | None = None
    ScreenSetID: str | None = None
    SubjectID: str | None = None
    SubjectName: str | None = None
    Room: str | None = None
    SISExpression: str | None = None
    Period: str | None = None
    MeetingDays: str | None = None
    Active: str | None = None
    LastSynced: str | None = None
    StudentIDs: str | None = None
    GradeLevels: str | None = None
    StudentCount: str | None = None
    MarkerColor: str | None = None
    SISGradebookName: str | None = None
    ScreenSetName: str | None = None
    RTIFocusID: str | None = None
    RTITier: str | None = None


class Term(BaseModel):
    TermID: str | None = None
    AcademicYearID: str | None = None
    AcademicYearName: str | None = None
    SchoolID: str | None = None
    TermTypeID: str | None = None
    TermType: str | None = None
    TermName: str | None = None
    IntegrationID: str | None = None
    SecondaryIntegrationID: str | None = None
    GradeKey: str | None = None
    StoredGrades: bool | None = None
    Days: str | None = None
    SecondaryGradeKey: str | None = None

    StartDate: Date | None = None
    EndDate: Date | None = None


class User(BaseModel):
    AccountID: str | None = None
    Active: str | None = None
    DLSchoolID: str | None = None
    DLUserID: str | None = None
    Email: str | None = None
    FirstName: str | None = None
    GroupName: str | None = None
    LastName: str | None = None
    MiddleName: str | None = None
    SchoolName: str | None = None
    StaffRole: str | None = None
    Title: str | None = None
    Username: str | None = None
    UserSchoolID: str | None = None
    UserStateID: str | None = None


class EnrollmentObject(BaseModel):
    AcademicYearID: str | None = None
    BehaviorPlanID: str | None = None
    BehaviorPlanName: str | None = None
    CreateByName: str | None = None
    CreateDate: str | None = None
    DepartmentID: str | None = None
    DepartmentName: str | None = None
    EnrollmentID: str | None = None
    GradeLevelID: str | None = None
    GradeLevelKey: str | None = None
    GradeLevelName: str | None = None
    TermByName: str | None = None
    TermDate: str | None = None
    YearName: str | None = None

    StartDate: Date | None = None
    EndDate: Date | None = None


class PhoneNumber(BaseModel):
    AutoDial: bool | None = None
    AutoSMS: bool | None = None
    Label: str | None = None
    PhoneNumber: str | None = None
    SPhoneID: str | None = None
    TextDeliverability: str | None = None


class Parent(BaseModel):
    AutoEmail: bool | None = None
    AutoLanguageCode: str | None = None
    CanPickup: bool | None = None
    Email: str | None = None
    FirstName: str | None = None
    Guardian: bool | None = None
    IntegrationKey: str | None = None
    IsEmergency: bool | None = None
    Language: str | None = None
    LanguageCode: str | None = None
    LanguageID: str | None = None
    LastName: str | None = None
    log: str | None = None
    MiddleName: str | None = None
    Provider: str | None = None
    ReceivesMail: bool | None = None
    Relationship: str | None = None
    ResidesWith: bool | None = None
    Sort: str | None = None
    SParentID: str | None = None
    StudentID: str | None = None

    PhoneNumbers: list[PhoneNumber] | None = None


class Student(BaseModel):
    BehaviorPlan: str | None = None
    BirthDate: int | str | None = None
    CellPhone: str | None = None
    City: str | None = None
    Department: str | None = None
    DepartmentID: str | None = None
    DLPS_ValidationCode: str | None = None
    ELLStatus: str | None = None
    Email: str | None = None
    Emoji: str | None = None
    EnrollmentID: str | None = None
    EnrollmentStatus: str | None = None
    Ethnicity: str | None = None
    FirstName: str | None = None
    Gender: str | None = None
    GenderLetter: str | None = None
    GradeLevel: str | None = None
    GradeLevelID: str | None = None
    GradeLevelKey: str | None = None
    GradeLevelShort: str | None = None
    GradeLevelSort: str | None = None
    HomeLanguage: str | None = None
    HomeLanguageCode: str | None = None
    HomeLanguageID: str | None = None
    Homeroom: str | None = None
    HomeroomID: str | None = None
    IntegrationID: str | None = None
    Is504: bool | None = None
    IsNSLP: str | None = None
    LastName: str | None = None
    LegalFirstName: str | None = None
    MessageMerge1: str | None = None
    MessageMerge2: str | None = None
    MessageMerge3: str | None = None
    MiddleName: str | None = None
    PhotoFile: str | None = None
    PhotoFileUrl: str | None = None
    PreferredName: str | None = None
    Pronouns: str | None = None
    SecondaryIntegrationID: str | None = None
    SecondaryStudentID: str | None = None
    SourceSchoolID: str | None = None
    SPEDPlan: str | None = None
    State: str | None = None
    StreetAddress1: str | None = None
    StreetAddress2: str | None = None
    StudentID: str | None = None
    StudentSchoolID: str | None = None
    TransportationNotes: str | None = None
    ZipCode: str | None = None

    Enrollment: EnrollmentObject | None = None

    Notes: list[str | None] | None = None

    Parents: list[Parent | None] | None = None
    CustomFields: list[CustomField | None] | None = None


class ReconcileAttendance(BaseModel):
    attendancebehavior: str | None = None
    attendancedate: str | None = None
    schoolname: str | None = None
    studentfirst: str | None = None
    studentid: int | None = None
    studentlast: str | None = None
    submittedat: str | None = None
    submittedfn: str | None = None
    submittedln: str | None = None
    unnamed_9: str | None = None


class ReconcileSuspensions(BaseModel):
    attendancebehavior: str | None = None
    attendancedate: str | None = None
    conend: str | None = None
    consequence: str | None = None
    constart: str | None = None
    dlincidentid: int | None = None
    schoolname: str | None = None
    studentfirst: str | None = None
    studentid: int | None = None
    studentlast: str | None = None
    submittedat: str | None = None
    submittedfn: str | None = None
    submittedln: str | None = None
    unnamed_13: str | None = None


"""
helper classes for backwards compatibility
"""


class behavior_record(Behavior): ...


class comm_log_record(CommLog): ...


class followups_record(Followup): ...


class homework_record(Homework): ...


class incidents_record(Incident): ...


ASSET_SCHEMA = {
    "behavior": json.loads(
        py_avro_schema.generate(py_type=behavior_record, namespace="behavior")
    ),
    "comm-log": json.loads(
        py_avro_schema.generate(py_type=comm_log_record, namespace="comm_log")
    ),
    "followups": json.loads(
        py_avro_schema.generate(py_type=Followup, namespace="followup")
    ),
    "homework": json.loads(
        py_avro_schema.generate(py_type=homework_record, namespace="homework")
    ),
    "incidents": json.loads(
        py_avro_schema.generate(py_type=incidents_record, namespace="incident")
    ),
    "lists": json.loads(py_avro_schema.generate(py_type=ListModel, namespace="list")),
    "roster-assignments": json.loads(
        py_avro_schema.generate(py_type=RosterAssignment, namespace="roster_assignment")
    ),
    "rosters": json.loads(py_avro_schema.generate(py_type=Roster, namespace="roster")),
    "students": json.loads(
        py_avro_schema.generate(py_type=Student, namespace="student")
    ),
    "terms": json.loads(py_avro_schema.generate(py_type=Term, namespace="term")),
    "users": json.loads(py_avro_schema.generate(py_type=User, namespace="user")),
    "reconcile_attendance": json.loads(
        py_avro_schema.generate(
            py_type=ReconcileAttendance, namespace="reconcile_attendance"
        )
    ),
    "reconcile_suspensions": json.loads(
        py_avro_schema.generate(
            py_type=ReconcileSuspensions, namespace="reconcile_suspension"
        )
    ),
}
