from pydantic import BaseModel


class User(BaseModel):
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    employee_number: str | None = None


class Enrollment(BaseModel):
    enrollment_id: int | None = None
    content_type: str | None = None
    module_name: str | None = None
    user: User | None = None
    campaign_name: str | None = None
    enrollment_date: str | None = None
    start_date: str | None = None
    completion_date: str | None = None
    status: str | None = None
    time_spent: int | None = None
    policy_acknowledged: bool | None = None
    score: float | None = None
