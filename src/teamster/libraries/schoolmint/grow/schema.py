from pydantic import BaseModel, Field


class Ref(BaseModel):
    name: str | None = None
    field_id: str | None = Field(None, alias="_id")


class Timestamp(BaseModel):
    archivedAt: str | None = None
    created: str | None = None
    lastModified: str | None = None


class Tag(Ref):
    url: str | None = None


class UserRef(Ref):
    email: str | None = None


class Progress(BaseModel):
    percent: int | None = None
    date: str | None = None
    justification: str | None = None
    assigner: str | None = None
    field_id: str | None = Field(None, alias="_id")


class Content(BaseModel):
    left: str | None = None
    right: str | None = None


class AdditionalField(Ref):
    description: str | None = None
    disableDeleting: bool | None = None
    disableEnableParticipantCopyToggle: bool | None = None
    disableHideUntilMeetingStartToggle: bool | None = None
    disablePrivateToggle: bool | None = None
    enableHiding: bool | None = None
    enableParticipantsCopy: bool | None = None
    hidden: bool | None = None
    hiddenUntilMeetingStart: bool | None = None
    isPrivate: bool | None = None
    key: str | None = None
    leftName: str | None = None
    rightName: str | None = None
    type: str | None = None

    content: bool | int | str | Content | None = None


class SignedItem(BaseModel):
    signed: bool | None = None
    user: str | None = None
    field_id: str | None = Field(None, alias="_id")


class Type(Ref):
    canRequireSignature: bool | None = None
    canBePrivate: bool | None = None


class Participant(BaseModel):
    user: str | None = None
    isAbsent: bool | None = None
    customCategory: str | None = None
    field_id: str | None = Field(None, alias="_id")


class MeasurementOption(BaseModel):
    label: str | None = None
    description: str | None = None
    value: int | None = None
    booleanValue: bool | None = None
    created: str | None = None
    percentage: float | None = None
    field_id: str | None = Field(None, alias="_id")


class VideoUser(BaseModel):
    user: str | None = None
    role: str | None = None
    sharedAt: str | None = None
    field_id: str | None = Field(None, alias="_id")


class VideoNote(BaseModel):
    text: str | None = None
    createdOnMillisecond: int | None = None
    creator: str | None = None
    shared: bool | None = None
    timestamp: str | None = None
    field_id: str | None = Field(None, alias="_id")


class ObservationGroup(Ref):
    observees: list[UserRef | None] | None = None
    observers: list[UserRef | None] | None = None


class DefaultInformation(BaseModel):
    school: str | None = None
    gradeLevel: str | None = None
    course: str | None = None


class PluConfig(BaseModel):
    startDate: str | None = None
    endDate: str | None = None
    required: int | None = None


class AdminDashboard(BaseModel):
    hidden: list[str | None] | None = None


class NavBar(BaseModel):
    shortcuts: list[str | None] | None = None


class ObsPage(BaseModel):
    panelWidth: str | None = None

    collapsedPanes: list[str | None] | None = None


class Preferences(BaseModel):
    timezone: int | None = None
    timezoneText: str | None = None
    actionsDashTimeframe: str | None = None
    homepage: str | None = None
    showTutorial: bool | None = None
    showActionStepMessage: bool | None = None
    showDCPSMessage: bool | None = None
    showSystemWideMessage: bool | None = None
    lastSchoolSelected: str | None = None

    adminDashboard: AdminDashboard | None = None
    navBar: NavBar | None = None
    obsPage: ObsPage | None = None

    unsubscribedTo: list[str | None] | None = None


class Expectations(BaseModel):
    meeting: int | None = None
    exceeding: int | None = None
    meetingAggregate: int | None = None
    exceedingAggregate: int | None = None
    summary: str | None = None


class Usertype(Ref, Timestamp):
    abbreviation: str | None = None
    creator: str | None = None
    district: str | None = None
    field__v: int | None = Field(None, alias="__v")

    expectations: Expectations | None = None


class ExternalIntegration(BaseModel):
    type: str | None = None
    id: str | None = None


