import json

import py_avro_schema
from pydantic import BaseModel


class View(BaseModel):
    content_url: str | None = None
    id: str | None = None
    name: str | None = None
    owner_id: str | None = None
    project_id: str | None = None
    total_views: int | None = None


class view_record(View):
    """helper class for backwards compatibility"""


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

    views: list[view_record | None] | None = None


class workbook_record(Workbook):
    """helper class for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

ASSET_SCHEMA = {
    "workbook": json.loads(
        py_avro_schema.generate(py_type=workbook_record, options=pas_options)
    ),
}
