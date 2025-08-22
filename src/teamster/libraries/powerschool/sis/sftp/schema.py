from pydantic import BaseModel, Field


class Users(BaseModel):
    dcid: str | None = Field(default=None, validation_alias="users_dcid")
    access: str | None = Field(default=None, validation_alias="users_access")
    adminldapenabled: str | None = Field(
        default=None, validation_alias="users_adminldapenabled"
    )
    allowloginend: str | None = Field(
        default=None, validation_alias="users_allowloginend"
    )
    allowloginstart: str | None = Field(
        default=None, validation_alias="users_allowloginstart"
    )
    canchangeschool: str | None = Field(
        default=None, validation_alias="users_canchangeschool"
    )
    city: str | None = Field(default=None, validation_alias="users_city")
    defaultstudscrn: str | None = Field(
        default=None, validation_alias="users_defaultstudscrn"
    )
    email_addr: str | None = Field(default=None, validation_alias="users_email_addr")
    ethnicity: str | None = Field(default=None, validation_alias="users_ethnicity")
    fedethnicity: str | None = Field(
        default=None, validation_alias="users_fedethnicity"
    )
    fedracedecline: str | None = Field(
        default=None, validation_alias="users_fedracedecline"
    )
    first_name: str | None = Field(default=None, validation_alias="users_first_name")
    gradebooktype: str | None = Field(
        default=None, validation_alias="users_gradebooktype"
    )
    group: str | None = Field(default=None, validation_alias="users_group")
    home_phone: str | None = Field(default=None, validation_alias="users_home_phone")
    homepage: str | None = Field(default=None, validation_alias="users_homepage")
    homeroom: str | None = Field(default=None, validation_alias="users_homeroom")
    homeschoolid: str | None = Field(
        default=None, validation_alias="users_homeschoolid"
    )
    ip_address: str | None = Field(default=None, validation_alias="users_ip_address")
    ipaddrrestrict: str | None = Field(
        default=None, validation_alias="users_ipaddrrestrict"
    )
    last_name: str | None = Field(default=None, validation_alias="users_last_name")
    lastfirst: str | None = Field(default=None, validation_alias="users_lastfirst")
    lastmeal: str | None = Field(default=None, validation_alias="users_lastmeal")
    loginid: str | None = Field(default=None, validation_alias="users_loginid")
    lunch_id: str | None = Field(default=None, validation_alias="users_lunch_id")
    maximum_load: str | None = Field(
        default=None, validation_alias="users_maximum_load"
    )
    middle_name: str | None = Field(default=None, validation_alias="users_middle_name")
    nameasimported: str | None = Field(
        default=None, validation_alias="users_nameasimported"
    )
    numlogins: str | None = Field(default=None, validation_alias="users_numlogins")
    password: str | None = Field(default=None, validation_alias="users_password")
    periodsavail: str | None = Field(
        default=None, validation_alias="users_periodsavail"
    )
    photo: str | None = Field(default=None, validation_alias="users_photo")
    powergradepw: str | None = Field(
        default=None, validation_alias="users_powergradepw"
    )
    preferredname: str | None = Field(
        default=None, validation_alias="users_preferredname"
    )
    prefixcodesetid: str | None = Field(
        default=None, validation_alias="users_prefixcodesetid"
    )
    psaccess: str | None = Field(default=None, validation_alias="users_psaccess")
    psguid: str | None = Field(default=None, validation_alias="users_psguid")
    ptaccess: str | None = Field(default=None, validation_alias="users_ptaccess")
    school_phone: str | None = Field(
        default=None, validation_alias="users_school_phone"
    )
    sif_stateprid: str | None = Field(
        default=None, validation_alias="users_sif_stateprid"
    )
    ssn: str | None = Field(default=None, validation_alias="users_ssn")
    staffpers_guid: str | None = Field(
        default=None, validation_alias="users_staffpers_guid"
    )
    state: str | None = Field(default=None, validation_alias="users_state")
    street: str | None = Field(default=None, validation_alias="users_street")
    supportcontact: str | None = Field(
        default=None, validation_alias="users_supportcontact"
    )
    teacherldapenabled: str | None = Field(
        default=None, validation_alias="users_teacherldapenabled"
    )
    teacherloginid: str | None = Field(
        default=None, validation_alias="users_teacherloginid"
    )
    teacherloginip: str | None = Field(
        default=None, validation_alias="users_teacherloginip"
    )
    teacherloginpw: str | None = Field(
        default=None, validation_alias="users_teacherloginpw"
    )
    teachernumber: str | None = Field(
        default=None, validation_alias="users_teachernumber"
    )
    title: str | None = Field(default=None, validation_alias="users_title")
    transaction_date: str | None = Field(
        default=None, validation_alias="users_transaction_date"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="users_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="users_whomodifiedtype"
    )
    wm_address: str | None = Field(default=None, validation_alias="users_wm_address")
    wm_validation_alias: str | None = Field(
        default=None, validation_alias="users_wm_validation_alias"
    )
    wm_createdate: str | None = Field(
        default=None, validation_alias="users_wm_createdate"
    )
    wm_createtime: str | None = Field(
        default=None, validation_alias="users_wm_createtime"
    )
    wm_exclude: str | None = Field(default=None, validation_alias="users_wm_exclude")
    wm_password: str | None = Field(default=None, validation_alias="users_wm_password")
    wm_status: str | None = Field(default=None, validation_alias="users_wm_status")
    wm_statusdate: str | None = Field(
        default=None, validation_alias="users_wm_statusdate"
    )
    wm_ta_date: str | None = Field(default=None, validation_alias="users_wm_ta_date")
    wm_ta_flag: str | None = Field(default=None, validation_alias="users_wm_ta_flag")
    wm_tier: str | None = Field(default=None, validation_alias="users_wm_tier")
    zip: str | None = Field(default=None, validation_alias="users_zip")


class Attendance(BaseModel):
    id: str | None = Field(default=None, validation_alias="attendance_id")
    dcid: str | None = Field(default=None, validation_alias="attendance_dcid")
    ada_value_code: str | None = Field(
        default=None, validation_alias="attendance_ada_value_code"
    )
    ada_value_time: str | None = Field(
        default=None, validation_alias="attendance_ada_value_time"
    )
    adm_value: str | None = Field(default=None, validation_alias="attendance_adm_value")
    att_comment: str | None = Field(
        default=None, validation_alias="attendance_att_comment"
    )
    att_date: str | None = Field(default=None, validation_alias="attendance_att_date")
    att_flags: str | None = Field(default=None, validation_alias="attendance_att_flags")
    att_interval: str | None = Field(
        default=None, validation_alias="attendance_att_interval"
    )
    att_mode_code: str | None = Field(
        default=None, validation_alias="attendance_att_mode_code"
    )
    attendance_codeid: str | None = Field(
        default=None, validation_alias="attendance_attendance_codeid"
    )
    calendar_dayid: str | None = Field(
        default=None, validation_alias="attendance_calendar_dayid"
    )
    ccid: str | None = Field(default=None, validation_alias="attendance_ccid")
    ip_address: str | None = Field(
        default=None, validation_alias="attendance_ip_address"
    )
    lock_reporting_yn: str | None = Field(
        default=None, validation_alias="attendance_lock_reporting_yn"
    )
    lock_teacher_yn: str | None = Field(
        default=None, validation_alias="attendance_lock_teacher_yn"
    )
    parent_attendanceid: str | None = Field(
        default=None, validation_alias="attendance_parent_attendanceid"
    )
    periodid: str | None = Field(default=None, validation_alias="attendance_periodid")
    prog_crse_type: str | None = Field(
        default=None, validation_alias="attendance_prog_crse_type"
    )
    programid: str | None = Field(default=None, validation_alias="attendance_programid")
    psguid: str | None = Field(default=None, validation_alias="attendance_psguid")
    schoolid: str | None = Field(default=None, validation_alias="attendance_schoolid")
    studentid: str | None = Field(default=None, validation_alias="attendance_studentid")
    total_minutes: str | None = Field(
        default=None, validation_alias="attendance_total_minutes"
    )
    transaction_date: str | None = Field(
        default=None, validation_alias="attendance_transaction_date"
    )
    transaction_type: str | None = Field(
        default=None, validation_alias="attendance_transaction_type"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="attendance_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="attendance_whomodifiedtype"
    )
    yearid: str | None = Field(default=None, validation_alias="attendance_yearid")


class AttendanceCode(BaseModel):
    id: str | None = Field(default=None, validation_alias="attendance_code_id")
    dcid: str | None = Field(default=None, validation_alias="attendance_code_dcid")
    alternate_code: str | None = Field(
        default=None, validation_alias="attendance_code_alternate_code"
    )
    assignment_filter_yn: str | None = Field(
        default=None, validation_alias="attendance_code_assignment_filter_yn"
    )
    att_code: str | None = Field(
        default=None, validation_alias="attendance_code_att_code"
    )
    attendancecodeinfo_guid: str | None = Field(
        default=None, validation_alias="attendance_code_attendancecodeinfo_guid"
    )
    calculate_ada_yn: str | None = Field(
        default=None, validation_alias="attendance_code_calculate_ada_yn"
    )
    calculate_adm_yn: str | None = Field(
        default=None, validation_alias="attendance_code_calculate_adm_yn"
    )
    course_credit_points: str | None = Field(
        default=None, validation_alias="attendance_code_course_credit_points"
    )
    description: str | None = Field(
        default=None, validation_alias="attendance_code_description"
    )
    lock_teacher_yn: str | None = Field(
        default=None, validation_alias="attendance_code_lock_teacher_yn"
    )
    presence_status_cd: str | None = Field(
        default=None, validation_alias="attendance_code_presence_status_cd"
    )
    psguid: str | None = Field(default=None, validation_alias="attendance_code_psguid")
    schoolid: str | None = Field(
        default=None, validation_alias="attendance_code_schoolid"
    )
    sortorder: str | None = Field(
        default=None, validation_alias="attendance_code_sortorder"
    )
    unused1: str | None = Field(
        default=None, validation_alias="attendance_code_unused1"
    )
    yearid: str | None = Field(default=None, validation_alias="attendance_code_yearid")


class AttendanceConversionItems(BaseModel):
    id: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_id"
    )
    dcid: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_dcid"
    )
    attendance_conversion_id: str | None = Field(
        default=None,
        validation_alias="attendance_conversion_items_attendance_conversion_id",
    )
    attendance_value: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_attendance_value"
    )
    comment: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_comment"
    )
    conversion_mode_code: str | None = Field(
        default=None,
        validation_alias="attendance_conversion_items_conversion_mode_code",
    )
    daypartid: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_daypartid"
    )
    fteid: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_fteid"
    )
    input_value: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_input_value"
    )
    unused: str | None = Field(
        default=None, validation_alias="attendance_conversion_items_unused"
    )


class BellSchedule(BaseModel):
    id: str | None = Field(default=None, validation_alias="bell_schedule_id")
    dcid: str | None = Field(default=None, validation_alias="bell_schedule_dcid")
    attendance_conversion_id: str | None = Field(
        default=None, validation_alias="bell_schedule_attendance_conversion_id"
    )
    name: str | None = Field(default=None, validation_alias="bell_schedule_name")
    psguid: str | None = Field(default=None, validation_alias="bell_schedule_psguid")
    schoolid: str | None = Field(
        default=None, validation_alias="bell_schedule_schoolid"
    )
    year_id: str | None = Field(default=None, validation_alias="bell_schedule_year_id")


class CalendarDay(BaseModel):
    id: str | None = Field(default=None, validation_alias="calendar_day_id")
    dcid: str | None = Field(default=None, validation_alias="calendar_day_dcid")
    a: str | None = Field(default=None, validation_alias="calendar_day_a")
    b: str | None = Field(default=None, validation_alias="calendar_day_b")
    bell_schedule_id: str | None = Field(
        default=None, validation_alias="calendar_day_bell_schedule_id"
    )
    c: str | None = Field(default=None, validation_alias="calendar_day_c")
    cycle_day_id: str | None = Field(
        default=None, validation_alias="calendar_day_cycle_day_id"
    )
    d: str | None = Field(default=None, validation_alias="calendar_day_d")
    date: str | None = Field(default=None, validation_alias="calendar_day_date")
    e: str | None = Field(default=None, validation_alias="calendar_day_e")
    f: str | None = Field(default=None, validation_alias="calendar_day_f")
    insession: str | None = Field(
        default=None, validation_alias="calendar_day_insession"
    )
    ip_address: str | None = Field(
        default=None, validation_alias="calendar_day_ip_address"
    )
    membershipvalue: str | None = Field(
        default=None, validation_alias="calendar_day_membershipvalue"
    )
    note: str | None = Field(default=None, validation_alias="calendar_day_note")
    psguid: str | None = Field(default=None, validation_alias="calendar_day_psguid")
    scheduleid: str | None = Field(
        default=None, validation_alias="calendar_day_scheduleid"
    )
    schoolid: str | None = Field(default=None, validation_alias="calendar_day_schoolid")
    type: str | None = Field(default=None, validation_alias="calendar_day_type")
    week_num: str | None = Field(default=None, validation_alias="calendar_day_week_num")
    whomodifiedid: str | None = Field(
        default=None, validation_alias="calendar_day_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="calendar_day_whomodifiedtype"
    )


