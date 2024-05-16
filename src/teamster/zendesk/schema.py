from pydantic import BaseModel


class Minutes(BaseModel):
    calendar: int | None = None
    business: int | None = None


class TicketMetric(BaseModel):
    id: int | None = None
    ticket_id: int | None = None
    assignee_stations: int | None = None
    group_stations: int | None = None
    reopens: int | None = None
    replies: int | None = None
    url: str | None = None
    assignee_updated_at: str | None = None
    assigned_at: str | None = None
    created_at: str | None = None
    initially_assigned_at: str | None = None
    latest_comment_added_at: str | None = None
    requester_updated_at: str | None = None
    solved_at: str | None = None
    status_updated_at: str | None = None
    updated_at: str | None = None

    agent_wait_time_in_minutes: Minutes | None = None
    first_resolution_time_in_minutes: Minutes | None = None
    full_resolution_time_in_minutes: Minutes | None = None
    on_hold_time_in_minutes: Minutes | None = None
    reply_time_in_minutes: Minutes | None = None
    requester_wait_time_in_minutes: Minutes | None = None