class DistrictDatum(BaseModel):
    field_id: str | None = Field(None, alias="_id")
    archivedAt: str | None = None
    coach: str | None = None
    course: str | None = None
    district: str | None = None
    evaluator: str | None = None
    grade: str | None = None
    inactive: bool | None = None
    internalId: str | None = None
    locked: bool | None = None
    nonInstructional: bool | None = None
    readonly: bool | None = None
    school: str | None = None
    showOnDashboards: bool | None = None
    usertag1: str | None = None
    videoLicense: bool | None = None

    pluConfig: PluConfig | None = None
    usertype: Usertype | None = None


class MeasurementRef(BaseModel):
    field_id: str | None = Field(None, alias="_id")
    key: str | None = None
    isPrivate: bool | None = None
    require: bool | None = None
    weight: float | None = None
    measurement: str | None = None
    exclude: bool | None = None


class MeasurementGroup(Ref):
    key: str | None = None
    description: str | None = None
    weight: int | None = None

    measurements: list[MeasurementRef | None] | None = None


class Resource(BaseModel):
    label: str | None = None
    url: str | None = None
    field_id: str | None = Field(None, alias="_id")


class FeatureInstruction(BaseModel):
    hideOnDraft: bool | None = None
    hideOnFinalized: bool | None = None
    includeOnEmails: bool | None = None
    section: str | None = None
    text: str | None = None
    titleOverride: str | None = None
    field_id: str | None = Field(None, alias="_id")


class FormItem(BaseModel):
    assignmentSlug: str | None = None
    hideOnDraft: bool | None = None
    hideOnFinalized: bool | None = None
    includeInEmail: bool | None = None
    mustBeMainPanel: bool | None = None
    rubricMeasurement: str | None = None
    showOnFinalizedPopup: bool | None = None
    widgetDescription: str | None = None
    widgetKey: str | None = None
    widgetTitle: str | None = None


class Layout(BaseModel):
    formLeft: list[FormItem | None] | None = None
    formWide: list[FormItem | None] | None = None


class Role(Ref):
    category: str | None = None
    district: str | None = None


class RolesExcluded(Role, Timestamp):
    visibleRoles: list[str | None] | None = None
    privileges: list[str | None] | None = None


