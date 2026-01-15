from pydantic import BaseModel


class SubmissionRecord(BaseModel):
    id: int | None = None
    status: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    dateOfBirth: str | None = None
    externalStudentID: str | None = None
    externalFamilyID: str | None = None
    household: str | None = None
    school: str | None = None
    grade: str | None = None
    enrollStatus: str | None = None
    imported: str | None = None
    started: str | None = None
    submitted: str | None = None

    tags: list[str | None] | None = None
    dataItems: dict[str, str | None] | None = None
