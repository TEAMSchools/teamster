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