class CC(BaseModel):
    id: str | None = Field(default=None, validation_alias="cc_id")
    dcid: str | None = Field(default=None, validation_alias="cc_dcid")
    ab_course_cmp_ext_crd: str | None = Field(
        default=None, validation_alias="cc_ab_course_cmp_ext_crd"
    )
    ab_course_cmp_fun_flg: str | None = Field(
        default=None, validation_alias="cc_ab_course_cmp_fun_flg"
    )
    ab_course_cmp_met_cd: str | None = Field(
        default=None, validation_alias="cc_ab_course_cmp_met_cd"
    )
    ab_course_cmp_sta_cd: str | None = Field(
        default=None, validation_alias="cc_ab_course_cmp_sta_cd"
    )
    ab_course_eva_pro_cd: str | None = Field(
        default=None, validation_alias="cc_ab_course_eva_pro_cd"
    )
    asmtscores: str | None = Field(default=None, validation_alias="cc_asmtscores")
    attendance: str | None = Field(default=None, validation_alias="cc_attendance")
    attendance_type_code: str | None = Field(
        default=None, validation_alias="cc_attendance_type_code"
    )
    course_number: str | None = Field(default=None, validation_alias="cc_course_number")
    currentabsences: str | None = Field(
        default=None, validation_alias="cc_currentabsences"
    )
    currenttardies: str | None = Field(
        default=None, validation_alias="cc_currenttardies"
    )
    dateenrolled: str | None = Field(default=None, validation_alias="cc_dateenrolled")
    dateleft: str | None = Field(default=None, validation_alias="cc_dateleft")
    expression: str | None = Field(default=None, validation_alias="cc_expression")
    finalgrades: str | None = Field(default=None, validation_alias="cc_finalgrades")
    firstattdate: str | None = Field(default=None, validation_alias="cc_firstattdate")
    ip_address: str | None = Field(default=None, validation_alias="cc_ip_address")
    lastattmod: str | None = Field(default=None, validation_alias="cc_lastattmod")
    lastgradeupdate: str | None = Field(
        default=None, validation_alias="cc_lastgradeupdate"
    )
    log: str | None = Field(default=None, validation_alias="cc_log")
    origsectionid: str | None = Field(default=None, validation_alias="cc_origsectionid")
    period_obsolete: str | None = Field(
        default=None, validation_alias="cc_period_obsolete"
    )
    psguid: str | None = Field(default=None, validation_alias="cc_psguid")
    schoolid: str | None = Field(default=None, validation_alias="cc_schoolid")
    section_number: str | None = Field(
        default=None, validation_alias="cc_section_number"
    )
    sectionid: str | None = Field(default=None, validation_alias="cc_sectionid")
    studentid: str | None = Field(default=None, validation_alias="cc_studentid")
    studentsectenrl_guid: str | None = Field(
        default=None, validation_alias="cc_studentsectenrl_guid"
    )
    studyear: str | None = Field(default=None, validation_alias="cc_studyear")
    teachercomment: str | None = Field(
        default=None, validation_alias="cc_teachercomment"
    )
    teacherid: str | None = Field(default=None, validation_alias="cc_teacherid")
    teacherprivatenote: str | None = Field(
        default=None, validation_alias="cc_teacherprivatenote"
    )
    termid: str | None = Field(default=None, validation_alias="cc_termid")
    transaction_date: str | None = Field(
        default=None, validation_alias="cc_transaction_date"
    )
    unused2: str | None = Field(default=None, validation_alias="cc_unused2")
    unused3: str | None = Field(default=None, validation_alias="cc_unused3")
    whomodifiedid: str | None = Field(default=None, validation_alias="cc_whomodifiedid")
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="cc_whomodifiedtype"
    )


class CodeSet(BaseModel):
    alternatecode1: str | None = Field(
        default=None, validation_alias="codeset_alternatecode1"
    )
    alternatecode2: str | None = Field(
        default=None, validation_alias="codeset_alternatecode2"
    )
    changevalidation: str | None = Field(
        default=None, validation_alias="codeset_changevalidation"
    )
    code: str | None = Field(default=None, validation_alias="codeset_code")
    codeorigin: str | None = Field(default=None, validation_alias="codeset_codeorigin")
    codesetid: str | None = Field(default=None, validation_alias="codeset_codesetid")
    codetype: str | None = Field(default=None, validation_alias="codeset_codetype")
    description: str | None = Field(
        default=None, validation_alias="codeset_description"
    )
    displayvalue: str | None = Field(
        default=None, validation_alias="codeset_displayvalue"
    )
    effectiveenddate: str | None = Field(
        default=None, validation_alias="codeset_effectiveenddate"
    )
    effectivestartdate: str | None = Field(
        default=None, validation_alias="codeset_effectivestartdate"
    )
    excludefromstatereporting: str | None = Field(
        default=None, validation_alias="codeset_excludefromstatereporting"
    )
    isdeletable: str | None = Field(
        default=None, validation_alias="codeset_isdeletable"
    )
    ismodifiable: str | None = Field(
        default=None, validation_alias="codeset_ismodifiable"
    )
    isvisible: str | None = Field(default=None, validation_alias="codeset_isvisible")
    originalcodetype: str | None = Field(
        default=None, validation_alias="codeset_originalcodetype"
    )
    parentcodesetid: str | None = Field(
        default=None, validation_alias="codeset_parentcodesetid"
    )
    reportedvalue: str | None = Field(
        default=None, validation_alias="codeset_reportedvalue"
    )
    uidisplayorder: str | None = Field(
        default=None, validation_alias="codeset_uidisplayorder"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="codeset_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="codeset_whenmodified"
    )
    whocreated: str | None = Field(default=None, validation_alias="codeset_whocreated")
    whomodified: str | None = Field(
        default=None, validation_alias="codeset_whomodified"
    )


class Courses(BaseModel):
    id: str | None = Field(default=None, validation_alias="courses_id")
    dcid: str | None = Field(default=None, validation_alias="courses_dcid")
    add_to_gpa: str | None = Field(default=None, validation_alias="courses_add_to_gpa")
    code: str | None = Field(default=None, validation_alias="courses_code")
    corequisites: str | None = Field(
        default=None, validation_alias="courses_corequisites"
    )
    course_name: str | None = Field(
        default=None, validation_alias="courses_course_name"
    )
    course_number: str | None = Field(
        default=None, validation_alias="courses_course_number"
    )
    credit_hours: str | None = Field(
        default=None, validation_alias="courses_credit_hours"
    )
    credittype: str | None = Field(default=None, validation_alias="courses_credittype")
    crhrweight: str | None = Field(default=None, validation_alias="courses_crhrweight")
    exclude_ada: str | None = Field(
        default=None, validation_alias="courses_exclude_ada"
    )
    excludefromclassrank: str | None = Field(
        default=None, validation_alias="courses_excludefromclassrank"
    )
    excludefromgpa: str | None = Field(
        default=None, validation_alias="courses_excludefromgpa"
    )
    excludefromhonorroll: str | None = Field(
        default=None, validation_alias="courses_excludefromhonorroll"
    )
    excludefromstoredgrades: str | None = Field(
        default=None, validation_alias="courses_excludefromstoredgrades"
    )
    gpa_addedvalue: str | None = Field(
        default=None, validation_alias="courses_gpa_addedvalue"
    )
    gradescaleid: str | None = Field(
        default=None, validation_alias="courses_gradescaleid"
    )
    ip_address: str | None = Field(default=None, validation_alias="courses_ip_address")
    iscareertech: str | None = Field(
        default=None, validation_alias="courses_iscareertech"
    )
    isfitnesscourse: str | None = Field(
        default=None, validation_alias="courses_isfitnesscourse"
    )
    ispewaiver: str | None = Field(default=None, validation_alias="courses_ispewaiver")
    maxclasssize: str | None = Field(
        default=None, validation_alias="courses_maxclasssize"
    )
    maxcredit: str | None = Field(default=None, validation_alias="courses_maxcredit")
    multiterm: str | None = Field(default=None, validation_alias="courses_multiterm")
    powerlink: str | None = Field(default=None, validation_alias="courses_powerlink")
    powerlinkspan: str | None = Field(
        default=None, validation_alias="courses_powerlinkspan"
    )
    prerequisites: str | None = Field(
        default=None, validation_alias="courses_prerequisites"
    )
    programid: str | None = Field(default=None, validation_alias="courses_programid")
    psguid: str | None = Field(default=None, validation_alias="courses_psguid")
    regavailable: str | None = Field(
        default=None, validation_alias="courses_regavailable"
    )
    regcoursegroup: str | None = Field(
        default=None, validation_alias="courses_regcoursegroup"
    )
    reggradelevels: str | None = Field(
        default=None, validation_alias="courses_reggradelevels"
    )
    regteachers: str | None = Field(
        default=None, validation_alias="courses_regteachers"
    )
    sched_balancepriority: str | None = Field(
        default=None, validation_alias="courses_sched_balancepriority"
    )
    sched_balanceterms: str | None = Field(
        default=None, validation_alias="courses_sched_balanceterms"
    )
    sched_blockstart: str | None = Field(
        default=None, validation_alias="courses_sched_blockstart"
    )
    sched_closesectionaftermax: str | None = Field(
        default=None, validation_alias="courses_sched_closesectionaftermax"
    )
    sched_concurrentflag: str | None = Field(
        default=None, validation_alias="courses_sched_concurrentflag"
    )
    sched_consecutiveperiods: str | None = Field(
        default=None, validation_alias="courses_sched_consecutiveperiods"
    )
    sched_consecutiveterms: str | None = Field(
        default=None, validation_alias="courses_sched_consecutiveterms"
    )
    sched_coursepackage: str | None = Field(
        default=None, validation_alias="courses_sched_coursepackage"
    )
    sched_coursepkgcontents: str | None = Field(
        default=None, validation_alias="courses_sched_coursepkgcontents"
    )
    sched_coursesubjectareacode: str | None = Field(
        default=None, validation_alias="courses_sched_coursesubjectareacode"
    )
    sched_department: str | None = Field(
        default=None, validation_alias="courses_sched_department"
    )
    sched_do_not_print: str | None = Field(
        default=None, validation_alias="courses_sched_do_not_print"
    )
    sched_extradayscheduletypecode: str | None = Field(
        default=None, validation_alias="courses_sched_extradayscheduletypecode"
    )
    sched_facilities: str | None = Field(
        default=None, validation_alias="courses_sched_facilities"
    )
    sched_frequency: str | None = Field(
        default=None, validation_alias="courses_sched_frequency"
    )
    sched_fullcatalogdescription: str | None = Field(
        default=None, validation_alias="courses_sched_fullcatalogdescription"
    )
    sched_globalsubstitution1: str | None = Field(
        default=None, validation_alias="courses_sched_globalsubstitution1"
    )
    sched_globalsubstitution2: str | None = Field(
        default=None, validation_alias="courses_sched_globalsubstitution2"
    )
    sched_globalsubstitution3: str | None = Field(
        default=None, validation_alias="courses_sched_globalsubstitution3"
    )
    sched_labflag: str | None = Field(
        default=None, validation_alias="courses_sched_labflag"
    )
    sched_labfrequency: str | None = Field(
        default=None, validation_alias="courses_sched_labfrequency"
    )
    sched_labperiodspermeeting: str | None = Field(
        default=None, validation_alias="courses_sched_labperiodspermeeting"
    )
    sched_lengthinnumberofterms: str | None = Field(
        default=None, validation_alias="courses_sched_lengthinnumberofterms"
    )
    sched_loadpriority: str | None = Field(
        default=None, validation_alias="courses_sched_loadpriority"
    )
    sched_loadtype: str | None = Field(
        default=None, validation_alias="courses_sched_loadtype"
    )
    sched_lunchcourse: str | None = Field(
        default=None, validation_alias="courses_sched_lunchcourse"
    )
    sched_maximumdayspercycle: str | None = Field(
        default=None, validation_alias="courses_sched_maximumdayspercycle"
    )
    sched_maximumenrollment: str | None = Field(
        default=None, validation_alias="courses_sched_maximumenrollment"
    )
    sched_maximumperiodsperday: str | None = Field(
        default=None, validation_alias="courses_sched_maximumperiodsperday"
    )
    sched_minimumdayspercycle: str | None = Field(
        default=None, validation_alias="courses_sched_minimumdayspercycle"
    )
    sched_minimumperiodsperday: str | None = Field(
        default=None, validation_alias="courses_sched_minimumperiodsperday"
    )
    sched_multiplerooms: str | None = Field(
        default=None, validation_alias="courses_sched_multiplerooms"
    )
    sched_periodspercycle: str | None = Field(
        default=None, validation_alias="courses_sched_periodspercycle"
    )
    sched_periodspermeeting: str | None = Field(
        default=None, validation_alias="courses_sched_periodspermeeting"
    )
    sched_repeatsallowed: str | None = Field(
        default=None, validation_alias="courses_sched_repeatsallowed"
    )
    sched_scheduled: str | None = Field(
        default=None, validation_alias="courses_sched_scheduled"
    )
    sched_scheduletypecode: str | None = Field(
        default=None, validation_alias="courses_sched_scheduletypecode"
    )
    sched_sectionsoffered: str | None = Field(
        default=None, validation_alias="courses_sched_sectionsoffered"
    )
    sched_substitutionallowed: str | None = Field(
        default=None, validation_alias="courses_sched_substitutionallowed"
    )
    sched_teachercount: str | None = Field(
        default=None, validation_alias="courses_sched_teachercount"
    )
    sched_usepreestablishedteams: str | None = Field(
        default=None, validation_alias="courses_sched_usepreestablishedteams"
    )
    sched_usesectiontypes: str | None = Field(
        default=None, validation_alias="courses_sched_usesectiontypes"
    )
    sched_validdaycombinations: str | None = Field(
        default=None, validation_alias="courses_sched_validdaycombinations"
    )
    sched_validextradaycombinations: str | None = Field(
        default=None, validation_alias="courses_sched_validextradaycombinations"
    )
    sched_validstartperiods: str | None = Field(
        default=None, validation_alias="courses_sched_validstartperiods"
    )
    sched_year: str | None = Field(default=None, validation_alias="courses_sched_year")
    schoolgroup: str | None = Field(
        default=None, validation_alias="courses_schoolgroup"
    )
    schoolid: str | None = Field(default=None, validation_alias="courses_schoolid")
    sectionstooffer: str | None = Field(
        default=None, validation_alias="courses_sectionstooffer"
    )
    status: str | None = Field(default=None, validation_alias="courses_status")
    targetclasssize: str | None = Field(
        default=None, validation_alias="courses_targetclasssize"
    )
    termsoffered: str | None = Field(
        default=None, validation_alias="courses_termsoffered"
    )
    transaction_date: str | None = Field(
        default=None, validation_alias="courses_transaction_date"
    )
    vocational: str | None = Field(default=None, validation_alias="courses_vocational")
    whomodifiedid: str | None = Field(
        default=None, validation_alias="courses_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="courses_whomodifiedtype"
    )


class CycleDay(BaseModel):
    id: str | None = Field(default=None, validation_alias="cycle_day_id")
    dcid: str | None = Field(default=None, validation_alias="cycle_day_dcid")
    abbreviation: str | None = Field(
        default=None, validation_alias="cycle_day_abbreviation"
    )
    day_name: str | None = Field(default=None, validation_alias="cycle_day_day_name")
    day_number: str | None = Field(
        default=None, validation_alias="cycle_day_day_number"
    )
    letter: str | None = Field(default=None, validation_alias="cycle_day_letter")
    psguid: str | None = Field(default=None, validation_alias="cycle_day_psguid")
    schoolid: str | None = Field(default=None, validation_alias="cycle_day_schoolid")
    sortorder: str | None = Field(default=None, validation_alias="cycle_day_sortorder")
    year_id: str | None = Field(default=None, validation_alias="cycle_day_year_id")


class EmailAddress(BaseModel):
    emailaddress: str | None = Field(
        default=None, validation_alias="emailaddress_emailaddress"
    )
    emailaddressid: str | None = Field(
        default=None, validation_alias="emailaddress_emailaddressid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="emailaddress_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="emailaddress_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="emailaddress_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="emailaddress_whomodified"
    )