class Settings(BaseModel):
    actionStep: bool | None = None
    actionStepCreate: bool | None = None
    actionStepWorkflow: bool | None = None
    allowCoTeacher: bool | None = None
    allowTakeOverObservation: bool | None = None
    cloneable: bool | None = None
    coachActionStep: bool | None = None
    coachingEvalType: str | None = None
    customHtml: str | None = None
    customHtml1: str | None = None
    customHtml2: str | None = None
    customHtml3: str | None = None
    customHtmlTitle: str | None = None
    customHtmlTitle1: str | None = None
    customHtmlTitle2: str | None = None
    customHtmlTitle3: str | None = None
    dashHidden: bool | None = None
    debrief: bool | None = None
    defaultCourse: str | None = None
    defaultObsModule: str | None = None
    defaultObsTag1: str | None = None
    defaultObsTag2: str | None = None
    defaultObsTag3: str | None = None
    defaultObsTag4: str | None = None
    defaultObsType: str | None = None
    defaultUsertype: str | None = None
    descriptionsInEditor: bool | None = None
    disableMeetingsTab: bool | None = None
    displayLabels: bool | None = None
    displayNumbers: bool | None = None
    dontRequireTextboxesOnLikertRows: bool | None = None
    enableClickToFill: bool | None = None
    enablePointClick: bool | None = None
    filters: bool | None = None
    goalCreate: bool | None = None
    goals: bool | None = None
    hasCompletionMarks: bool | None = None
    hasRowDescriptions: bool | None = None
    hideEmptyRows: bool | None = None
    hideEmptyTextRows: bool | None = None
    hideFromCoaches: bool | None = None
    hideFromLists: bool | None = None
    hideFromRegionalCoaches: bool | None = None
    hideFromSchoolAdmins: bool | None = None
    hideFromSchoolAssistantAdmins: bool | None = None
    hideFromTeachers: bool | None = None
    hideOverallScore: bool | None = None
    isAlwaysFocus: bool | None = None
    isCoachingStartForm: bool | None = None
    isCompetencyRubric: bool | None = None
    isHolisticDefault: bool | None = None
    isPeerRubric: bool | None = None
    isPrivate: bool | None = None
    isScorePrivate: bool | None = None
    isSiteVisit: bool | None = None
    locked: bool | None = None
    meetingQuickCreate: bool | None = None
    meetingTypesExcludedFromScheduling: bool | None = None
    nameAndSignatureDisplay: bool | None = None
    notification: bool | None = None
    notificationNote: bool | None = None
    obsShowEndDate: bool | None = None
    obsTypeFinalize: bool | None = None
    prepopulateActionStep: str | None = None
    quickHits: str | None = None
    requireActionStepBeforeFinalize: bool | None = None
    requireAll: bool | None = None
    requireGoal: bool | None = None
    requireObservationType: bool | None = None
    requireOnlyScores: bool | None = None
    rubrictag1: str | None = None
    scoreOnForm: bool | None = None
    scoreOverride: bool | None = None
    scripting: bool | None = None
    sendEmailOnSignature: bool | None = None
    showAllTextOnOpts: bool | None = None
    showAvgByStrand: bool | None = None
    showObservationLabels: bool | None = None
    showObservationModule: bool | None = None
    showObservationTag1: bool | None = None
    showObservationTag2: bool | None = None
    showObservationTag3: bool | None = None
    showObservationTag4: bool | None = None
    showObservationType: bool | None = None
    showOnDataReports: bool | None = None
    showStrandScores: bool | None = None
    signature: bool | None = None
    signatureOnByDefault: bool | None = None
    transferDescriptionToTextbox: bool | None = None
    useAdditiveScoring: bool | None = None
    useStrandWeights: bool | None = None
    video: bool | None = None
    videoForm: bool | None = None

    lockScoreAfterDays: int | str | None = None

    hiddenFeatures: list[str | None] | None = None
    observationTypesHidden: list[str | None] | None = None
    privateRows: list[str | None] | None = None
    requiredRows: list[str | None] | None = None
    schoolsExcluded: list[str | None] | None = None

    featureInstructions: list[FeatureInstruction | None] | None = None
    resources: list[Resource | None] | None = None

    rolesExcluded: list[str | RolesExcluded | None] | None = None


class TagNote(BaseModel):
    notes: str | None = None
    tags: list[str | None] | None = None


class TeachingAssignment(DefaultInformation):
    grade: str | None = None
    period: str | None = None
    field_id: str | None = Field(None, alias="_id")


class MagicNote(BaseModel):
    column: str | None = None
    shared: bool | None = None
    text: str | None = None
    created: str | None = None
    field_id: str | None = Field(None, alias="_id")


class VideoRef(BaseModel):
    video: str | None = None
    includeVideoTimestamps: bool | None = None


class Checkbox(BaseModel):
    label: str | None = None
    value: bool | None = None


class TextBox(BaseModel):
    key: str | None = None
    label: str | None = None
    value: str | None = None


class ObservationScore(BaseModel):
    measurement: str | None = None
    measurementGroup: str | None = None
    valueText: str | None = None
    percentage: float | None = None
    valueScore: int | None = None
    lastModified: str | None = None

    checkboxes: list[Checkbox | None] | None = None
    textBoxes: list[TextBox | None] | None = None


class Attachment(BaseModel):
    creator: str | None = None
    file: str | None = None
    id: str | None = None
    private: bool | None = None
    resource: str | None = None
    created: str | None = None
    field_id: str | None = Field(None, alias="_id")


class Assignment(Ref, Timestamp):
    coachingActivity: bool | None = None
    excludeFromBank: bool | None = None
    locked: bool | None = None
    private: bool | None = None
    observation: str | None = None
    type: str | None = None
    goalType: str | None = None

    creator: UserRef | None = None
    parent: Ref | None = None
    progress: Progress | None = None
    user: UserRef | None = None

    tags: list[Tag | None] | None = None


