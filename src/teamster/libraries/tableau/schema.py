from pydantic import BaseModel


class View(BaseModel):
    content_url: str | None = None
    id: str | None = None
    name: str | None = None
    owner_id: str | None = None
    project_id: str | None = None
    total_views: int | None = None


class Workbook(BaseModel):
    content_url: str | None = None
    id: str | None = None
    name: str | None = None
    owner_id: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    size: int | None = None
    show_tabs: bool | None = None
    webpage_url: str | None = None

    views: list[View | None] | None = None