class FTE(BaseModel):
    id: str | None = Field(default=None, validation_alias="fte_id")
    dcid: str | None = Field(default=None, validation_alias="fte_dcid")
    description: str | None = Field(default=None, validation_alias="fte_description")
    dflt_att_mode_code: str | None = Field(
        default=None, validation_alias="fte_dflt_att_mode_code"
    )
    dflt_conversion_mode_code: str | None = Field(
        default=None, validation_alias="fte_dflt_conversion_mode_code"
    )
    fte_value: str | None = Field(default=None, validation_alias="fte_fte_value")
    name: str | None = Field(default=None, validation_alias="fte_name")
    schoolid: str | None = Field(default=None, validation_alias="fte_schoolid")
    yearid: str | None = Field(default=None, validation_alias="fte_yearid")


class Gen(BaseModel):
    id: str | None = Field(default=None, validation_alias="gen_id")
    dcid: str | None = Field(default=None, validation_alias="gen_dcid")
    cat: str | None = Field(default=None, validation_alias="gen_cat")
    date: str | None = Field(default=None, validation_alias="gen_date")
    date2: str | None = Field(default=None, validation_alias="gen_date2")
    log: str | None = Field(default=None, validation_alias="gen_log")
    name: str | None = Field(default=None, validation_alias="gen_name")
    powerlink: str | None = Field(default=None, validation_alias="gen_powerlink")
    powerlinkspan: str | None = Field(
        default=None, validation_alias="gen_powerlinkspan"
    )
    psguid: str | None = Field(default=None, validation_alias="gen_psguid")
    schoolid: str | None = Field(default=None, validation_alias="gen_schoolid")
    sortorder: str | None = Field(default=None, validation_alias="gen_sortorder")
    spedindicator: str | None = Field(
        default=None, validation_alias="gen_spedindicator"
    )
    time1: str | None = Field(default=None, validation_alias="gen_time1")
    time2: str | None = Field(default=None, validation_alias="gen_time2")
    value: str | None = Field(default=None, validation_alias="gen_value")
    value2: str | None = Field(default=None, validation_alias="gen_value2")
    value_x: str | None = Field(default=None, validation_alias="gen_value_x")
    valueli: str | None = Field(default=None, validation_alias="gen_valueli")
    valueli2: str | None = Field(default=None, validation_alias="gen_valueli2")
    valueli3: str | None = Field(default=None, validation_alias="gen_valueli3")
    valueli4: str | None = Field(default=None, validation_alias="gen_valueli4")
    valuer: str | None = Field(default=None, validation_alias="gen_valuer")
    valuer2: str | None = Field(default=None, validation_alias="gen_valuer2")
    valuet: str | None = Field(default=None, validation_alias="gen_valuet")
    valuet2: str | None = Field(default=None, validation_alias="gen_valuet2")
    yearid: str | None = Field(default=None, validation_alias="gen_yearid")


class OriginalContactMap(BaseModel):
    originalcontactmapid: str | None = Field(
        default=None, validation_alias="originalcontactmap_originalcontactmapid"
    )
    originalcontacttype: str | None = Field(
        default=None, validation_alias="originalcontactmap_originalcontacttype"
    )
    studentcontactassocid: str | None = Field(
        default=None, validation_alias="originalcontactmap_studentcontactassocid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="originalcontactmap_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="originalcontactmap_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="originalcontactmap_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="originalcontactmap_whomodified"
    )


class Person(BaseModel):
    id: str | None = Field(default=None, validation_alias="person_id")
    dcid: str | None = Field(default=None, validation_alias="person_dcid")
    employer: str | None = Field(default=None, validation_alias="person_employer")
    excludefromstatereporting: str | None = Field(
        default=None, validation_alias="person_excludefromstatereporting"
    )
    firstname: str | None = Field(default=None, validation_alias="person_firstname")
    gendercodesetid: str | None = Field(
        default=None, validation_alias="person_gendercodesetid"
    )
    isactive: str | None = Field(default=None, validation_alias="person_isactive")
    lastname: str | None = Field(default=None, validation_alias="person_lastname")
    middlename: str | None = Field(default=None, validation_alias="person_middlename")
    prefixcodesetid: str | None = Field(
        default=None, validation_alias="person_prefixcodesetid"
    )
    statecontactid: str | None = Field(
        default=None, validation_alias="person_statecontactid"
    )
    statecontactnumber: str | None = Field(
        default=None, validation_alias="person_statecontactnumber"
    )
    suffixcodesetid: str | None = Field(
        default=None, validation_alias="person_suffixcodesetid"
    )
    whencreated: str | None = Field(default=None, validation_alias="person_whencreated")
    whenmodified: str | None = Field(
        default=None, validation_alias="person_whenmodified"
    )
    whocreated: str | None = Field(default=None, validation_alias="person_whocreated")
    whomodified: str | None = Field(default=None, validation_alias="person_whomodified")


class PersonAddress(BaseModel):
    addressline3: str | None = Field(
        default=None, validation_alias="personaddress_addressline3"
    )
    addressline4: str | None = Field(
        default=None, validation_alias="personaddress_addressline4"
    )
    addressline5: str | None = Field(
        default=None, validation_alias="personaddress_addressline5"
    )
    city: str | None = Field(default=None, validation_alias="personaddress_city")
    countrycodesetid: str | None = Field(
        default=None, validation_alias="personaddress_countrycodesetid"
    )
    countycodesetid: str | None = Field(
        default=None, validation_alias="personaddress_countycodesetid"
    )
    geocodelatitude: str | None = Field(
        default=None, validation_alias="personaddress_geocodelatitude"
    )
    geocodelongitude: str | None = Field(
        default=None, validation_alias="personaddress_geocodelongitude"
    )
    isverified: str | None = Field(
        default=None, validation_alias="personaddress_isverified"
    )
    linetwo: str | None = Field(default=None, validation_alias="personaddress_linetwo")
    personaddressid: str | None = Field(
        default=None, validation_alias="personaddress_personaddressid"
    )
    postalcode: str | None = Field(
        default=None, validation_alias="personaddress_postalcode"
    )
    statescodesetid: str | None = Field(
        default=None, validation_alias="personaddress_statescodesetid"
    )
    street: str | None = Field(default=None, validation_alias="personaddress_street")
    unit: str | None = Field(default=None, validation_alias="personaddress_unit")
    verification: str | None = Field(
        default=None, validation_alias="personaddress_verification"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="personaddress_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="personaddress_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="personaddress_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="personaddress_whomodified"
    )


class PersonAddressAssoc(BaseModel):
    addresspriorityorder: str | None = Field(
        default=None, validation_alias="personaddressassoc_addresspriorityorder"
    )
    addresstypecodesetid: str | None = Field(
        default=None, validation_alias="personaddressassoc_addresstypecodesetid"
    )
    enddate: str | None = Field(
        default=None, validation_alias="personaddressassoc_enddate"
    )
    personaddressassocid: str | None = Field(
        default=None, validation_alias="personaddressassoc_personaddressassocid"
    )
    personaddressid: str | None = Field(
        default=None, validation_alias="personaddressassoc_personaddressid"
    )
    personid: str | None = Field(
        default=None, validation_alias="personaddressassoc_personid"
    )
    startdate: str | None = Field(
        default=None, validation_alias="personaddressassoc_startdate"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="personaddressassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="personaddressassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="personaddressassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="personaddressassoc_whomodified"
    )


class PersonEmailAddressAssoc(BaseModel):
    emailaddressid: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_emailaddressid"
    )
    emailaddresspriorityorder: str | None = Field(
        default=None,
        validation_alias="personemailaddressassoc_emailaddresspriorityorder",
    )
    emailtypecodesetid: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_emailtypecodesetid"
    )
    isprimaryemailaddress: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_isprimaryemailaddress"
    )
    personemailaddressassocid: str | None = Field(
        default=None,
        validation_alias="personemailaddressassoc_personemailaddressassocid",
    )
    personid: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_personid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="personemailaddressassoc_whomodified"
    )


class PersonPhoneNumberAssoc(BaseModel):
    ispreferred: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_ispreferred"
    )
    personid: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_personid"
    )
    personphonenumberassocid: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_personphonenumberassocid"
    )
    phonenumberasentered: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_phonenumberasentered"
    )
    phonenumberid: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_phonenumberid"
    )
    phonenumberpriorityorder: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_phonenumberpriorityorder"
    )
    phonetypecodesetid: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_phonetypecodesetid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="personphonenumberassoc_whomodified"
    )


class PhoneNumber(BaseModel):
    issms: str | None = Field(default=None, validation_alias="phonenumber_issms")
    phonenumber: str | None = Field(
        default=None, validation_alias="phonenumber_phonenumber"
    )
    phonenumberext: str | None = Field(
        default=None, validation_alias="phonenumber_phonenumberext"
    )
    phonenumberid: str | None = Field(
        default=None, validation_alias="phonenumber_phonenumberid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="phonenumber_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="phonenumber_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="phonenumber_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="phonenumber_whomodified"
    )


class Reenrollments(BaseModel):
    id: str | None = Field(default=None, validation_alias="reenrollments_id")
    dcid: str | None = Field(default=None, validation_alias="reenrollments_dcid")
    districtofresidence: str | None = Field(
        default=None, validation_alias="reenrollments_districtofresidence"
    )
    enrollmentcode: str | None = Field(
        default=None, validation_alias="reenrollments_enrollmentcode"
    )
    enrollmenttype: str | None = Field(
        default=None, validation_alias="reenrollments_enrollmenttype"
    )
    entrycode: str | None = Field(
        default=None, validation_alias="reenrollments_entrycode"
    )
    entrycomment: str | None = Field(
        default=None, validation_alias="reenrollments_entrycomment"
    )
    entrydate: str | None = Field(
        default=None, validation_alias="reenrollments_entrydate"
    )
    exitcode: str | None = Field(
        default=None, validation_alias="reenrollments_exitcode"
    )
    exitcomment: str | None = Field(
        default=None, validation_alias="reenrollments_exitcomment"
    )
    exitdate: str | None = Field(
        default=None, validation_alias="reenrollments_exitdate"
    )
    fteid: str | None = Field(default=None, validation_alias="reenrollments_fteid")
    fulltimeequiv_obsolete: str | None = Field(
        default=None, validation_alias="reenrollments_fulltimeequiv_obsolete"
    )
    grade_level: str | None = Field(
        default=None, validation_alias="reenrollments_grade_level"
    )
    lunchstatus: str | None = Field(
        default=None, validation_alias="reenrollments_lunchstatus"
    )
    membershipshare: str | None = Field(
        default=None, validation_alias="reenrollments_membershipshare"
    )
    psguid: str | None = Field(default=None, validation_alias="reenrollments_psguid")
    schoolid: str | None = Field(
        default=None, validation_alias="reenrollments_schoolid"
    )
    studentid: str | None = Field(
        default=None, validation_alias="reenrollments_studentid"
    )
    studentschlenrl_guid: str | None = Field(
        default=None, validation_alias="reenrollments_studentschlenrl_guid"
    )
    track: str | None = Field(default=None, validation_alias="reenrollments_track")
    tuitionpayer: str | None = Field(
        default=None, validation_alias="reenrollments_tuitionpayer"
    )
    type: str | None = Field(default=None, validation_alias="reenrollments_type")
    withdrawal_reason_code: str | None = Field(
        default=None, validation_alias="reenrollments_withdrawal_reason_code"
    )


class SNJCrsX(BaseModel):
    coursesdcid: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_coursesdcid"
    )
    ap_course_subject: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_ap_course_subject"
    )
    block_schedule_session: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_block_schedule_session"
    )
    county_code_override: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_county_code_override"
    )
    course_level: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_course_level"
    )
    course_sequence_code: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_course_sequence_code"
    )
    course_span: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_course_span"
    )
    course_type: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_course_type"
    )
    cte_test_name_code: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_cte_test_name_code"
    )
    ctecollegecredits: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_ctecollegecredits"
    )
    ctetestdevelopercode: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_ctetestdevelopercode"
    )
    ctetestname: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_ctetestname"
    )
    district_code_override: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_district_code_override"
    )
    dual_institution: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_dual_institution"
    )
    exclude_course_submission_tf: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_exclude_course_submission_tf"
    )
    nces_course_id: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_nces_course_id"
    )
    nces_subject_area: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_nces_subject_area"
    )
    school_code_override: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_school_code_override"
    )
    sla_include_tf: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_sla_include_tf"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="s_nj_crs_x_whomodified"
    )


