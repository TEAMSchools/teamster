from pydantic import BaseModel


class GeneralLedger(BaseModel):
    acct_no: str | None = None
    credit: str | None = None
    customer_id: str | None = None
    date: str | None = None
    debit: str | None = None
    dept_id: str | None = None
    description: str | None = None
    document: str | None = None
    employee_name: str | None = None
    file_number: str | None = None
    gldimdonor_restriction: str | None = None
    gldimfunction: str | None = None
    glentry_classid: str | None = None
    glentry_projectid: str | None = None
    item_id: str | None = None
    job_title: str | None = None
    journal: str | None = None
    line_no: str | None = None
    location_id: str | None = None
    memo: str | None = None
    position_id: str | None = None
    reference_no: str | None = None
    sourceentity: str | None = None
    state: str | None = None
    vendor_id: str | None = None
