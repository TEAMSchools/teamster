import json

from py_avro_schema import generate
from pydantic import BaseModel


class CleverCore(BaseModel):
    clever_school_id: str | None = None
    clever_user_id: str | None = None
    date: str | None = None
    school_name: str | None = None

    sis_id: str | int | None = None
    staff_id: str | int | None = None


class ResourceUsage(CleverCore):
    num_access: int | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    resource_type: str | None = None


class DailyParticipation(CleverCore):
    active: bool | None = None
    num_logins: int | None = None
    num_resources_accessed: int | None = None


ASSET_FIELDS = {
    "daily_participation": json.loads(
        generate(py_type=DailyParticipation, namespace="daily_participation")
    ),
    "resource_usage": json.loads(
        generate(py_type=ResourceUsage, namespace="resource_usage")
    ),
}