class SNJRenX(BaseModel):
    reenrollmentsdcid: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_reenrollmentsdcid"
    )
    alternativeeducationprogram_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_alternativeeducationprogram_yn"
    )
    city: str | None = Field(default=None, validation_alias="s_nj_ren_x_city")
    countycodeattending: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_countycodeattending"
    )
    countycodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_countycodereceiving"
    )
    countycoderesident: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_countycoderesident"
    )
    cumulativedaysabsent: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_cumulativedaysabsent"
    )
    cumulativedayspresent: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_cumulativedayspresent"
    )
    cumulativestateabs: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_cumulativestateabs"
    )
    daysopen: str | None = Field(default=None, validation_alias="s_nj_ren_x_daysopen")
    deafhardofhearing_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_deafhardofhearing_yn"
    )
    declassificationspeddate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_declassificationspeddate"
    )
    deviceowner: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_deviceowner"
    )
    devicetype: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_devicetype"
    )
    district_status_override: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_district_status_override"
    )
    districtcodeattending: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_districtcodeattending"
    )
    districtcodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_districtcodereceiving"
    )
    districtcoderesident: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_districtcoderesident"
    )
    districtentrydate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_districtentrydate"
    )
    eligible_for_liep: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_eligible_for_liep"
    )
    elp_screener_date: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_elp_screener_date"
    )
    gifted_and_talented: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_gifted_and_talented"
    )
    gradelevelcode: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_gradelevelcode"
    )
    home_language2: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language2"
    )
    home_language3: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language3"
    )
    home_language4: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language4"
    )
    home_language5: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language5"
    )
    home_language_name2: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language_name2"
    )
    home_language_name3: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language_name3"
    )
    home_language_name4: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language_name4"
    )
    home_language_name5: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_home_language_name5"
    )
    homeless_code: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_homeless_code"
    )
    homelessinstrucservice: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_homelessinstrucservice"
    )
    homelessprimarynighttimeres: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_homelessprimarynighttimeres"
    )
    homelesssupportservice: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_homelesssupportservice"
    )
    indistrictplacement: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_indistrictplacement"
    )
    internetconnectivity: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_internetconnectivity"
    )
    languageacquisition: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_languageacquisition"
    )
    learningenvironment: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_learningenvironment"
    )
    lep_completion_date_refused: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_lep_completion_date_refused"
    )
    lep_tf: str | None = Field(default=None, validation_alias="s_nj_ren_x_lep_tf")
    lepbegindate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_lepbegindate"
    )
    lepbegindate2: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_lepbegindate2"
    )
    lependdate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_lependdate"
    )
    liep_languageofinstruction: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_liep_languageofinstruction"
    )
    liep_parent_refusal_date: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_liep_parent_refusal_date"
    )
    liep_type: str | None = Field(default=None, validation_alias="s_nj_ren_x_liep_type")
    liependdate2: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_liependdate2"
    )
    mddisablingcondition1: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_mddisablingcondition1"
    )
    mddisablingcondition2: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_mddisablingcondition2"
    )
    mddisablingcondition3: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_mddisablingcondition3"
    )
    mddisablingcondition4: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_mddisablingcondition4"
    )
    mddisablingcondition5: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_mddisablingcondition5"
    )
    nonpublic: str | None = Field(default=None, validation_alias="s_nj_ren_x_nonpublic")
    pid_504_tf: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_pid_504_tf"
    )
    programtypecode: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_programtypecode"
    )
    remotedaysabsent: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_remotedaysabsent"
    )
    remotedayspresent: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_remotedayspresent"
    )
    reportedsharedvoc_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_reportedsharedvoc_yn"
    )
    residentmunicipalcode: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_residentmunicipalcode"
    )
    retained_tf: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_retained_tf"
    )
    schoolcodeattending: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_schoolcodeattending"
    )
    schoolcodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_schoolcodereceiving"
    )
    schoolcoderesident: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_schoolcoderesident"
    )
    schoolentrydate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_schoolentrydate"
    )
    shared_time_code: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_shared_time_code"
    )
    sid_entrydate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sid_entrydate"
    )
    sid_excludeenrollment: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sid_excludeenrollment"
    )
    sid_exitdate: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sid_exitdate"
    )
    sld_basic_reading_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_basic_reading_yn"
    )
    sld_listen_comp_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_listen_comp_yn"
    )
    sld_math_cal_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_math_cal_yn"
    )
    sld_math_prob_solve_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_math_prob_solve_yn"
    )
    sld_oral_expresn_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_oral_expresn_yn"
    )
    sld_read_fluency_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_read_fluency_yn"
    )
    sld_reading_comp_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_reading_comp_yn"
    )
    sld_writn_exprsn_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_sld_writn_exprsn_yn"
    )
    specialed_classification: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_specialed_classification"
    )
    studentslearningmodel: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_studentslearningmodel"
    )
    titleiindicator: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_titleiindicator"
    )
    titleilanguage_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_titleilanguage_yn"
    )
    titleimath_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_titleimath_yn"
    )
    titleiscience_yn: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_titleiscience_yn"
    )
    tuition_code: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_tuition_code"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_whomodified"
    )
    withdrawal_date: str | None = Field(
        default=None, validation_alias="s_nj_ren_x_withdrawal_date"
    )


