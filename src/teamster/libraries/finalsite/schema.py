from pydantic import BaseModel


class StatusReport(BaseModel):
    finalsite_student_id: str | None = None
    powerschool_student_number: str | None = None
    enrollment_year: str | None = None
    enrollment_type: str | None = None
    status: str | None = None
    timestamp: str | None = None
    last_name: str | None = None
    first_name: str | None = None
    grade_level: str | None = None
    school: str | None = None
