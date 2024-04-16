import json

import py_avro_schema
from pydantic import BaseModel


class GeneralLedger(BaseModel):
    credit: float | None = None
    customer_id: str | None = None
    date: str | None = None
    debit: float | None = None
    description: str | None = None
    document: str | None = None
    employee_name: str | None = None
    file_number: int | None = None
    gldimdonor_restriction: str | None = None
    gldimfunction: str | None = None
    glentry_classid: int | None = None
    item_id: str | None = None
    job_title: int | None = None
    journal: str | None = None
    line_no: int | None = None
    memo: str | None = None
    position_id: str | None = None
    reference_no: int | None = None
    sourceentity: str | None = None
    state: str | None = None
    vendor_id: str | None = None

    acct_no: str | int | None = None
    dept_id: int | float | None = None
    glentry_projectid: int | float | None = None
    location_id: str | int | float | None = None


class general_ledger_file_record(GeneralLedger):
    """helper classes for backwards compatibility"""


ASSET_SCHEMA = {
    "general_ledger_file": json.loads(
        py_avro_schema.generate(
            py_type=general_ledger_file_record,
            options=py_avro_schema.Option.NO_DOC
            | py_avro_schema.Option.NO_AUTO_NAMESPACE,
        )
    ),
}