class SNJStuX(BaseModel):
    studentsdcid: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_studentsdcid"
    )
    access_accountablecounty: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_accountablecounty"
    )
    access_accountabledistrict: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_accountabledistrict"
    )
    access_accountableschool: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_accountableschool"
    )
    access_test_format_override: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_test_format_override"
    )
    access_testingsitecounty: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_testingsitecounty"
    )
    access_testingsitedistrict: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_testingsitedistrict"
    )
    access_testingsiteschool: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_testingsiteschool"
    )
    access_tier_paper_tests: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_access_tier_paper_tests"
    )
    adulths_nb_credits: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_adulths_nb_credits"
    )
    alternate_access: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_alternate_access"
    )
    alternativeeducationprogram_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_alternativeeducationprogram_yn"
    )
    annual_iep_review_meeting_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_annual_iep_review_meeting_date"
    )
    ask_specialcodesa: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ask_specialcodesa"
    )
    ask_specialcodesb: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ask_specialcodesb"
    )
    ask_specialcodesc: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ask_specialcodesc"
    )
    ask_specialcodesd: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ask_specialcodesd"
    )
    asmt_ac: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_ac")
    asmt_alt_rep_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_alt_rep_paper"
    )
    asmt_alternate_location: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_alternate_location"
    )
    asmt_answer_masking: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_answer_masking"
    )
    asmt_answers_recorded_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_answers_recorded_paper"
    )
    asmt_asl_video: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_asl_video"
    )
    asmt_at: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_at")
    asmt_braille_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_braille_response"
    )
    asmt_braille_tactile_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_braille_tactile_paper"
    )
    asmt_bw: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_bw")
    asmt_closed_caption_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_closed_caption_ela"
    )
    asmt_color_contrast: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_color_contrast"
    )
    asmt_dictionary: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_dictionary"
    )
    asmt_directions_aloud: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_directions_aloud"
    )
    asmt_directions_clarified: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_directions_clarified"
    )
    asmt_em: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_em")
    asmt_emergency_accommodation: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_emergency_accommodation"
    )
    asmt_es: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_es")
    asmt_et: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_et")
    asmt_exclude_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_exclude_ela"
    )
    asmt_exclude_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_exclude_math"
    )
    asmt_extended_time: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_extended_time"
    )
    asmt_extended_time_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_extended_time_math"
    )
    asmt_first_enroll_in_us_school: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_first_enroll_in_us_school"
    )
    asmt_frequent_breaks: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_frequent_breaks"
    )
    asmt_human_signer: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_human_signer"
    )
    asmt_humanreader_signer: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_humanreader_signer"
    )
    asmt_ih: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_ih")
    asmt_length_in_ell: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_length_in_ell"
    )
    asmt_lh: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_lh")
    asmt_math_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_math_response"
    )
    asmt_math_response_el: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_math_response_el"
    )
    asmt_mc: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_mc")
    asmt_monitor_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_monitor_response"
    )
    asmt_non_screen_reader: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_non_screen_reader"
    )
    asmt_ns: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_ns")
    asmt_ra: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_ra")
    asmt_rd: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_rd")
    asmt_read_aloud: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_read_aloud"
    )
    asmt_refresh_braille_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_refresh_braille_ela"
    )
    asmt_ri: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_ri")
    asmt_rl: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_rl")
    asmt_screen_reader: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_screen_reader"
    )
    asmt_sd: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_sd")
    asmt_selected_response_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_selected_response_ela"
    )
    asmt_small_group: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_small_group"
    )
    asmt_special_equip: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_special_equip"
    )
    asmt_specified_area: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_specified_area"
    )
    asmt_text_to_speech: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_text_to_speech"
    )
    asmt_time_of_day: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_time_of_day"
    )
    asmt_unique_accommodation: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_unique_accommodation"
    )
    asmt_wd: str | None = Field(default=None, validation_alias="s_nj_stu_x_asmt_wd")
    asmt_word_prediction: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_asmt_word_prediction"
    )
    assessmt_ms_accomm_resp: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_assessmt_ms_accomm_resp"
    )
    biliterate_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_biliterate_yn"
    )
    birthplace_refusal: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_birthplace_refusal"
    )
    block_schedule_session_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_block_schedule_session_ela"
    )
    block_schedule_session_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_block_schedule_session_math"
    )
    bridge_year: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_bridge_year"
    )
    calculation_device_math_tools: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_calculation_device_math_tools"
    )
    caresactfunds: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_caresactfunds"
    )
    charter_assigned_school: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_charter_assigned_school"
    )
    charter_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_charter_date"
    )
    charter_school_loc: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_charter_school_loc"
    )
    charter_school_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_charter_school_name"
    )
    cityofbirth: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cityofbirth"
    )
    collegecreditsearned: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_collegecreditsearned"
    )
    counseling_services_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_counseling_services_yn"
    )
    countryofbirth: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_countryofbirth"
    )
    countycodeattending: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_countycodeattending"
    )
    countycodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_countycodereceiving"
    )
    countycoderesident: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_countycoderesident"
    )
    ctecollegecredits: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctecollegecredits"
    )
    ctepostsecondaryinstitution: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctepostsecondaryinstitution"
    )
    cteprogramofstudy_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cteprogramofstudy_yn"
    )
    cteprogramstatus: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cteprogramstatus"
    )
    ctesingleparentstatus_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctesingleparentstatus_yn"
    )
    ctetestdevelopercode: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctetestdevelopercode"
    )
    ctetestname: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctetestname"
    )
    ctetestskillassesment: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctetestskillassesment"
    )
    ctewblearning: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_ctewblearning"
    )
    cteworkbasedlearning: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cteworkbasedlearning"
    )
    cumdaysinmembershipaddto_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumdaysinmembershipaddto_tf"
    )
    cumdayspresentaddto_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumdayspresentaddto_tf"
    )
    cumdaystowardtruancyaddto_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumdaystowardtruancyaddto_tf"
    )
    cumulativedaysabsent: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumulativedaysabsent"
    )
    cumulativedaysinmembership: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumulativedaysinmembership"
    )
    cumulativedayspresent: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumulativedayspresent"
    )
    cumulativedaystowardtruancy: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumulativedaystowardtruancy"
    )
    cumulativestateabs: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_cumulativestateabs"
    )
    datelastleadtest: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_datelastleadtest"
    )
    datelastmedexam: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_datelastmedexam"
    )
    dateofpolioimmun: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_dateofpolioimmun"
    )
    daysopen: str | None = Field(default=None, validation_alias="s_nj_stu_x_daysopen")
    deafhardofhearing_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_deafhardofhearing_yn"
    )
    declassificationspeddate: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_declassificationspeddate"
    )
    determined_ineligible_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_determined_ineligible_yn"
    )
    deviceowner: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_deviceowner"
    )
    devicetype: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_devicetype"
    )
    district_status_override: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_district_status_override"
    )
    district_studentid: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_district_studentid"
    )
    districtcodeattending: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_districtcodeattending"
    )
    districtcodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_districtcodereceiving"
    )
    districtcoderesident: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_districtcoderesident"
    )
    districttimeless1year_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_districttimeless1year_yn"
    )
    early_intervention_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_early_intervention_yn"
    )
    eighthtechlit: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_eighthtechlit"
    )
    eligibility_determ_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_eligibility_determ_date"
    )
    eligible_for_liep: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_eligible_for_liep"
    )
    elp_screener_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_elp_screener_date"
    )
    eoc_title1biology_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_eoc_title1biology_tf"
    )
    examiner_smid: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examiner_smid"
    )
    examinersmid1: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examinersmid1"
    )
    examinersmid2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examinersmid2"
    )
    examinersmid3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examinersmid3"
    )
    examinersmid4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examinersmid4"
    )
    examinersmid5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_examinersmid5"
    )
    family_care_release_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_family_care_release_yn"
    )
    federalhsmathtestingreq: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_federalhsmathtestingreq"
    )
    firstentrydateintoausschool: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_firstentrydateintoausschool"
    )
    firsthsmathassessment_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_firsthsmathassessment_yn"
    )
    former_iep: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_former_iep"
    )
    generationcodesuffix: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_generationcodesuffix"
    )
    gifted_and_talented: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_gifted_and_talented"
    )
    gradelevelcode: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_gradelevelcode"
    )
    graduation_pathway_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_graduation_pathway_ela"
    )
    graduation_pathway_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_graduation_pathway_math"
    )
    healthinsprovider: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_healthinsprovider"
    )
    healthinsstatus_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_healthinsstatus_yn"
    )
    home_language: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language"
    )
    home_language2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language2"
    )
    home_language3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language3"
    )
    home_language4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language4"
    )
    home_language5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language5"
    )
    home_language_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language_name"
    )
    home_language_name2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language_name2"
    )
    home_language_name3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language_name3"
    )
    home_language_name4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language_name4"
    )
    home_language_name5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_home_language_name5"
    )
    homelessinstrucservice: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_homelessinstrucservice"
    )
    homelessprimarynighttimeres: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_homelessprimarynighttimeres"
    )
    homelesssupportservice: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_homelesssupportservice"
    )
    iep_begin_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_begin_date"
    )
    iep_end_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_end_date"
    )
    iep_exemptpassingbiology_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exemptpassingbiology_tf"
    )
    iep_exemptpassinglal_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exemptpassinglal_tf"
    )
    iep_exemptpassingmath_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exemptpassingmath_tf"
    )
    iep_exempttakingbiology_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exempttakingbiology_tf"
    )
    iep_exempttakinglal_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exempttakinglal_tf"
    )
    iep_exempttakingmath_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iep_exempttakingmath_tf"
    )
    iep_level: str | None = Field(default=None, validation_alias="s_nj_stu_x_iep_level")
    iepgradcourserequirement: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iepgradcourserequirement"
    )
    iepgraduationattendance: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_iepgraduationattendance"
    )
    immigrantstatus_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_immigrantstatus_yn"
    )
    includeinassareport_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_includeinassareport_tf"
    )
    includeinctereport_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_includeinctereport_tf"
    )
    includeinnjsmart_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_includeinnjsmart_tf"
    )
    includeinstucourse_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_includeinstucourse_tf"
    )
    indistrictplacement: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_indistrictplacement"
    )
    initial_iep_meeting_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_initial_iep_meeting_date"
    )
    initial_process_delay_reason: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_initial_process_delay_reason"
    )
    internetconnectivity: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_internetconnectivity"
    )
    languageacquisition: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_languageacquisition"
    )
    leadlevel: str | None = Field(default=None, validation_alias="s_nj_stu_x_leadlevel")
    learningenvironment: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_learningenvironment"
    )
    lep_completion_date_refused: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_lep_completion_date_refused"
    )
    lep_tf: str | None = Field(default=None, validation_alias="s_nj_stu_x_lep_tf")
    lepbegindate: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_lepbegindate"
    )
    lepbegindate2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_lepbegindate2"
    )
    lependdate: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_lependdate"
    )
    liep_classification: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_liep_classification"
    )
    liep_data: str | None = Field(default=None, validation_alias="s_nj_stu_x_liep_data")
    liep_languageofinstruction: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_liep_languageofinstruction"
    )
    liep_parent_refusal_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_liep_parent_refusal_date"
    )
    liep_refusal: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_liep_refusal"
    )
    liep_type: str | None = Field(default=None, validation_alias="s_nj_stu_x_liep_type")
    liependdate2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_liependdate2"
    )
    lunchstatusoverride: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_lunchstatusoverride"
    )
    math_state_assessment_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_math_state_assessment_name"
    )
    mddisablingcondition1: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_mddisablingcondition1"
    )
    mddisablingcondition2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_mddisablingcondition2"
    )
    mddisablingcondition3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_mddisablingcondition3"
    )
    mddisablingcondition4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_mddisablingcondition4"
    )
    mddisablingcondition5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_mddisablingcondition5"
    )
    migrant_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_migrant_tf"
    )
    military_connected_indicator: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_military_connected_indicator"
    )
    native_language: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_native_language"
    )
    nces_course_id: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_nces_course_id"
    )
    nces_subject_area: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_nces_subject_area"
    )
    nonpublic: str | None = Field(default=None, validation_alias="s_nj_stu_x_nonpublic")
    occupational_therapy_serv_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_occupational_therapy_serv_yn"
    )
    other_related_services_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_other_related_services_yn"
    )
    parcc_braille_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_braille_paper"
    )
    parcc_class_name_override_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_class_name_override_ela"
    )
    parcc_class_name_override_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_class_name_override_math"
    )
    parcc_constructed_response_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_constructed_response_ela"
    )
    parcc_ela_test_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_ela_test_code"
    )
    parcc_ell_paper_accom: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_ell_paper_accom"
    )
    parcc_examiner_smid_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_examiner_smid_ela"
    )
    parcc_examiner_smid_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_examiner_smid_math"
    )
    parcc_exempt_from_passing: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_exempt_from_passing"
    )
    parcc_iep_paper_accom: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_iep_paper_accom"
    )
    parcc_large_print_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_large_print_paper"
    )
    parcc_math_test_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_math_test_code"
    )
    parcc_math_tools: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_math_tools"
    )
    parcc_reader_signer_for_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_reader_signer_for_paper"
    )
    parcc_retest: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_retest"
    )
    parcc_sec504_paper_accom: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_sec504_paper_accom"
    )
    parcc_session_location_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_session_location_ela"
    )
    parcc_session_location_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_session_location_math"
    )
    parcc_staff_smid_override_ela: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_staff_smid_override_ela"
    )
    parcc_staff_smid_override_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_staff_smid_override_math"
    )
    parcc_student_identifier: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_student_identifier"
    )
    parcc_test_format: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_test_format"
    )
    parcc_testing_site_county: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_testing_site_county"
    )
    parcc_testing_site_district: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_testing_site_district"
    )
    parcc_testing_site_school: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_testing_site_school"
    )
    parcc_text_to_speech: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_text_to_speech"
    )
    parcc_text_to_speech_math: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_text_to_speech_math"
    )
    parcc_translation_math_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parcc_translation_math_paper"
    )
    parent_consent_intial_iep_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parent_consent_intial_iep_date"
    )
    parent_consent_obtain_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parent_consent_obtain_code"
    )
    parental_consent_eval_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_parental_consent_eval_date"
    )
    physical_therapy_services_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_physical_therapy_services_yn"
    )
    pid_504_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_504_tf"
    )
    pid_accommodations_a_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_accommodations_a_tf"
    )
    pid_accommodations_b_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_accommodations_b_tf"
    )
    pid_accommodations_c_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_accommodations_c_tf"
    )
    pid_accommodations_d_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_accommodations_d_tf"
    )
    pid_apalangartsliteracy_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_apalangartsliteracy_tf"
    )
    pid_apamath_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_apamath_tf"
    )
    pid_apascience_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_apascience_tf"
    )
    pid_apatestingcds: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_apatestingcds"
    )
    pid_audioamplification: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_audioamplification"
    )
    pid_brailletest_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_brailletest_yn"
    )
    pid_classroom: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_classroom"
    )
    pid_computerassisted: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_computerassisted"
    )
    pid_contentareatutoring_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_contentareatutoring_yn"
    )
    pid_contentbasedesl_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_contentbasedesl_yn"
    )
    pid_developbilingual_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_developbilingual_yn"
    )
    pid_heritagelanguage_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_heritagelanguage_yn"
    )
    pid_inclusionarysupport_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_inclusionarysupport_yn"
    )
    pid_largeprint_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_largeprint_yn"
    )
    pid_lepexemptlal_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_lepexemptlal_tf"
    )
    pid_lowvisionaids: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_lowvisionaids"
    )
    pid_madetape_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_madetape_tf"
    )
    pid_modifiedtestdirections: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_modifiedtestdirections"
    )
    pid_nativelang: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_nativelang"
    )
    pid_noadditionalservices_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_noadditionalservices_yn"
    )
    pid_notapplicable_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_notapplicable_yn"
    )
    pid_otherapproved: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_otherapproved"
    )
    pid_outofdistplacement_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_outofdistplacement_tf"
    )
    pid_outresidenceplacement_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_outresidenceplacement_tf"
    )
    pid_parentalrefusal_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_parentalrefusal_yn"
    )
    pid_presentationformat: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_presentationformat"
    )
    pid_pullout_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_pullout_yn"
    )
    pid_pulloutesl_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_pulloutesl_yn"
    )
    pid_scribedresponse_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_scribedresponse_yn"
    )
    pid_selfcontained_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_selfcontained_yn"
    )
    pid_sendingcds: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_sendingcds"
    )
    pid_settingformat: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_settingformat"
    )
    pid_shelteredenginstruct_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_shelteredenginstruct_yn"
    )
    pid_shortsegmenttestadmin_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_shortsegmenttestadmin_tf"
    )
    pid_structengimmersion_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_structengimmersion_yn"
    )
    pid_supplementaleduserv: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_supplementaleduserv"
    )
    pid_testformat: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_testformat"
    )
    pid_timeinlep2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_timeinlep2"
    )
    pid_timingscheduling: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_timingscheduling"
    )
    pid_title1langartslit_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_title1langartslit_tf"
    )
    pid_title1math_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_title1math_tf"
    )
    pid_title1science_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_title1science_tf"
    )
    pid_title3status: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_title3status"
    )
    pid_transbilingual_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_transbilingual_yn"
    )
    pid_twowayimmersion_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_pid_twowayimmersion_yn"
    )
    primarycipcode: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_primarycipcode"
    )
    programtypecode: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_programtypecode"
    )
    proofofage: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_proofofage"
    )
    reevaluation_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_reevaluation_date"
    )
    referral_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_referral_date"
    )
    remotedaysabsent: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_remotedaysabsent"
    )
    remotedaysmembership: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_remotedaysmembership"
    )
    remotedayspresent: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_remotedayspresent"
    )
    remotelearninghelpline_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_remotelearninghelpline_yn"
    )
    remotepercentageofday: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_remotepercentageofday"
    )
    reportedsharedvoc_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_reportedsharedvoc_yn"
    )
    residentmunicipalcode: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_residentmunicipalcode"
    )
    retained_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_retained_tf"
    )
    school_disabled: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_school_disabled"
    )
    schoolcodeattending: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_schoolcodeattending"
    )
    schoolcodereceiving: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_schoolcodereceiving"
    )
    schoolcoderesident: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_schoolcoderesident"
    )
    schooltimeless1year_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_schooltimeless1year_yn"
    )
    science_test_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_science_test_name"
    )
    secondary_disability: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_secondary_disability"
    )
    shared_time_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_shared_time_code"
    )
    sid_entrydate: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sid_entrydate"
    )
    sid_excludeenrollment: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sid_excludeenrollment"
    )
    sid_exitdate: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sid_exitdate"
    )
    sla_accountable_site_county: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_accountable_site_county"
    )
    sla_accountable_site_district: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_accountable_site_district"
    )
    sla_accountable_site_school: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_accountable_site_school"
    )
    sla_alt_rep_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_alt_rep_paper"
    )
    sla_alternate_location: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_alternate_location"
    )
    sla_answer_masking: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_answer_masking"
    )
    sla_answers_recorded_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_answers_recorded_paper"
    )
    sla_asl_video: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_asl_video"
    )
    sla_braille_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_braille_response"
    )
    sla_braille_tactile_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_braille_tactile_paper"
    )
    sla_class_name_override: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_class_name_override"
    )
    sla_closed_caption: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_closed_caption"
    )
    sla_color_contrast: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_color_contrast"
    )
    sla_constructed_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_constructed_response"
    )
    sla_dictionary: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_dictionary"
    )
    sla_directions_aloud: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_directions_aloud"
    )
    sla_directions_clarified: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_directions_clarified"
    )
    sla_emergency_accommodation: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_emergency_accommodation"
    )
    sla_examiner_smid: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_examiner_smid"
    )
    sla_exclude_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_exclude_tf"
    )
    sla_extended_time: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_extended_time"
    )
    sla_frequent_breaks: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_frequent_breaks"
    )
    sla_human_signer: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_human_signer"
    )
    sla_humanreader_signer: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_humanreader_signer"
    )
    sla_large_print_paper: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_large_print_paper"
    )
    sla_monitor_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_monitor_response"
    )
    sla_non_screen_reader: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_non_screen_reader"
    )
    sla_read_aloud: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_read_aloud"
    )
    sla_refresh_braille: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_refresh_braille"
    )
    sla_retest: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_retest"
    )
    sla_science_response_el: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_science_response_el"
    )
    sla_screen_reader: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_screen_reader"
    )
    sla_selected_response: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_selected_response"
    )
    sla_session_loc_override: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_session_loc_override"
    )
    sla_small_group: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_small_group"
    )
    sla_spanish_trans: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_spanish_trans"
    )
    sla_special_equip: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_special_equip"
    )
    sla_specified_area: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_specified_area"
    )
    sla_staffoverride_smid: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_staffoverride_smid"
    )
    sla_test_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_test_code"
    )
    sla_test_format: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_test_format"
    )
    sla_testing_site_county: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_testing_site_county"
    )
    sla_testing_site_district: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_testing_site_district"
    )
    sla_testing_site_school: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_testing_site_school"
    )
    sla_text_to_speech: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_text_to_speech"
    )
    sla_time_of_day: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_time_of_day"
    )
    sla_unique_accommodation: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_unique_accommodation"
    )
    sla_word_prediction: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sla_word_prediction"
    )
    sld_basic_reading_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_basic_reading_yn"
    )
    sld_listen_comp_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_listen_comp_yn"
    )
    sld_math_cal_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_math_cal_yn"
    )
    sld_math_prob_solve_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_math_prob_solve_yn"
    )
    sld_oral_expresn_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_oral_expresn_yn"
    )
    sld_read_fluency_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_read_fluency_yn"
    )
    sld_reading_comp_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_reading_comp_yn"
    )
    sld_writn_exprsn_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_sld_writn_exprsn_yn"
    )
    speassessmentparticipant_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speassessmentparticipant_yn"
    )
    speassignmentsubmissions_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speassignmentsubmissions_yn"
    )
    special_education_placement: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_special_education_placement"
    )
    special_status: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_special_status"
    )
    specialed_classification: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_specialed_classification"
    )
    specoachingorcheckin_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_specoachingorcheckin_yn"
    )
    spedtier: str | None = Field(default=None, validation_alias="s_nj_stu_x_spedtier")
    speech_lang_theapy_services_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speech_lang_theapy_services_yn"
    )
    speechtotextwordprediction: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speechtotextwordprediction"
    )
    speelectroniccomm_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speelectroniccomm_yn"
    )
    speonlinelearningplatforms: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speonlinelearningplatforms"
    )
    speother_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_speother_yn"
    )
    spesynchonlineclass_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_spesynchonlineclass_yn"
    )
    state_assessment_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_state_assessment_name"
    )
    state_ell_status: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_state_ell_status"
    )
    state_lep_status: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_state_lep_status"
    )
    stateofbirth: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_stateofbirth"
    )
    student_type: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_student_type"
    )
    studentslearningmodel: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_studentslearningmodel"
    )
    stureporting_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_stureporting_name"
    )
    supplementaleduserv: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_supplementaleduserv"
    )
    time_in_regular_program: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_time_in_regular_program"
    )
    title1_status_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_title1_status_tf"
    )
    titleiindicator: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_titleiindicator"
    )
    titleilanguage_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_titleilanguage_yn"
    )
    titleimath_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_titleimath_yn"
    )
    titleiscience_yn: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_titleiscience_yn"
    )
    tiv_serv_aide_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_aide_tf"
    )
    tiv_serv_assist_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_assist_tf"
    )
    tiv_serv_extyear_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_extyear_tf"
    )
    tiv_serv_ind_instr_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_ind_instr_tf"
    )
    tiv_serv_indnursing_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_indnursing_tf"
    )
    tiv_serv_intensive_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_intensive_tf"
    )
    tiv_serv_interpreter_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_interpreter_tf"
    )
    tiv_serv_pupil_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_pupil_tf"
    )
    tiv_serv_resplacement_tf: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tiv_serv_resplacement_tf"
    )
    tuition_code: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_tuition_code"
    )
    typeofearnedcollegecredits: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_typeofearnedcollegecredits"
    )
    typeofworkbasedlearning: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_typeofworkbasedlearning"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_whomodified"
    )
    withdrawal_date: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_withdrawal_date"
    )
    worldlang_assessed1: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed1"
    )
    worldlang_assessed1_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed1_name"
    )
    worldlang_assessed2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed2"
    )
    worldlang_assessed2_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed2_name"
    )
    worldlang_assessed3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed3"
    )
    worldlang_assessed3_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed3_name"
    )
    worldlang_assessed4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed4"
    )
    worldlang_assessed4_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed4_name"
    )
    worldlang_assessed5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed5"
    )
    worldlang_assessed5_name: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessed5_name"
    )
    worldlang_assessment1: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessment1"
    )
    worldlang_assessment2: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessment2"
    )
    worldlang_assessment3: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessment3"
    )
    worldlang_assessment4: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessment4"
    )
    worldlang_assessment5: str | None = Field(
        default=None, validation_alias="s_nj_stu_x_worldlang_assessment5"
    )


