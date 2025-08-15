from pydantic import BaseModel, Field


class Schools(BaseModel):
    id: str | None = Field(default=None, alias="schools_id")
    dcid: str | None = Field(default=None, alias="schools_dcid")
    abbreviation: str | None = Field(default=None, alias="schools_abbreviation")
    alternate_school_number: str | None = Field(
        default=None, alias="schools_alternate_school_number"
    )
    dfltnextschool: str | None = Field(default=None, alias="schools_dfltnextschool")
    district_number: str | None = Field(default=None, alias="schools_district_number")
    fee_exemption_status: str | None = Field(
        default=None, alias="schools_fee_exemption_status"
    )
    high_grade: str | None = Field(default=None, alias="schools_high_grade")
    hist_high_grade: str | None = Field(default=None, alias="schools_hist_high_grade")
    hist_low_grade: str | None = Field(default=None, alias="schools_hist_low_grade")
    ip_address: str | None = Field(default=None, alias="schools_ip_address")
    issummerschool: str | None = Field(default=None, alias="schools_issummerschool")
    low_grade: str | None = Field(default=None, alias="schools_low_grade")
    name: str | None = Field(default=None, alias="schools_name")
    schedulewhichschool: str | None = Field(
        default=None, alias="schools_schedulewhichschool"
    )
    school_number: str | None = Field(default=None, alias="schools_school_number")
    schoolgroup: str | None = Field(default=None, alias="schools_schoolgroup")
    sortorder: str | None = Field(default=None, alias="schools_sortorder")
    state_excludefromreporting: str | None = Field(
        default=None, alias="schools_state_excludefromreporting"
    )
    transaction_date: str | None = Field(default=None, alias="schools_transaction_date")
    view_in_portal: str | None = Field(default=None, alias="schools_view_in_portal")
    whomodifiedid: str | None = Field(default=None, alias="schools_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="schools_whomodifiedtype")
    activecrslist: str | None = Field(default=None, alias="schools_activecrslist")
    address: str | None = Field(default=None, alias="schools_address")
    asstprincipalemail: str | None = Field(
        default=None, alias="schools_asstprincipalemail"
    )
    schooladdress: str | None = Field(default=None, alias="schools_schooladdress")
    schoolcategorycodesetid: str | None = Field(
        default=None, alias="schools_schoolcategorycodesetid"
    )
    schoolcity: str | None = Field(default=None, alias="schools_schoolcity")
    schoolinfo_guid: str | None = Field(default=None, alias="schools_schoolinfo_guid")
    schoolphone: str | None = Field(default=None, alias="schools_schoolphone")
    schoolstate: str | None = Field(default=None, alias="schools_schoolstate")
    schoolzip: str | None = Field(default=None, alias="schools_schoolzip")
