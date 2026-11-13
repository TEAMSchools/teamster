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
    nj_se_delayreason: str | None = None
    nj_se_earlyintervention: str | None = None
    nj_se_eligibilityddate: str | None = None
    nj_se_initialiepmeetingdate: str | None = None
    nj_se_lastiepmeetingdate: str | None = None
    nj_se_parentalconsentdate: str | None = None
    nj_se_parentalconsentobtained: str | None = None
    nj_se_placement: str | None = None
    nj_se_reevaluationdate: str | None = None
    nj_se_referraldate: str | None = None
    nj_timeinregularprogram: str | None = None
    preschooledenvironment: str | None = None
    schoolageedenvironment: str | None = None
    sldbasicreadingskills: str | None = None
    sldlisteningcomprehension: str | None = None
    sldmathcalculations: str | None = None
    sldmathproblemsolving: str | None = None
    sldoralexpression: str | None = None
    sldreadingcomprehension: str | None = None
    sldreadingfluency: str | None = None
    sldwrittenexpression: str | None = None
    special_education: str | None = None
    state_studentnumber: str | None = None
    student_number: str | None = None
    ti_serv_counseling: str | None = None
    ti_serv_occup: str | None = None
    ti_serv_other: str | None = None
    ti_serv_physical: str | None = None
    ti_serv_speech: str | None = None
    source_file_name: str | None = None


class Section504StudentReport(BaseModel):
    internal_student_id: str | None = None
    school: str | None = None
    last_name: str | None = None
    first_name: str | None = None
    state_id: str | None = None
    student_id: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    ethnicity: str | None = None
    race_abbrev_csv_list: str | None = None
    grade_abbrev: str | None = None
    student_status: str | None = None
    date_snapshot_section_504_eligibility_y_n: str | None = None
    date_snapshot_historical_section_504_eligibility_y_n: str | None = None
    section_504_case_manager: str | None = None
    event_selector: str | None = None
    event_type: str | None = None
    document_id: str | None = None
    event_date: str | None = None
    primary_disability: str | None = None
    secondary_disability: str | None = None
    third_disability: str | None = None
    begin_date: str | None = None
    end_date: str | None = None
    source_file_name: str | None = None
