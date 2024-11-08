from pydantic import BaseModel, Field


class Code(BaseModel):
    codeValue: str | None = None
    longName: str | None = None
    shortName: str | None = None
    effectiveDate: str | None = None


class RaceCode(Code):
    identificationMethodCode: Code | None = None


class CountrySubdivisionLevel(Code):
    subdivisionType: str


class CustomField(BaseModel):
    itemID: str

    nameCode: Code


class CodeField(CustomField, Code): ...


class DateField(CustomField):
    dateValue: str | None = None


class NumberField(CustomField):
    numberValue: float | None = None


class MultiCodeField(CustomField):
    codes: list[Code]


class StringField(CustomField):
    stringValue: str | None = None


class IndicatorField(CustomField):
    indicatorValue: bool | None = None


class Phone(BaseModel):
    areaDialing: str
    countryDialing: str
    dialNumber: str
    formattedNumber: str
    itemID: str
    access: str | None = None
    extension: str | None = None

    nameCode: Code


class Email(BaseModel):
    emailUri: str
    itemID: str | None = None
    notificationIndicator: bool

    nameCode: Code


class Address(BaseModel):
    cityName: str | None = None
    countryCode: str | None = None
    itemID: str | None = None
    lineOne: str | None = None
    lineTwo: str | None = None
    lineThree: str | None = None
    postalCode: str | None = None

    countrySubdivisionLevel1: CountrySubdivisionLevel | None = None
    countrySubdivisionLevel2: CountrySubdivisionLevel | None = None
    nameCode: Code | None = None
    typeCode: Code | None = None


class GovernmentID(BaseModel):
    countryCode: str
    idValue: str
    itemID: str
    expirationDate: str | None = None

    nameCode: Code
    statusCode: Code | None = None


class PreferredSalutation(BaseModel):
    salutationCode: Code


class Name(BaseModel):
    formattedName: str | None = None
    familyName1: str | None = None
    givenName: str | None = None
    middleName: str | None = None
    nickName: str | None = None

    generationAffixCode: Code | None = None
    qualificationAffixCode: Code | None = None

    preferredSalutations: list[PreferredSalutation] | None = None


class SocialInsuranceProgram(BaseModel):
    coveredIndicator: bool

    nameCode: Code


class AssignmentStatus(BaseModel):
    effectiveDate: str | None = None

    statusCode: Code
    reasonCode: Code | None = None


class WorkerGroup(BaseModel):
    groupCode: Code
    nameCode: Code


class WageLawCoverage(BaseModel):
    coverageCode: Code
    wageLawNameCode: Code


class OrganizationalUnit(BaseModel):
    nameCode: Code
    typeCode: Code


class WorkLocation(BaseModel):
    address: Address | None = None
    nameCode: Code | None = None


class StandardPayPeriodHours(BaseModel):
    hoursQuantity: float


class Rate(BaseModel):
    amountValue: float
    currencyCode: str | None = None

    nameCode: Code | None = None


class BaseRemuneration(BaseModel):
    effectiveDate: str

    annualRateAmount: Rate
    payPeriodRateAmount: Rate | None = None
    hourlyRateAmount: Rate | None = None
    dailyRateAmount: Rate | None = None


class AdditionalRemuneration(BaseModel):
    itemID: str
    effectiveDate: str

    nameCode: Code
    rate: Rate


class OccupationalClassification(BaseModel):
    nameCode: Code
    classificationCode: Code


class StandardHours(BaseModel):
    hoursQuantity: float

    unitCode: Code


class Link(BaseModel):
    href: str
    mediaType: str
    method: str


class Photo(BaseModel):
    links: list[Link]


class Communication(BaseModel):
    emails: list[Email] | None = None
    landlines: list[Phone] | None = None
    mobiles: list[Phone] | None = None


class WorkerStatus(BaseModel):
    statusCode: Code


class WorkerID(BaseModel):
    idValue: str

    schemeCode: Code | None = None


class ReportsToItem(BaseModel):
    associateOID: str
    positionID: str

    reportsToWorkerName: Name
    workerID: WorkerID


class WorkerDates(BaseModel):
    originalHireDate: str
    terminationDate: str | None = None
    rehireDate: str | None = None


class CustomFieldGroup(BaseModel):
    codeFields: list[CodeField] | None = None
    dateFields: list[DateField] | None = None
    indicatorFields: list[IndicatorField] | None = None
    multiCodeFields: list[MultiCodeField] | None = None
    numberFields: list[NumberField] | None = None
    stringFields: list[StringField] | None = None


class Person(BaseModel):
    birthDate: str
    disabledIndicator: bool
    militaryDischargeDate: str | None = None
    tobaccoUserIndicator: bool | None = None

    birthName: Name | None = None
    communication: Communication | None = None
    customFieldGroup: CustomFieldGroup
    ethnicityCode: Code | None = None
    genderCode: Code
    genderSelfIdentityCode: Code | None = None
    highestEducationLevelCode: Code | None = None
    legalAddress: Address | None = None
    legalName: Name
    maritalStatusCode: Code | None = None
    militaryStatusCode: Code | None = None
    preferredGenderPronounCode: Code | None = None
    preferredName: Name
    raceCode: RaceCode | None = None

    disabilityTypeCodes: list[Code] | None = None
    governmentIDs: list[GovernmentID] | None = None
    militaryClassificationCodes: list[Code]
    otherPersonalAddresses: list[Address] | None = None
    socialInsurancePrograms: list[SocialInsuranceProgram] | None = None


class WorkAssignment(BaseModel):
    actualStartDate: str
    fullTimeEquivalenceRatio: float | None = None
    hireDate: str
    itemID: str
    jobTitle: str | None = None
    managementPositionIndicator: bool
    payrollFileNumber: str | None = None
    payrollGroupCode: str | None = None
    payrollScheduleGroupID: str | None = None
    positionID: str
    primaryIndicator: bool
    seniorityDate: str | None = None
    terminationDate: str | None = None
    voluntaryIndicator: bool | None = None

    assignmentStatus: AssignmentStatus
    baseRemuneration: BaseRemuneration | None = None
    customFieldGroup: CustomFieldGroup | None = None
    homeWorkLocation: WorkLocation | None = None
    jobCode: Code | None = None
    payCycleCode: Code | None = None
    payrollProcessingStatusCode: Code
    standardHours: StandardHours | None = None
    standardPayPeriodHours: StandardPayPeriodHours | None = None
    wageLawCoverage: WageLawCoverage | None = None
    workerTypeCode: Code | None = None

    additionalRemunerations: list[AdditionalRemuneration] | None = None
    assignedOrganizationalUnits: list[OrganizationalUnit] | None = None
    assignedWorkLocations: list[WorkLocation] | None = None
    homeOrganizationalUnits: list[OrganizationalUnit] | None = None
    occupationalClassifications: list[OccupationalClassification] | None = None
    reportsTo: list[ReportsToItem] | None = None
    workerGroups: list[WorkerGroup] | None = None


class Worker(BaseModel):
    associateOID: str
    customFieldGroup: CustomFieldGroup
    person: Person
    workerDates: WorkerDates
    workerID: WorkerID
    workerStatus: WorkerStatus
    businessCommunication: Communication | None = None
    field_languageCode: Code | None = Field(default=None, alias="_languageCode")

    photos: list[Photo] | None = None
    workAssignments: list[WorkAssignment]
