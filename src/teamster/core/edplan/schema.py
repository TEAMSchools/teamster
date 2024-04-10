import json

from py_avro_schema import generate
from pydantic import BaseModel


class NJSmartPowerschool(BaseModel):
    declassificationspeddate: str | None = None
    dob: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    mddisabling_condition1: str | None = None
    mddisabling_condition2: str | None = None
    mddisabling_condition3: str | None = None
    mddisabling_condition4: str | None = None
    mddisabling_condition5: str | None = None
    nj_se_consenttoimplementdate: str | None = None
    nj_se_delayreason: float | None = None
    nj_se_earlyintervention: str | None = None
    nj_se_eligibilityddate: str | None = None
    nj_se_initialiepmeetingdate: str | None = None
    nj_se_lastiepmeetingdate: str | None = None
    nj_se_parentalconsentdate: str | None = None
    nj_se_parentalconsentobtained: str | None = None
    nj_se_placement: float | None = None
    nj_se_reevaluationdate: str | None = None
    nj_se_referraldate: str | None = None
    nj_timeinregularprogram: str | None = None
    special_education: float | None = None
    student_number: int | None = None
    ti_serv_counseling: str | None = None
    ti_serv_occup: str | None = None
    ti_serv_other: str | None = None
    ti_serv_physical: str | None = None
    ti_serv_speech: str | None = None

    state_studentnumber: int | float | None = None


class NJSmartPowerschoolArchive(BaseModel):
    academic_year: int | None = None
    case_manager: str | None = None
    effective_date: str | None = None
    effective_end_date: str | None = None
    file: str | None = None
    iepbegin_date: str | None = None
    iepend_date: str | None = None
    iepgraduation_attendance: str | None = None
    iepgraduation_course_requirement: str | None = None
    line: int | None = None
    nj_se_consenttoimplementdate: str | None = None
    nj_se_delayreason: float | None = None
    nj_se_eligibilityddate: str | None = None
    nj_se_initialiepmeetingdate: str | None = None
    nj_se_lastiepmeetingdate: str | None = None
    nj_se_parental_consentobtained: str | None = None
    nj_se_parentalconsentdate: str | None = None
    nj_se_placement: float | None = None
    nj_se_reevaluationdate: str | None = None
    nj_se_referraldate: str | None = None
    nj_timeinregularprogram: str | None = None
    rn_stu_yr: int | None = None
    row_hash: str | None = None
    special_education_code: str | None = None
    special_education: float | None = None
    spedlep: str | None = None
    state_studentnumber: float | None = None
    student_number: float | None = None
    ti_serv_counseling: str | None = None
    ti_serv_occup: str | None = None
    ti_serv_other: str | None = None
    ti_serv_physical: str | None = None
    ti_serv_speech: str | None = None


ASSET_FIELDS = {
    "njsmart_powerschool": json.loads(
        generate(py_type=NJSmartPowerschool, namespace="njsmart_powerschool")
    ),
    "njsmart_powerschool_archive": json.loads(
        generate(
            py_type=NJSmartPowerschoolArchive, namespace="njsmart_powerschool_archive"
        )
    ),
}