class GenericTag(Tag, Timestamp):
    order: int | None = None
    creator: str | None = None
    district: str | None = None
    abbreviation: str | None = None
    parent: str | None = None
    color: str | None = None
    showOnDash: bool | None = None
    field__v: int | None = Field(None, alias="__v")

    parents: list[str | None] | None = None
    rows: list[str | None] | None = None
    tags: list[str | None] | None = None


class MeetingTypeTag(GenericTag):
    coachingEvalType: str | None = None
    description: str | None = None

    canBePrivate: bool | None = None
    canRequireSignature: bool | None = None
    enableClickToFill: bool | None = None
    enableModule: bool | None = None
    enableParticipantsCopy: bool | None = None
    enablePhases: bool | None = None
    enableTag1: bool | None = None
    enableTag2: bool | None = None
    enableTag3: bool | None = None
    enableTag4: bool | None = None
    hideFromLists: bool | None = None
    isWeeklyDataMeeting: bool | None = None
    videoForm: bool | None = None

    excludedModules: list[str | None] | None = None
    excludedTag1s: list[str | None] | None = None
    excludedTag2s: list[str | None] | None = None
    excludedTag3s: list[str | None] | None = None
    excludedTag4s: list[str | None] | None = None
    rolesExcluded: list[str | None] | None = None
    schoolsExcluded: list[str | None] | None = None
    customAbsentCategories: list[str | None] | None = None

    resources: list[Resource | None] | None = None
    additionalFields: list[AdditionalField | None] | None = None


class AssignmentPresetTag(GenericTag):
    type: str | None = None


class TagTag(GenericTag):
    type: str | None = None


class UserTypeTag(GenericTag):
    expectations: Expectations | None = None


class Informal(Ref, Timestamp):
    shared: str | None = None
    private: str | None = None
    district: str | None = None

    user: UserRef | None = None
    creator: UserRef | None = None

    tags: list[Ref | None] | None = None


class Measurement(Ref, Timestamp):
    description: str | None = None
    district: str | None = None
    rowStyle: str | None = None
    scaleMax: int | None = None
    scaleMin: int | None = None

    measurementOptions: list[MeasurementOption | None] | None = None
    textBoxes: list[TextBox | None] | None = None


class Meeting(Ref, Timestamp):
    isTemplate: bool | None = None
    isWeeklyDataMeeting: bool | None = None
    isOpenToParticipants: bool | None = None
    locked: bool | None = None
    private: bool | None = None
    signatureRequired: bool | None = None
    date: str | None = None
    enablePhases: bool | None = None
    title: str | None = None
    course: str | None = None
    grade: str | None = None
    school: str | None = None
    district: str | None = None
    meetingtag1: str | None = None

    creator: UserRef | None = None
    type: Type | None = None

    actionSteps: list[str | None] | None = None
    observations: list[str | None] | None = None
    offweek: list[str | None] | None = None
    onleave: list[str | None] | None = None
    unable: list[str | None] | None = None

    additionalFields: list[AdditionalField | None] | None = None
    participants: list[Participant | None] | None = None
    signed: list[SignedItem | None] | None = None


class Observation(Ref, Timestamp):
    assignActionStepWidgetText: str | None = None
    district: str | None = None
    firstPublished: str | None = None
    isPrivate: bool | None = None
    isPublished: bool | None = None
    lastPublished: str | None = None
    locked: bool | None = None
    observationModule: str | None = None
    observationtag1: str | None = None
    observationtag2: str | None = None
    observationtag3: str | None = None
    observationType: str | None = None
    observedAt: str | None = None
    observedUntil: str | None = None
    privateNotes1: str | None = None
    privateNotes2: str | None = None
    privateNotes3: str | None = None
    privateNotes4: str | None = None
    quickHits: str | None = None
    requireSignature: bool | None = None
    score: float | None = None
    scoreAveragedByStrand: float | None = None
    sendEmail: bool | None = None
    sharedNotes1: str | None = None
    sharedNotes2: str | None = None
    sharedNotes3: str | None = None
    signed: bool | None = None
    signedAt: str | None = None
    viewedByTeacher: str | None = None

    rubric: Ref | None = None
    observer: UserRef | None = None
    teacher: UserRef | None = None
    tagNotes1: TagNote | None = None
    tagNotes2: TagNote | None = None
    tagNotes3: TagNote | None = None
    tagNotes4: TagNote | None = None
    teachingAssignment: TeachingAssignment | None = None

    meetings: list[str | None] | None = None
    tags: list[str | None] | None = None
    comments: list[str | None] | None = None
    listTwoColumnA: list[str | None] | None = None
    listTwoColumnB: list[str | None] | None = None
    listTwoColumnAPaired: list[str | None] | None = None
    listTwoColumnBPaired: list[str | None] | None = None
    eventLog: list[str | None] | None = None
    files: list[str | None] | None = None

    observationScores: list[ObservationScore | None] | None = None
    magicNotes: list[MagicNote | None] | None = None
    videoNotes: list[VideoNote | None] | None = None
    attachments: list[Attachment | None] | None = None
    videos: list[VideoRef | None] | None = None