class Schools(BaseModel):
    id: str | None = Field(default=None, validation_alias="schools_id")
    dcid: str | None = Field(default=None, validation_alias="schools_dcid")
    abbreviation: str | None = Field(
        default=None, validation_alias="schools_abbreviation"
    )
    activecrslist: str | None = Field(
        default=None, validation_alias="schools_activecrslist"
    )
    address: str | None = Field(default=None, validation_alias="schools_address")
    alternate_school_number: str | None = Field(
        default=None, validation_alias="schools_alternate_school_number"
    )
    asstprincipal: str | None = Field(
        default=None, validation_alias="schools_asstprincipal"
    )
    asstprincipalemail: str | None = Field(
        default=None, validation_alias="schools_asstprincipalemail"
    )
    asstprincipalphone: str | None = Field(
        default=None, validation_alias="schools_asstprincipalphone"
    )
    bulletinemail: str | None = Field(
        default=None, validation_alias="schools_bulletinemail"
    )
    countyname: str | None = Field(default=None, validation_alias="schools_countyname")
    countynbr: str | None = Field(default=None, validation_alias="schools_countynbr")
    dfltnextschool: str | None = Field(
        default=None, validation_alias="schools_dfltnextschool"
    )
    district_number: str | None = Field(
        default=None, validation_alias="schools_district_number"
    )
    fee_exemption_status: str | None = Field(
        default=None, validation_alias="schools_fee_exemption_status"
    )
    high_grade: str | None = Field(default=None, validation_alias="schools_high_grade")
    hist_high_grade: str | None = Field(
        default=None, validation_alias="schools_hist_high_grade"
    )
    hist_low_grade: str | None = Field(
        default=None, validation_alias="schools_hist_low_grade"
    )
    ip_address: str | None = Field(default=None, validation_alias="schools_ip_address")
    issummerschool: str | None = Field(
        default=None, validation_alias="schools_issummerschool"
    )
    low_grade: str | None = Field(default=None, validation_alias="schools_low_grade")
    name: str | None = Field(default=None, validation_alias="schools_name")
    portalid: str | None = Field(default=None, validation_alias="schools_portalid")
    principal: str | None = Field(default=None, validation_alias="schools_principal")
    principalemail: str | None = Field(
        default=None, validation_alias="schools_principalemail"
    )
    principalphone: str | None = Field(
        default=None, validation_alias="schools_principalphone"
    )
    pscomm_path: str | None = Field(
        default=None, validation_alias="schools_pscomm_path"
    )
    psguid: str | None = Field(default=None, validation_alias="schools_psguid")
    schedulewhichschool: str | None = Field(
        default=None, validation_alias="schools_schedulewhichschool"
    )
    school_number: str | None = Field(
        default=None, validation_alias="schools_school_number"
    )
    schooladdress: str | None = Field(
        default=None, validation_alias="schools_schooladdress"
    )
    schoolcategorycodesetid: str | None = Field(
        default=None, validation_alias="schools_schoolcategorycodesetid"
    )
    schoolcity: str | None = Field(default=None, validation_alias="schools_schoolcity")
    schoolcountry: str | None = Field(
        default=None, validation_alias="schools_schoolcountry"
    )
    schoolfax: str | None = Field(default=None, validation_alias="schools_schoolfax")
    schoolgroup: str | None = Field(
        default=None, validation_alias="schools_schoolgroup"
    )
    schoolinfo_guid: str | None = Field(
        default=None, validation_alias="schools_schoolinfo_guid"
    )
    schoolphone: str | None = Field(
        default=None, validation_alias="schools_schoolphone"
    )
    schoolstate: str | None = Field(
        default=None, validation_alias="schools_schoolstate"
    )
    schoolzip: str | None = Field(default=None, validation_alias="schools_schoolzip")
    sif_stateprid: str | None = Field(
        default=None, validation_alias="schools_sif_stateprid"
    )
    sortorder: str | None = Field(default=None, validation_alias="schools_sortorder")
    state_excludefromreporting: str | None = Field(
        default=None, validation_alias="schools_state_excludefromreporting"
    )
    sysemailfrom: str | None = Field(
        default=None, validation_alias="schools_sysemailfrom"
    )
    tchrlogentrto: str | None = Field(
        default=None, validation_alias="schools_tchrlogentrto"
    )
    transaction_date: str | None = Field(
        default=None, validation_alias="schools_transaction_date"
    )
    view_in_portal: str | None = Field(
        default=None, validation_alias="schools_view_in_portal"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="schools_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="schools_whomodifiedtype"
    )


class SchoolStaff(BaseModel):
    id: str | None = Field(default=None, validation_alias="schoolstaff_id")
    dcid: str | None = Field(default=None, validation_alias="schoolstaff_dcid")
    balance1: str | None = Field(default=None, validation_alias="schoolstaff_balance1")
    balance2: str | None = Field(default=None, validation_alias="schoolstaff_balance2")
    balance3: str | None = Field(default=None, validation_alias="schoolstaff_balance3")
    balance4: str | None = Field(default=None, validation_alias="schoolstaff_balance4")
    classpua: str | None = Field(default=None, validation_alias="schoolstaff_classpua")
    ip_address: str | None = Field(
        default=None, validation_alias="schoolstaff_ip_address"
    )
    log: str | None = Field(default=None, validation_alias="schoolstaff_log")
    noofcurclasses: str | None = Field(
        default=None, validation_alias="schoolstaff_noofcurclasses"
    )
    notes: str | None = Field(default=None, validation_alias="schoolstaff_notes")
    psguid: str | None = Field(default=None, validation_alias="schoolstaff_psguid")
    sched_activitystatuscode: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_activitystatuscode"
    )
    sched_buildingcode: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_buildingcode"
    )
    sched_classroom: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_classroom"
    )
    sched_department: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_department"
    )
    sched_gender: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_gender"
    )
    sched_homeroom: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_homeroom"
    )
    sched_housecode: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_housecode"
    )
    sched_isteacherfree: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_isteacherfree"
    )
    sched_lunch: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_lunch"
    )
    sched_maximumconsecutive: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maximumconsecutive"
    )
    sched_maximumcourses: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maximumcourses"
    )
    sched_maximumduty: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maximumduty"
    )
    sched_maximumfree: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maximumfree"
    )
    sched_maxpers: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maxpers"
    )
    sched_maxpreps: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_maxpreps"
    )
    sched_primaryschoolcode: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_primaryschoolcode"
    )
    sched_scheduled: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_scheduled"
    )
    sched_substitute: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_substitute"
    )
    sched_teachermoreoneschool: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_teachermoreoneschool"
    )
    sched_team: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_team"
    )
    sched_totalcourses: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_totalcourses"
    )
    sched_usebuilding: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_usebuilding"
    )
    sched_usehouse: str | None = Field(
        default=None, validation_alias="schoolstaff_sched_usehouse"
    )
    schoolid: str | None = Field(default=None, validation_alias="schoolstaff_schoolid")
    staffstatus: str | None = Field(
        default=None, validation_alias="schoolstaff_staffstatus"
    )
    status: str | None = Field(default=None, validation_alias="schoolstaff_status")
    transaction_date: str | None = Field(
        default=None, validation_alias="schoolstaff_transaction_date"
    )
    users_dcid: str | None = Field(
        default=None, validation_alias="schoolstaff_users_dcid"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="schoolstaff_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="schoolstaff_whomodifiedtype"
    )


class Sections(BaseModel):
    id: str | None = Field(default=None, validation_alias="sections_id")
    dcid: str | None = Field(default=None, validation_alias="sections_dcid")
    att_mode_code: str | None = Field(
        default=None, validation_alias="sections_att_mode_code"
    )
    attendance: str | None = Field(default=None, validation_alias="sections_attendance")
    attendance_type_code: str | None = Field(
        default=None, validation_alias="sections_attendance_type_code"
    )
    bitmap: str | None = Field(default=None, validation_alias="sections_bitmap")
    blockperiods_obsolete: str | None = Field(
        default=None, validation_alias="sections_blockperiods_obsolete"
    )
    buildid: str | None = Field(default=None, validation_alias="sections_buildid")
    campusid: str | None = Field(default=None, validation_alias="sections_campusid")
    ccrnarray: str | None = Field(default=None, validation_alias="sections_ccrnarray")
    comment: str | None = Field(default=None, validation_alias="sections_comment")
    course_number: str | None = Field(
        default=None, validation_alias="sections_course_number"
    )
    days_obsolete: str | None = Field(
        default=None, validation_alias="sections_days_obsolete"
    )
    dependent_secs: str | None = Field(
        default=None, validation_alias="sections_dependent_secs"
    )
    distuniqueid: str | None = Field(
        default=None, validation_alias="sections_distuniqueid"
    )
    exclude_ada: str | None = Field(
        default=None, validation_alias="sections_exclude_ada"
    )
    exclude_state_rpt_yn: str | None = Field(
        default=None, validation_alias="sections_exclude_state_rpt_yn"
    )
    excludefromclassrank: str | None = Field(
        default=None, validation_alias="sections_excludefromclassrank"
    )
    excludefromgpa: str | None = Field(
        default=None, validation_alias="sections_excludefromgpa"
    )
    excludefromhonorroll: str | None = Field(
        default=None, validation_alias="sections_excludefromhonorroll"
    )
    excludefromstoredgrades: str | None = Field(
        default=None, validation_alias="sections_excludefromstoredgrades"
    )
    expression: str | None = Field(default=None, validation_alias="sections_expression")
    external_expression: str | None = Field(
        default=None, validation_alias="sections_external_expression"
    )
    fastperlist: str | None = Field(
        default=None, validation_alias="sections_fastperlist"
    )
    grade_level: str | None = Field(
        default=None, validation_alias="sections_grade_level"
    )
    gradebooktype: str | None = Field(
        default=None, validation_alias="sections_gradebooktype"
    )
    gradeprofile: str | None = Field(
        default=None, validation_alias="sections_gradeprofile"
    )
    gradescaleid: str | None = Field(
        default=None, validation_alias="sections_gradescaleid"
    )
    house: str | None = Field(default=None, validation_alias="sections_house")
    instruction_lang: str | None = Field(
        default=None, validation_alias="sections_instruction_lang"
    )
    ip_address: str | None = Field(default=None, validation_alias="sections_ip_address")
    lastattupdate: str | None = Field(
        default=None, validation_alias="sections_lastattupdate"
    )
    log: str | None = Field(default=None, validation_alias="sections_log")
    max_load_status: str | None = Field(
        default=None, validation_alias="sections_max_load_status"
    )
    maxcut: str | None = Field(default=None, validation_alias="sections_maxcut")
    maxenrollment: str | None = Field(
        default=None, validation_alias="sections_maxenrollment"
    )
    no_of_students: str | None = Field(
        default=None, validation_alias="sections_no_of_students"
    )
    noofterms: str | None = Field(default=None, validation_alias="sections_noofterms")
    original_expression: str | None = Field(
        default=None, validation_alias="sections_original_expression"
    )
    parent_section_id: str | None = Field(
        default=None, validation_alias="sections_parent_section_id"
    )
    period_obsolete: str | None = Field(
        default=None, validation_alias="sections_period_obsolete"
    )
    pgflags: str | None = Field(default=None, validation_alias="sections_pgflags")
    pgversion: str | None = Field(default=None, validation_alias="sections_pgversion")
    programid: str | None = Field(default=None, validation_alias="sections_programid")
    psguid: str | None = Field(default=None, validation_alias="sections_psguid")
    room: str | None = Field(default=None, validation_alias="sections_room")
    rostermodser: str | None = Field(
        default=None, validation_alias="sections_rostermodser"
    )
    schedulesectionid: str | None = Field(
        default=None, validation_alias="sections_schedulesectionid"
    )
    schoolid: str | None = Field(default=None, validation_alias="sections_schoolid")
    section_number: str | None = Field(
        default=None, validation_alias="sections_section_number"
    )
    section_type: str | None = Field(
        default=None, validation_alias="sections_section_type"
    )
    sectioninfo_guid: str | None = Field(
        default=None, validation_alias="sections_sectioninfo_guid"
    )
    sortorder: str | None = Field(default=None, validation_alias="sections_sortorder")
    teacher: str | None = Field(default=None, validation_alias="sections_teacher")
    teacherdescr: str | None = Field(
        default=None, validation_alias="sections_teacherdescr"
    )
    team: str | None = Field(default=None, validation_alias="sections_team")
    termid: str | None = Field(default=None, validation_alias="sections_termid")
    trackteacheratt: str | None = Field(
        default=None, validation_alias="sections_trackteacheratt"
    )
    transaction_date: str | None = Field(
        default=None, validation_alias="sections_transaction_date"
    )
    wheretaught: str | None = Field(
        default=None, validation_alias="sections_wheretaught"
    )
    wheretaughtdistrict: str | None = Field(
        default=None, validation_alias="sections_wheretaughtdistrict"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="sections_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="sections_whomodifiedtype"
    )


class StudentContactAssoc(BaseModel):
    contactpriorityorder: str | None = Field(
        default=None, validation_alias="studentcontactassoc_contactpriorityorder"
    )
    currreltypecodesetid: str | None = Field(
        default=None, validation_alias="studentcontactassoc_currreltypecodesetid"
    )
    personid: str | None = Field(
        default=None, validation_alias="studentcontactassoc_personid"
    )
    studentcontactassocid: str | None = Field(
        default=None, validation_alias="studentcontactassoc_studentcontactassocid"
    )
    studentdcid: str | None = Field(
        default=None, validation_alias="studentcontactassoc_studentdcid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="studentcontactassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="studentcontactassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="studentcontactassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="studentcontactassoc_whomodified"
    )


class StudentContactDetail(BaseModel):
    confidentialcommflag: str | None = Field(
        default=None, validation_alias="studentcontactdetail_confidentialcommflag"
    )
    enddate: str | None = Field(
        default=None, validation_alias="studentcontactdetail_enddate"
    )
    excludefromstatereportingflg: str | None = Field(
        default=None,
        validation_alias="studentcontactdetail_excludefromstatereportingflg",
    )
    generalcommflag: str | None = Field(
        default=None, validation_alias="studentcontactdetail_generalcommflag"
    )
    isactive: str | None = Field(
        default=None, validation_alias="studentcontactdetail_isactive"
    )
    iscustodial: str | None = Field(
        default=None, validation_alias="studentcontactdetail_iscustodial"
    )
    isemergency: str | None = Field(
        default=None, validation_alias="studentcontactdetail_isemergency"
    )
    liveswithflg: str | None = Field(
        default=None, validation_alias="studentcontactdetail_liveswithflg"
    )
    receivesmailflg: str | None = Field(
        default=None, validation_alias="studentcontactdetail_receivesmailflg"
    )
    relationshipnote: str | None = Field(
        default=None, validation_alias="studentcontactdetail_relationshipnote"
    )
    relationshiptypecodesetid: str | None = Field(
        default=None, validation_alias="studentcontactdetail_relationshiptypecodesetid"
    )
    schoolpickupflg: str | None = Field(
        default=None, validation_alias="studentcontactdetail_schoolpickupflg"
    )
    startdate: str | None = Field(
        default=None, validation_alias="studentcontactdetail_startdate"
    )
    studentcontactassocid: str | None = Field(
        default=None, validation_alias="studentcontactdetail_studentcontactassocid"
    )
    studentcontactdetailid: str | None = Field(
        default=None, validation_alias="studentcontactdetail_studentcontactdetailid"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="studentcontactdetail_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="studentcontactdetail_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="studentcontactdetail_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="studentcontactdetail_whomodified"
    )


