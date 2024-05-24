from pydantic import BaseModel


class DirectoryBaseModel(BaseModel):
    kind: str | None = None
    etag: str | None = None


class RolePrivilege(BaseModel):
    privilegeName: str | None = None
    serviceId: str | None = None


class Group(DirectoryBaseModel):
    id: str | None = None
    email: str | None = None
    name: str | None = None
    directMembersCount: str | None = None
    description: str | None = None
    adminCreated: bool | None = None

    nonEditableAliases: list[str | None] | None = None
    aliases: list[str | None] | None = None


class Member(DirectoryBaseModel):
    id: str | None = None
    email: str | None = None
    role: str | None = None
    type: str | None = None
    status: str | None = None


class RoleAssignment(DirectoryBaseModel):
    roleAssignmentId: str | None = None
    roleId: str | None = None
    assignedTo: str | None = None
    assigneeType: str | None = None
    scopeType: str | None = None
    orgUnitId: str | None = None


class Role(DirectoryBaseModel):
    roleId: str | None = None
    roleName: str | None = None
    roleDescription: str | None = None
    isSystemRole: bool | None = None
    isSuperAdminRole: bool | None = None

    rolePrivileges: list[RolePrivilege | None] | None = None


class OrganizationUnit(DirectoryBaseModel):
    name: str | None = None
    description: str | None = None
    orgUnitPath: str | None = None
    orgUnitId: str | None = None
    parentOrgUnitPath: str | None = None
    parentOrgUnitId: str | None = None
    blockInheritance: bool | None = None


class OrgUnits(DirectoryBaseModel):
    organizationUnits: list[OrganizationUnit | None] | None = None


class Name(BaseModel):
    givenName: str | None = None
    familyName: str | None = None
    fullName: str | None = None


class Email(BaseModel):
    address: str | None = None
    primary: bool | None = None
    type: str | None = None
    customType: str | None = None


class Language(BaseModel):
    languageCode: str | None = None
    preference: str | None = None


class Gender(BaseModel):
    type: str | None = None


class Relation(BaseModel):
    value: str | None = None
    type: str | None = None


class Organization(BaseModel):
    primary: bool | None = None
    customType: str | None = None
    title: str | None = None
    department: str | None = None
    description: str | None = None
    costCenter: str | None = None


class Notes(BaseModel):
    value: str | None = None


class ExternalId(BaseModel):
    value: str | None = None
    type: str | None = None


class StudentAttributes(BaseModel):
    Student_Number: int | None = None


class CustomSchemas(BaseModel):
    Student_attributes: StudentAttributes | None = None


class Phone(BaseModel):
    value: str | None = None
    type: str | None = None


class User(DirectoryBaseModel):
    id: str | None = None
    primaryEmail: str | None = None
    isAdmin: bool | None = None
    isDelegatedAdmin: bool | None = None
    lastLoginTime: str | None = None
    creationTime: str | None = None
    agreedToTerms: bool | None = None
    suspended: bool | None = None
    suspensionReason: str | None = None
    archived: bool | None = None
    changePasswordAtNextLogin: bool | None = None
    ipWhitelisted: bool | None = None
    customerId: str | None = None
    orgUnitPath: str | None = None
    isMailboxSetup: bool | None = None
    isEnrolledIn2Sv: bool | None = None
    isEnforcedIn2Sv: bool | None = None
    includeInGlobalAddressList: bool | None = None
    thumbnailPhotoUrl: str | None = None
    thumbnailPhotoEtag: str | None = None
    recoveryEmail: str | None = None
    recoveryPhone: str | None = None

    gender: Gender | None = None
    notes: Notes | None = None
    customSchemas: CustomSchemas | None = None
    name: Name | None = None

    nonEditableAliases: list[str | None] | None = None
    aliases: list[str | None] | None = None

    emails: list[Email | None] | None = None
    languages: list[Language | None] | None = None
    relations: list[Relation | None] | None = None
    organizations: list[Organization | None] | None = None
    externalIds: list[ExternalId | None] | None = None
    phones: list[Phone | None] | None = None