class Rubric(Ref, Timestamp):
    isPrivate: bool | None = None
    isPublished: bool | None = None
    order: int | None = None
    scaleMin: int | None = None
    scaleMax: int | None = None
    district: str | None = None

    settings: Settings | None = None
    layout: Layout | None = None

    measurementGroups: list[MeasurementGroup | None] | None = None


class School(Ref, Timestamp):
    abbreviation: str | None = None
    address: str | None = None
    city: str | None = None
    gradeSpan: str | None = None
    highGrade: str | None = None
    internalId: str | None = None
    lowGrade: str | None = None
    phone: str | None = None
    principal: str | None = None
    region: str | None = None
    state: str | None = None
    zip: str | None = None
    district: str | None = None

    nonInstructionalAdmins: list[str | None] | None = None

    admins: list[UserRef | None] | None = None
    assistantAdmins: list[UserRef | None] | None = None
    observationGroups: list[ObservationGroup | None] | None = None


class User(UserRef, Timestamp):
    internalId: str | None = None
    accountingId: str | None = None
    canvasId: str | None = None
    cleverId: str | None = None
    googleid: str | None = None
    oktaId: str | None = None
    powerSchoolId: str | None = None
    sibmeId: str | None = None
    coach: str | None = None
    evaluator: str | None = None
    first: str | None = None
    last: str | None = None
    lastActivity: str | None = None
    usertag1: str | None = None
    usertag2: str | None = None
    usertag3: str | None = None
    usertag4: str | None = None
    usertag5: str | None = None
    usertag6: str | None = None
    usertag7: str | None = None
    usertag8: str | None = None
    inactive: bool | None = None
    locked: bool | None = None
    nonInstructional: bool | None = None
    readonly: bool | None = None
    showOnDashboards: bool | None = None
    videoLicense: bool | None = None
    calendarEmail: str | None = None
    endOfYearLog: str | None = None
    endOfYearVisible: str | None = None
    isPracticeUser: str | None = None
    pastUserTypes: str | None = None
    sibmeToken: str | None = None
    track: str | None = None

    defaultInformation: DefaultInformation | None = None
    pluConfig: PluConfig | None = None
    preferences: Preferences | None = None
    usertype: Usertype | None = None

    additionalEmails: list[str | None] | None = None
    districts: list[str | None] | None = None

    districtData: list[DistrictDatum | None] | None = None
    externalIntegrations: list[ExternalIntegration | None] | None = None
    regionalAdminSchools: list[Ref | None] | None = None
    roles: list[Role | None] | None = None


class Video(Ref, Timestamp):
    url: str | None = None
    status: str | None = None
    style: str | None = None
    district: str | None = None
    fileName: str | None = None
    zencoderJobId: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    isCollaboration: bool | None = None
    parent: str | None = None
    key: str | None = None

    creator: Ref | None = None

    editors: list[str | None] | None = None
    commenters: list[str | None] | None = None
    comments: list[str | None] | None = None
    observations: list[str | None] | None = None
    tags: list[str | None] | None = None

    users: list[VideoUser | None] | None = None
    videoNotes: list[VideoNote | None] | None = None