class StudentCoreFields(BaseModel):
    studentsdcid: str | None = Field(
        default=None, validation_alias="studentcorefields_studentsdcid"
    )
    act_composite: str | None = Field(
        default=None, validation_alias="studentcorefields_act_composite"
    )
    act_date: str | None = Field(
        default=None, validation_alias="studentcorefields_act_date"
    )
    act_english: str | None = Field(
        default=None, validation_alias="studentcorefields_act_english"
    )
    act_math: str | None = Field(
        default=None, validation_alias="studentcorefields_act_math"
    )
    act_reading: str | None = Field(
        default=None, validation_alias="studentcorefields_act_reading"
    )
    act_science: str | None = Field(
        default=None, validation_alias="studentcorefields_act_science"
    )
    afdc: str | None = Field(default=None, validation_alias="studentcorefields_afdc")
    afdcappnum: str | None = Field(
        default=None, validation_alias="studentcorefields_afdcappnum"
    )
    allergies: str | None = Field(
        default=None, validation_alias="studentcorefields_allergies"
    )
    area: str | None = Field(default=None, validation_alias="studentcorefields_area")
    ate_skill_cert: str | None = Field(
        default=None, validation_alias="studentcorefields_ate_skill_cert"
    )
    autosend_attendancedetail: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_attendancedetail"
    )
    autosend_balancealert: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_balancealert"
    )
    autosend_gradedetail: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_gradedetail"
    )
    autosend_howoften: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_howoften"
    )
    autosend_schoolannouncements: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_schoolannouncements"
    )
    autosend_summary: str | None = Field(
        default=None, validation_alias="studentcorefields_autosend_summary"
    )
    awards: str | None = Field(
        default=None, validation_alias="studentcorefields_awards"
    )
    c_504_information: str | None = Field(
        default=None, validation_alias="studentcorefields_c_504_information"
    )
    career_goal: str | None = Field(
        default=None, validation_alias="studentcorefields_career_goal"
    )
    cip_code: str | None = Field(
        default=None, validation_alias="studentcorefields_cip_code"
    )
    competencies: str | None = Field(
        default=None, validation_alias="studentcorefields_competencies"
    )
    crt_7thmath: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_7thmath"
    )
    crt_7thscience: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_7thscience"
    )
    crt_8thscience: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_8thscience"
    )
    crt_applemath2: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_applemath2"
    )
    crt_applmath1: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_applmath1"
    )
    crt_biology: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_biology"
    )
    crt_chemistry: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_chemistry"
    )
    crt_earthsys: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_earthsys"
    )
    crt_elemalg: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_elemalg"
    )
    crt_elemmath: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_elemmath"
    )
    crt_elemread: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_elemread"
    )
    crt_humanbiol: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_humanbiol"
    )
    crt_interalg: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_interalg"
    )
    crt_physics: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_physics"
    )
    crt_prealg: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_prealg"
    )
    crt_secmath: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_secmath"
    )
    crt_secscience: str | None = Field(
        default=None, validation_alias="studentcorefields_crt_secscience"
    )
    dateofentryintousa: str | None = Field(
        default=None, validation_alias="studentcorefields_dateofentryintousa"
    )
    dentist_name: str | None = Field(
        default=None, validation_alias="studentcorefields_dentist_name"
    )
    dentist_phone: str | None = Field(
        default=None, validation_alias="studentcorefields_dentist_phone"
    )
    ec_athletics: str | None = Field(
        default=None, validation_alias="studentcorefields_ec_athletics"
    )
    ec_clubs: str | None = Field(
        default=None, validation_alias="studentcorefields_ec_clubs"
    )
    ec_community: str | None = Field(
        default=None, validation_alias="studentcorefields_ec_community"
    )
    ec_leadership: str | None = Field(
        default=None, validation_alias="studentcorefields_ec_leadership"
    )
    emerg_1_ptype: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_1_ptype"
    )
    emerg_1_rel: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_1_rel"
    )
    emerg_2_ptype: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_2_ptype"
    )
    emerg_2_rel: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_2_rel"
    )
    emerg_3_phone: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_3_phone"
    )
    emerg_3_ptype: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_3_ptype"
    )
    emerg_3_rel: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_3_rel"
    )
    emerg_contact_3: str | None = Field(
        default=None, validation_alias="studentcorefields_emerg_contact_3"
    )
    equipstudent: str | None = Field(
        default=None, validation_alias="studentcorefields_equipstudent"
    )
    esl_placement: str | None = Field(
        default=None, validation_alias="studentcorefields_esl_placement"
    )
    family_rep: str | None = Field(
        default=None, validation_alias="studentcorefields_family_rep"
    )
    father_employer: str | None = Field(
        default=None, validation_alias="studentcorefields_father_employer"
    )
    father_home_phone: str | None = Field(
        default=None, validation_alias="studentcorefields_father_home_phone"
    )
    fatherdayphone: str | None = Field(
        default=None, validation_alias="studentcorefields_fatherdayphone"
    )
    graduation_year: str | None = Field(
        default=None, validation_alias="studentcorefields_graduation_year"
    )
    guardian: str | None = Field(
        default=None, validation_alias="studentcorefields_guardian"
    )
    guardian_fn: str | None = Field(
        default=None, validation_alias="studentcorefields_guardian_fn"
    )
    guardian_ln: str | None = Field(
        default=None, validation_alias="studentcorefields_guardian_ln"
    )
    guardian_mn: str | None = Field(
        default=None, validation_alias="studentcorefields_guardian_mn"
    )
    guardiandayphone: str | None = Field(
        default=None, validation_alias="studentcorefields_guardiandayphone"
    )
    guardianrelcode: str | None = Field(
        default=None, validation_alias="studentcorefields_guardianrelcode"
    )
    guardianship: str | None = Field(
        default=None, validation_alias="studentcorefields_guardianship"
    )
    hln: str | None = Field(default=None, validation_alias="studentcorefields_hln")
    homeless_code: str | None = Field(
        default=None, validation_alias="studentcorefields_homeless_code"
    )
    ildp: str | None = Field(default=None, validation_alias="studentcorefields_ildp")
    immunizaton_dpt: str | None = Field(
        default=None, validation_alias="studentcorefields_immunizaton_dpt"
    )
    immunizaton_mmr: str | None = Field(
        default=None, validation_alias="studentcorefields_immunizaton_mmr"
    )
    immunizaton_polio: str | None = Field(
        default=None, validation_alias="studentcorefields_immunizaton_polio"
    )
    ipt_oral_curdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_oral_curdate"
    )
    ipt_oral_currentscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_oral_currentscore"
    )
    ipt_oral_origdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_oral_origdate"
    )
    ipt_oral_origscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_oral_origscore"
    )
    ipt_reading_curdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_reading_curdate"
    )
    ipt_reading_currentscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_reading_currentscore"
    )
    ipt_reading_origdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_reading_origdate"
    )
    ipt_reading_origscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_reading_origscore"
    )
    ipt_writing_curdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_writing_curdate"
    )
    ipt_writing_currentscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_writing_currentscore"
    )
    ipt_writing_origdate: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_writing_origdate"
    )
    ipt_writing_origscore: str | None = Field(
        default=None, validation_alias="studentcorefields_ipt_writing_origscore"
    )
    language_form: str | None = Field(
        default=None, validation_alias="studentcorefields_language_form"
    )
    lep_exit_date: str | None = Field(
        default=None, validation_alias="studentcorefields_lep_exit_date"
    )
    lep_status: str | None = Field(
        default=None, validation_alias="studentcorefields_lep_status"
    )
    lpac_date: str | None = Field(
        default=None, validation_alias="studentcorefields_lpac_date"
    )
    lunchapplicno: str | None = Field(
        default=None, validation_alias="studentcorefields_lunchapplicno"
    )
    medical_considerations: str | None = Field(
        default=None, validation_alias="studentcorefields_medical_considerations"
    )
    mesa: str | None = Field(default=None, validation_alias="studentcorefields_mesa")
    monitor_date: str | None = Field(
        default=None, validation_alias="studentcorefields_monitor_date"
    )
    mother_employer: str | None = Field(
        default=None, validation_alias="studentcorefields_mother_employer"
    )
    mother_home_phone: str | None = Field(
        default=None, validation_alias="studentcorefields_mother_home_phone"
    )
    motherdayphone: str | None = Field(
        default=None, validation_alias="studentcorefields_motherdayphone"
    )
    parttimestudent: str | None = Field(
        default=None, validation_alias="studentcorefields_parttimestudent"
    )
    phlote: str | None = Field(
        default=None, validation_alias="studentcorefields_phlote"
    )
    photolastupdated: str | None = Field(
        default=None, validation_alias="studentcorefields_photolastupdated"
    )
    post_secondary_objectives: str | None = Field(
        default=None, validation_alias="studentcorefields_post_secondary_objectives"
    )
    prevstudentid: str | None = Field(
        default=None, validation_alias="studentcorefields_prevstudentid"
    )
    primary_pathway: str | None = Field(
        default=None, validation_alias="studentcorefields_primary_pathway"
    )
    primarylanguage: str | None = Field(
        default=None, validation_alias="studentcorefields_primarylanguage"
    )
    pscore_legal_first_name: str | None = Field(
        default=None, validation_alias="studentcorefields_pscore_legal_first_name"
    )
    pscore_legal_gender: str | None = Field(
        default=None, validation_alias="studentcorefields_pscore_legal_gender"
    )
    pscore_legal_last_name: str | None = Field(
        default=None, validation_alias="studentcorefields_pscore_legal_last_name"
    )
    pscore_legal_middle_name: str | None = Field(
        default=None, validation_alias="studentcorefields_pscore_legal_middle_name"
    )
    pscore_legal_suffix: str | None = Field(
        default=None, validation_alias="studentcorefields_pscore_legal_suffix"
    )
    sat: str | None = Field(default=None, validation_alias="studentcorefields_sat")
    secondary_pathway: str | None = Field(
        default=None, validation_alias="studentcorefields_secondary_pathway"
    )
    secondarylanguage: str | None = Field(
        default=None, validation_alias="studentcorefields_secondarylanguage"
    )
    seop_notes: str | None = Field(
        default=None, validation_alias="studentcorefields_seop_notes"
    )
    singleparenthshldflag: str | None = Field(
        default=None, validation_alias="studentcorefields_singleparenthshldflag"
    )
    spedlep: str | None = Field(
        default=None, validation_alias="studentcorefields_spedlep"
    )
    test_comments: str | None = Field(
        default=None, validation_alias="studentcorefields_test_comments"
    )
    tracker: str | None = Field(
        default=None, validation_alias="studentcorefields_tracker"
    )
    whencreated: str | None = Field(
        default=None, validation_alias="studentcorefields_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, validation_alias="studentcorefields_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, validation_alias="studentcorefields_whocreated"
    )
    whomodified: str | None = Field(
        default=None, validation_alias="studentcorefields_whomodified"
    )


class Students(BaseModel):
    id: str | None = Field(default=None, validation_alias="students_id")
    dcid: str | None = Field(default=None, validation_alias="students_dcid")
    alert_discipline: str | None = Field(
        default=None, validation_alias="students_alert_discipline"
    )
    alert_disciplineexpires: str | None = Field(
        default=None, validation_alias="students_alert_disciplineexpires"
    )
    alert_guardian: str | None = Field(
        default=None, validation_alias="students_alert_guardian"
    )
    alert_guardianexpires: str | None = Field(
        default=None, validation_alias="students_alert_guardianexpires"
    )
    alert_medical: str | None = Field(
        default=None, validation_alias="students_alert_medical"
    )
    alert_medicalexpires: str | None = Field(
        default=None, validation_alias="students_alert_medicalexpires"
    )
    alert_other: str | None = Field(
        default=None, validation_alias="students_alert_other"
    )
    alert_otherexpires: str | None = Field(
        default=None, validation_alias="students_alert_otherexpires"
    )
    allowwebaccess: str | None = Field(
        default=None, validation_alias="students_allowwebaccess"
    )
    applic_response_recvd_date: str | None = Field(
        default=None, validation_alias="students_applic_response_recvd_date"
    )
    applic_submitted_date: str | None = Field(
        default=None, validation_alias="students_applic_submitted_date"
    )
    balance1: str | None = Field(default=None, validation_alias="students_balance1")
    balance2: str | None = Field(default=None, validation_alias="students_balance2")
    balance3: str | None = Field(default=None, validation_alias="students_balance3")
    balance4: str | None = Field(default=None, validation_alias="students_balance4")
    building: str | None = Field(default=None, validation_alias="students_building")
    bus_route: str | None = Field(default=None, validation_alias="students_bus_route")
    bus_stop: str | None = Field(default=None, validation_alias="students_bus_stop")
    campusid: str | None = Field(default=None, validation_alias="students_campusid")
    city: str | None = Field(default=None, validation_alias="students_city")
    classof: str | None = Field(default=None, validation_alias="students_classof")
    cumulative_gpa: str | None = Field(
        default=None, validation_alias="students_cumulative_gpa"
    )
    cumulative_pct: str | None = Field(
        default=None, validation_alias="students_cumulative_pct"
    )
    customrank_gpa: str | None = Field(
        default=None, validation_alias="students_customrank_gpa"
    )
    districtentrydate: str | None = Field(
        default=None, validation_alias="students_districtentrydate"
    )
    districtentrygradelevel: str | None = Field(
        default=None, validation_alias="students_districtentrygradelevel"
    )
    districtofresidence: str | None = Field(
        default=None, validation_alias="students_districtofresidence"
    )
    dob: str | None = Field(default=None, validation_alias="students_dob")
    doctor_name: str | None = Field(
        default=None, validation_alias="students_doctor_name"
    )
    doctor_phone: str | None = Field(
        default=None, validation_alias="students_doctor_phone"
    )
    emerg_contact_1: str | None = Field(
        default=None, validation_alias="students_emerg_contact_1"
    )
    emerg_contact_2: str | None = Field(
        default=None, validation_alias="students_emerg_contact_2"
    )
    emerg_phone_1: str | None = Field(
        default=None, validation_alias="students_emerg_phone_1"
    )
    emerg_phone_2: str | None = Field(
        default=None, validation_alias="students_emerg_phone_2"
    )
    enroll_status: str | None = Field(
        default=None, validation_alias="students_enroll_status"
    )
    enrollment_schoolid: str | None = Field(
        default=None, validation_alias="students_enrollment_schoolid"
    )
    enrollment_transfer_date_pend: str | None = Field(
        default=None, validation_alias="students_enrollment_transfer_date_pend"
    )
    enrollment_transfer_info: str | None = Field(
        default=None, validation_alias="students_enrollment_transfer_info"
    )
    enrollmentcode: str | None = Field(
        default=None, validation_alias="students_enrollmentcode"
    )
    enrollmentid: str | None = Field(
        default=None, validation_alias="students_enrollmentid"
    )
    enrollmenttype: str | None = Field(
        default=None, validation_alias="students_enrollmenttype"
    )
    entrycode: str | None = Field(default=None, validation_alias="students_entrycode")
    entrydate: str | None = Field(default=None, validation_alias="students_entrydate")
    ethnicity: str | None = Field(default=None, validation_alias="students_ethnicity")
    exclude_fr_rank: str | None = Field(
        default=None, validation_alias="students_exclude_fr_rank"
    )
    exitcode: str | None = Field(default=None, validation_alias="students_exitcode")
    exitcomment: str | None = Field(
        default=None, validation_alias="students_exitcomment"
    )
    exitdate: str | None = Field(default=None, validation_alias="students_exitdate")
    family_ident: str | None = Field(
        default=None, validation_alias="students_family_ident"
    )
    father: str | None = Field(default=None, validation_alias="students_father")
    father_studentcont_guid: str | None = Field(
        default=None, validation_alias="students_father_studentcont_guid"
    )
    fedethnicity: str | None = Field(
        default=None, validation_alias="students_fedethnicity"
    )
    fedracedecline: str | None = Field(
        default=None, validation_alias="students_fedracedecline"
    )
    fee_exemption_status: str | None = Field(
        default=None, validation_alias="students_fee_exemption_status"
    )
    first_name: str | None = Field(default=None, validation_alias="students_first_name")
    fteid: str | None = Field(default=None, validation_alias="students_fteid")
    fulltimeequiv_obsolete: str | None = Field(
        default=None, validation_alias="students_fulltimeequiv_obsolete"
    )
    gender: str | None = Field(default=None, validation_alias="students_gender")
    geocode: str | None = Field(default=None, validation_alias="students_geocode")
    gpentryyear: str | None = Field(
        default=None, validation_alias="students_gpentryyear"
    )
    grade_level: str | None = Field(
        default=None, validation_alias="students_grade_level"
    )
    gradreqset: str | None = Field(default=None, validation_alias="students_gradreqset")
    gradreqsetid: str | None = Field(
        default=None, validation_alias="students_gradreqsetid"
    )
    graduated_rank: str | None = Field(
        default=None, validation_alias="students_graduated_rank"
    )
    graduated_schoolid: str | None = Field(
        default=None, validation_alias="students_graduated_schoolid"
    )
    graduated_schoolname: str | None = Field(
        default=None, validation_alias="students_graduated_schoolname"
    )
    guardian_studentcont_guid: str | None = Field(
        default=None, validation_alias="students_guardian_studentcont_guid"
    )
    guardianemail: str | None = Field(
        default=None, validation_alias="students_guardianemail"
    )
    guardianfax: str | None = Field(
        default=None, validation_alias="students_guardianfax"
    )
    home_phone: str | None = Field(default=None, validation_alias="students_home_phone")
    home_room: str | None = Field(default=None, validation_alias="students_home_room")
    house: str | None = Field(default=None, validation_alias="students_house")
    ip_address: str | None = Field(default=None, validation_alias="students_ip_address")
    last_name: str | None = Field(default=None, validation_alias="students_last_name")
    lastfirst: str | None = Field(default=None, validation_alias="students_lastfirst")
    lastmeal: str | None = Field(default=None, validation_alias="students_lastmeal")
    ldapenabled: str | None = Field(
        default=None, validation_alias="students_ldapenabled"
    )
    locker_combination: str | None = Field(
        default=None, validation_alias="students_locker_combination"
    )
    locker_number: str | None = Field(
        default=None, validation_alias="students_locker_number"
    )
    log: str | None = Field(default=None, validation_alias="students_log")
    lunch_id: str | None = Field(default=None, validation_alias="students_lunch_id")
    lunchstatus: str | None = Field(
        default=None, validation_alias="students_lunchstatus"
    )
    mailing_city: str | None = Field(
        default=None, validation_alias="students_mailing_city"
    )
    mailing_geocode: str | None = Field(
        default=None, validation_alias="students_mailing_geocode"
    )
    mailing_state: str | None = Field(
        default=None, validation_alias="students_mailing_state"
    )
    mailing_street: str | None = Field(
        default=None, validation_alias="students_mailing_street"
    )
    mailing_zip: str | None = Field(
        default=None, validation_alias="students_mailing_zip"
    )
    membershipshare: str | None = Field(
        default=None, validation_alias="students_membershipshare"
    )
    middle_name: str | None = Field(
        default=None, validation_alias="students_middle_name"
    )
    mother: str | None = Field(default=None, validation_alias="students_mother")
    mother_studentcont_guid: str | None = Field(
        default=None, validation_alias="students_mother_studentcont_guid"
    )
    next_school: str | None = Field(
        default=None, validation_alias="students_next_school"
    )
    person_id: str | None = Field(default=None, validation_alias="students_person_id")
    phone_id: str | None = Field(default=None, validation_alias="students_phone_id")
    photoflag: str | None = Field(default=None, validation_alias="students_photoflag")
    pl_language: str | None = Field(
        default=None, validation_alias="students_pl_language"
    )
    psguid: str | None = Field(default=None, validation_alias="students_psguid")
    sched_loadlock: str | None = Field(
        default=None, validation_alias="students_sched_loadlock"
    )
    sched_lockstudentschedule: str | None = Field(
        default=None, validation_alias="students_sched_lockstudentschedule"
    )
    sched_nextyearbuilding: str | None = Field(
        default=None, validation_alias="students_sched_nextyearbuilding"
    )
    sched_nextyearbus: str | None = Field(
        default=None, validation_alias="students_sched_nextyearbus"
    )
    sched_nextyeargrade: str | None = Field(
        default=None, validation_alias="students_sched_nextyeargrade"
    )
    sched_nextyearhomeroom: str | None = Field(
        default=None, validation_alias="students_sched_nextyearhomeroom"
    )
    sched_nextyearhouse: str | None = Field(
        default=None, validation_alias="students_sched_nextyearhouse"
    )
    sched_nextyearteam: str | None = Field(
        default=None, validation_alias="students_sched_nextyearteam"
    )
    sched_priority: str | None = Field(
        default=None, validation_alias="students_sched_priority"
    )
    sched_scheduled: str | None = Field(
        default=None, validation_alias="students_sched_scheduled"
    )
    sched_yearofgraduation: str | None = Field(
        default=None, validation_alias="students_sched_yearofgraduation"
    )
    schoolentrydate: str | None = Field(
        default=None, validation_alias="students_schoolentrydate"
    )
    schoolentrygradelevel: str | None = Field(
        default=None, validation_alias="students_schoolentrygradelevel"
    )
    schoolid: str | None = Field(default=None, validation_alias="students_schoolid")
    sdatarn: str | None = Field(default=None, validation_alias="students_sdatarn")
    simple_gpa: str | None = Field(default=None, validation_alias="students_simple_gpa")
    simple_pct: str | None = Field(default=None, validation_alias="students_simple_pct")
    ssn: str | None = Field(default=None, validation_alias="students_ssn")
    state: str | None = Field(default=None, validation_alias="students_state")
    state_enrollflag: str | None = Field(
        default=None, validation_alias="students_state_enrollflag"
    )
    state_excludefromreporting: str | None = Field(
        default=None, validation_alias="students_state_excludefromreporting"
    )
    state_studentnumber: str | None = Field(
        default=None, validation_alias="students_state_studentnumber"
    )
    street: str | None = Field(default=None, validation_alias="students_street")
    student_allowwebaccess: str | None = Field(
        default=None, validation_alias="students_student_allowwebaccess"
    )
    student_number: str | None = Field(
        default=None, validation_alias="students_student_number"
    )
    student_web_id: str | None = Field(
        default=None, validation_alias="students_student_web_id"
    )
    student_web_password: str | None = Field(
        default=None, validation_alias="students_student_web_password"
    )
    studentpers_guid: str | None = Field(
        default=None, validation_alias="students_studentpers_guid"
    )
    studentpict_guid: str | None = Field(
        default=None, validation_alias="students_studentpict_guid"
    )
    studentschlenrl_guid: str | None = Field(
        default=None, validation_alias="students_studentschlenrl_guid"
    )
    summerschoolid: str | None = Field(
        default=None, validation_alias="students_summerschoolid"
    )
    summerschoolnote: str | None = Field(
        default=None, validation_alias="students_summerschoolnote"
    )
    teachergroupid: str | None = Field(
        default=None, validation_alias="students_teachergroupid"
    )
    team: str | None = Field(default=None, validation_alias="students_team")
    track: str | None = Field(default=None, validation_alias="students_track")
    transaction_date: str | None = Field(
        default=None, validation_alias="students_transaction_date"
    )
    transfercomment: str | None = Field(
        default=None, validation_alias="students_transfercomment"
    )
    tuitionpayer: str | None = Field(
        default=None, validation_alias="students_tuitionpayer"
    )
    web_id: str | None = Field(default=None, validation_alias="students_web_id")
    web_password: str | None = Field(
        default=None, validation_alias="students_web_password"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="students_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="students_whomodifiedtype"
    )
    withdrawal_reason_code: str | None = Field(
        default=None, validation_alias="students_withdrawal_reason_code"
    )
    wm_address: str | None = Field(default=None, validation_alias="students_wm_address")
    wm_createdate: str | None = Field(
        default=None, validation_alias="students_wm_createdate"
    )
    wm_createtime: str | None = Field(
        default=None, validation_alias="students_wm_createtime"
    )
    wm_password: str | None = Field(
        default=None, validation_alias="students_wm_password"
    )
    wm_status: str | None = Field(default=None, validation_alias="students_wm_status")
    wm_statusdate: str | None = Field(
        default=None, validation_alias="students_wm_statusdate"
    )
    wm_ta_date: str | None = Field(default=None, validation_alias="students_wm_ta_date")
    wm_ta_flag: str | None = Field(default=None, validation_alias="students_wm_ta_flag")
    wm_tier: str | None = Field(default=None, validation_alias="students_wm_tier")
    zip: str | None = Field(default=None, validation_alias="students_zip")


class TermBins(BaseModel):
    id: str | None = Field(default=None, validation_alias="termbins_id")
    dcid: str | None = Field(default=None, validation_alias="termbins_dcid")
    changegradeto: str | None = Field(
        default=None, validation_alias="termbins_changegradeto"
    )
    citasmt: str | None = Field(default=None, validation_alias="termbins_citasmt")
    collect: str | None = Field(default=None, validation_alias="termbins_collect")
    collectiondate: str | None = Field(
        default=None, validation_alias="termbins_collectiondate"
    )
    creditpct: str | None = Field(default=None, validation_alias="termbins_creditpct")
    creditstring: str | None = Field(
        default=None, validation_alias="termbins_creditstring"
    )
    currentgrade: str | None = Field(
        default=None, validation_alias="termbins_currentgrade"
    )
    date1: str | None = Field(default=None, validation_alias="termbins_date1")
    date2: str | None = Field(default=None, validation_alias="termbins_date2")
    description: str | None = Field(
        default=None, validation_alias="termbins_description"
    )
    excludedmarks: str | None = Field(
        default=None, validation_alias="termbins_excludedmarks"
    )
    gradescaleid: str | None = Field(
        default=None, validation_alias="termbins_gradescaleid"
    )
    ip_address: str | None = Field(default=None, validation_alias="termbins_ip_address")
    numattpoints: str | None = Field(
        default=None, validation_alias="termbins_numattpoints"
    )
    schoolid: str | None = Field(default=None, validation_alias="termbins_schoolid")
    showonspreadsht: str | None = Field(
        default=None, validation_alias="termbins_showonspreadsht"
    )
    storecode: str | None = Field(default=None, validation_alias="termbins_storecode")
    storegrades: str | None = Field(
        default=None, validation_alias="termbins_storegrades"
    )
    suppressltrgrd: str | None = Field(
        default=None, validation_alias="termbins_suppressltrgrd"
    )
    suppresspercentscr: str | None = Field(
        default=None, validation_alias="termbins_suppresspercentscr"
    )
    termid: str | None = Field(default=None, validation_alias="termbins_termid")
    transaction_date: str | None = Field(
        default=None, validation_alias="termbins_transaction_date"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="termbins_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="termbins_whomodifiedtype"
    )
    yearid: str | None = Field(default=None, validation_alias="termbins_yearid")


class Terms(BaseModel):
    id: str | None = Field(default=None, validation_alias="terms_id")
    dcid: str | None = Field(default=None, validation_alias="terms_dcid")
    abbreviation: str | None = Field(
        default=None, validation_alias="terms_abbreviation"
    )
    attendance_calculation_code: str | None = Field(
        default=None, validation_alias="terms_attendance_calculation_code"
    )
    autobuildbin: str | None = Field(
        default=None, validation_alias="terms_autobuildbin"
    )
    days_per_cycle: str | None = Field(
        default=None, validation_alias="terms_days_per_cycle"
    )
    firstday: str | None = Field(default=None, validation_alias="terms_firstday")
    importmap: str | None = Field(default=None, validation_alias="terms_importmap")
    ip_address: str | None = Field(default=None, validation_alias="terms_ip_address")
    isyearrec: str | None = Field(default=None, validation_alias="terms_isyearrec")
    lastday: str | None = Field(default=None, validation_alias="terms_lastday")
    name: str | None = Field(default=None, validation_alias="terms_name")
    noofdays: str | None = Field(default=None, validation_alias="terms_noofdays")
    periods_per_day: str | None = Field(
        default=None, validation_alias="terms_periods_per_day"
    )
    portion: str | None = Field(default=None, validation_alias="terms_portion")
    psguid: str | None = Field(default=None, validation_alias="terms_psguid")
    schoolid: str | None = Field(default=None, validation_alias="terms_schoolid")
    sterms: str | None = Field(default=None, validation_alias="terms_sterms")
    suppresspublicview: str | None = Field(
        default=None, validation_alias="terms_suppresspublicview"
    )
    terminfo_guid: str | None = Field(
        default=None, validation_alias="terms_terminfo_guid"
    )
    termsinyear: str | None = Field(default=None, validation_alias="terms_termsinyear")
    transaction_date: str | None = Field(
        default=None, validation_alias="terms_transaction_date"
    )
    whomodifiedid: str | None = Field(
        default=None, validation_alias="terms_whomodifiedid"
    )
    whomodifiedtype: str | None = Field(
        default=None, validation_alias="terms_whomodifiedtype"
    )
    yearid: str | None = Field(default=None, validation_alias="terms_yearid")
    yearlycredithrs: str | None = Field(
        default=None, validation_alias="terms_yearlycredithrs"
    )
