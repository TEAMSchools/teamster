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


class Attendance(BaseModel):
    id: str | None = Field(default=None, alias="attendance_id")
    dcid: str | None = Field(default=None, alias="attendance_dcid")
    ada_value_code: str | None = Field(default=None, alias="attendance_ada_value_code")
    ada_value_time: str | None = Field(default=None, alias="attendance_ada_value_time")
    adm_value: str | None = Field(default=None, alias="attendance_adm_value")
    att_date: str | None = Field(default=None, alias="attendance_att_date")
    att_flags: str | None = Field(default=None, alias="attendance_att_flags")
    att_interval: str | None = Field(default=None, alias="attendance_att_interval")
    att_mode_code: str | None = Field(default=None, alias="attendance_att_mode_code")
    attendance_codeid: str | None = Field(
        default=None, alias="attendance_attendance_codeid"
    )
    calendar_dayid: str | None = Field(default=None, alias="attendance_calendar_dayid")
    ccid: str | None = Field(default=None, alias="attendance_ccid")
    ip_address: str | None = Field(default=None, alias="attendance_ip_address")
    lock_reporting_yn: str | None = Field(
        default=None, alias="attendance_lock_reporting_yn"
    )
    lock_teacher_yn: str | None = Field(
        default=None, alias="attendance_lock_teacher_yn"
    )
    parent_attendanceid: str | None = Field(
        default=None, alias="attendance_parent_attendanceid"
    )
    periodid: str | None = Field(default=None, alias="attendance_periodid")
    programid: str | None = Field(default=None, alias="attendance_programid")
    schoolid: str | None = Field(default=None, alias="attendance_schoolid")
    studentid: str | None = Field(default=None, alias="attendance_studentid")
    total_minutes: str | None = Field(default=None, alias="attendance_total_minutes")
    transaction_date: str | None = Field(
        default=None, alias="attendance_transaction_date"
    )
    whomodifiedid: str | None = Field(default=None, alias="attendance_whomodifiedid")
    whomodifiedtype: str | None = Field(
        default=None, alias="attendance_whomodifiedtype"
    )
    yearid: str | None = Field(default=None, alias="attendance_yearid")
    att_comment: str | None = Field(default=None, alias="attendance_att_comment")


class AttendanceCode(BaseModel):
    id: str | None = Field(default=None, alias="attendance_code_id")
    dcid: str | None = Field(default=None, alias="attendance_code_dcid")
    assignment_filter_yn: str | None = Field(
        default=None, alias="attendance_code_assignment_filter_yn"
    )
    calculate_ada_yn: str | None = Field(
        default=None, alias="attendance_code_calculate_ada_yn"
    )
    calculate_adm_yn: str | None = Field(
        default=None, alias="attendance_code_calculate_adm_yn"
    )
    course_credit_points: str | None = Field(
        default=None, alias="attendance_code_course_credit_points"
    )
    description: str | None = Field(default=None, alias="attendance_code_description")
    lock_teacher_yn: str | None = Field(
        default=None, alias="attendance_code_lock_teacher_yn"
    )
    presence_status_cd: str | None = Field(
        default=None, alias="attendance_code_presence_status_cd"
    )
    schoolid: str | None = Field(default=None, alias="attendance_code_schoolid")
    sortorder: str | None = Field(default=None, alias="attendance_code_sortorder")
    yearid: str | None = Field(default=None, alias="attendance_code_yearid")
    att_code: str | None = Field(default=None, alias="attendance_code_att_code")


class Gen(BaseModel):
    id: str | None = Field(default=None, alias="gen_id")
    dcid: str | None = Field(default=None, alias="gen_dcid")
    name: str | None = Field(default=None, alias="gen_name")
    schoolid: str | None = Field(default=None, alias="gen_schoolid")
    sortorder: str | None = Field(default=None, alias="gen_sortorder")
    spedindicator: str | None = Field(default=None, alias="gen_spedindicator")
    time1: str | None = Field(default=None, alias="gen_time1")
    time2: str | None = Field(default=None, alias="gen_time2")
    valueli: str | None = Field(default=None, alias="gen_valueli")
    valueli2: str | None = Field(default=None, alias="gen_valueli2")
    valueli3: str | None = Field(default=None, alias="gen_valueli3")
    valueli4: str | None = Field(default=None, alias="gen_valueli4")
    valuer: str | None = Field(default=None, alias="gen_valuer")
    valuer2: str | None = Field(default=None, alias="gen_valuer2")
    yearid: str | None = Field(default=None, alias="gen_yearid")
    cat: str | None = Field(default=None, alias="gen_cat")
    valuet: str | None = Field(default=None, alias="gen_valuet")
    value: str | None = Field(default=None, alias="gen_value")
    value2: str | None = Field(default=None, alias="gen_value2")
    valuet2: str | None = Field(default=None, alias="gen_valuet2")
    log: str | None = Field(default=None, alias="gen_log")
    powerlink: str | None = Field(default=None, alias="gen_powerlink")
    date: str | None = Field(default=None, alias="gen_date")
    date2: str | None = Field(default=None, alias="gen_date2")
    value_x: str | None = Field(default=None, alias="gen_value_x")


class AttendanceConversionItems(BaseModel):
    id: str | None = Field(default=None, alias="attendance_conversion_items_id")
    dcid: str | None = Field(default=None, alias="attendance_conversion_items_dcid")
    attendance_conversion_id: str | None = Field(
        default=None, alias="attendance_conversion_items_attendance_conversion_id"
    )
    attendance_value: str | None = Field(
        default=None, alias="attendance_conversion_items_attendance_value"
    )
    conversion_mode_code: str | None = Field(
        default=None, alias="attendance_conversion_items_conversion_mode_code"
    )
    daypartid: str | None = Field(
        default=None, alias="attendance_conversion_items_daypartid"
    )
    fteid: str | None = Field(default=None, alias="attendance_conversion_items_fteid")
    input_value: str | None = Field(
        default=None, alias="attendance_conversion_items_input_value"
    )
    unused: str | None = Field(default=None, alias="attendance_conversion_items_unused")


class Users(BaseModel):
    dcid: str | None = Field(default=None, alias="users_dcid")
    adminldapenabled: str | None = Field(default=None, alias="users_adminldapenabled")
    allowloginend: str | None = Field(default=None, alias="users_allowloginend")
    allowloginstart: str | None = Field(default=None, alias="users_allowloginstart")
    canchangeschool: str | None = Field(default=None, alias="users_canchangeschool")
    defaultstudscrn: str | None = Field(default=None, alias="users_defaultstudscrn")
    email_addr: str | None = Field(default=None, alias="users_email_addr")
    ethnicity: str | None = Field(default=None, alias="users_ethnicity")
    fedethnicity: str | None = Field(default=None, alias="users_fedethnicity")
    fedracedecline: str | None = Field(default=None, alias="users_fedracedecline")
    first_name: str | None = Field(default=None, alias="users_first_name")
    gradebooktype: str | None = Field(default=None, alias="users_gradebooktype")
    group: str | None = Field(default=None, alias="users_group")
    homeschoolid: str | None = Field(default=None, alias="users_homeschoolid")
    ip_address: str | None = Field(default=None, alias="users_ip_address")
    last_name: str | None = Field(default=None, alias="users_last_name")
    lastfirst: str | None = Field(default=None, alias="users_lastfirst")
    loginid: str | None = Field(default=None, alias="users_loginid")
    lunch_id: str | None = Field(default=None, alias="users_lunch_id")
    maximum_load: str | None = Field(default=None, alias="users_maximum_load")
    nameasimported: str | None = Field(default=None, alias="users_nameasimported")
    numlogins: str | None = Field(default=None, alias="users_numlogins")
    password: str | None = Field(default=None, alias="users_password")
    photo: str | None = Field(default=None, alias="users_photo")
    preferredname: str | None = Field(default=None, alias="users_preferredname")
    psaccess: str | None = Field(default=None, alias="users_psaccess")
    ptaccess: str | None = Field(default=None, alias="users_ptaccess")
    staffpers_guid: str | None = Field(default=None, alias="users_staffpers_guid")
    supportcontact: str | None = Field(default=None, alias="users_supportcontact")
    teacherldapenabled: str | None = Field(
        default=None, alias="users_teacherldapenabled"
    )
    teacherloginid: str | None = Field(default=None, alias="users_teacherloginid")
    teacherloginpw: str | None = Field(default=None, alias="users_teacherloginpw")
    teachernumber: str | None = Field(default=None, alias="users_teachernumber")
    transaction_date: str | None = Field(default=None, alias="users_transaction_date")
    whomodifiedid: str | None = Field(default=None, alias="users_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="users_whomodifiedtype")
    wm_createtime: str | None = Field(default=None, alias="users_wm_createtime")
    wm_exclude: str | None = Field(default=None, alias="users_wm_exclude")
    wm_tier: str | None = Field(default=None, alias="users_wm_tier")
    home_phone: str | None = Field(default=None, alias="users_home_phone")
    title: str | None = Field(default=None, alias="users_title")
    homepage: str | None = Field(default=None, alias="users_homepage")
    street: str | None = Field(default=None, alias="users_street")
    prefixcodesetid: str | None = Field(default=None, alias="users_prefixcodesetid")


class Terms(BaseModel):
    id: str | None = Field(default=None, alias="terms_id")
    dcid: str | None = Field(default=None, alias="terms_dcid")
    abbreviation: str | None = Field(default=None, alias="terms_abbreviation")
    attendance_calculation_code: str | None = Field(
        default=None, alias="terms_attendance_calculation_code"
    )
    autobuildbin: str | None = Field(default=None, alias="terms_autobuildbin")
    days_per_cycle: str | None = Field(default=None, alias="terms_days_per_cycle")
    firstday: str | None = Field(default=None, alias="terms_firstday")
    importmap: str | None = Field(default=None, alias="terms_importmap")
    ip_address: str | None = Field(default=None, alias="terms_ip_address")
    isyearrec: str | None = Field(default=None, alias="terms_isyearrec")
    lastday: str | None = Field(default=None, alias="terms_lastday")
    name: str | None = Field(default=None, alias="terms_name")
    noofdays: str | None = Field(default=None, alias="terms_noofdays")
    periods_per_day: str | None = Field(default=None, alias="terms_periods_per_day")
    portion: str | None = Field(default=None, alias="terms_portion")
    schoolid: str | None = Field(default=None, alias="terms_schoolid")
    sterms: str | None = Field(default=None, alias="terms_sterms")
    suppresspublicview: str | None = Field(
        default=None, alias="terms_suppresspublicview"
    )
    terminfo_guid: str | None = Field(default=None, alias="terms_terminfo_guid")
    termsinyear: str | None = Field(default=None, alias="terms_termsinyear")
    transaction_date: str | None = Field(default=None, alias="terms_transaction_date")
    whomodifiedid: str | None = Field(default=None, alias="terms_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="terms_whomodifiedtype")
    yearid: str | None = Field(default=None, alias="terms_yearid")
    yearlycredithrs: str | None = Field(default=None, alias="terms_yearlycredithrs")


class TermBins(BaseModel):
    id: str | None = Field(default=None, alias="termbins_id")
    dcid: str | None = Field(default=None, alias="termbins_dcid")
    collect: str | None = Field(default=None, alias="termbins_collect")
    creditpct: str | None = Field(default=None, alias="termbins_creditpct")
    currentgrade: str | None = Field(default=None, alias="termbins_currentgrade")
    date1: str | None = Field(default=None, alias="termbins_date1")
    date2: str | None = Field(default=None, alias="termbins_date2")
    gradescaleid: str | None = Field(default=None, alias="termbins_gradescaleid")
    ip_address: str | None = Field(default=None, alias="termbins_ip_address")
    numattpoints: str | None = Field(default=None, alias="termbins_numattpoints")
    schoolid: str | None = Field(default=None, alias="termbins_schoolid")
    showonspreadsht: str | None = Field(default=None, alias="termbins_showonspreadsht")
    storecode: str | None = Field(default=None, alias="termbins_storecode")
    storegrades: str | None = Field(default=None, alias="termbins_storegrades")
    suppressltrgrd: str | None = Field(default=None, alias="termbins_suppressltrgrd")
    suppresspercentscr: str | None = Field(
        default=None, alias="termbins_suppresspercentscr"
    )
    termid: str | None = Field(default=None, alias="termbins_termid")
    transaction_date: str | None = Field(
        default=None, alias="termbins_transaction_date"
    )
    whomodifiedid: str | None = Field(default=None, alias="termbins_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="termbins_whomodifiedtype")
    yearid: str | None = Field(default=None, alias="termbins_yearid")


class Students(BaseModel):
    id: str | None = Field(default=None, alias="students_id")
    dcid: str | None = Field(default=None, alias="students_dcid")
    allowwebaccess: str | None = Field(default=None, alias="students_allowwebaccess")
    balance1: str | None = Field(default=None, alias="students_balance1")
    balance2: str | None = Field(default=None, alias="students_balance2")
    balance3: str | None = Field(default=None, alias="students_balance3")
    balance4: str | None = Field(default=None, alias="students_balance4")
    campusid: str | None = Field(default=None, alias="students_campusid")
    city: str | None = Field(default=None, alias="students_city")
    classof: str | None = Field(default=None, alias="students_classof")
    cumulative_gpa: str | None = Field(default=None, alias="students_cumulative_gpa")
    cumulative_pct: str | None = Field(default=None, alias="students_cumulative_pct")
    customrank_gpa: str | None = Field(default=None, alias="students_customrank_gpa")
    districtentrygradelevel: str | None = Field(
        default=None, alias="students_districtentrygradelevel"
    )
    dob: str | None = Field(default=None, alias="students_dob")
    enroll_status: str | None = Field(default=None, alias="students_enroll_status")
    enrollment_schoolid: str | None = Field(
        default=None, alias="students_enrollment_schoolid"
    )
    enrollmentcode: str | None = Field(default=None, alias="students_enrollmentcode")
    enrollmentid: str | None = Field(default=None, alias="students_enrollmentid")
    entrydate: str | None = Field(default=None, alias="students_entrydate")
    ethnicity: str | None = Field(default=None, alias="students_ethnicity")
    exclude_fr_rank: str | None = Field(default=None, alias="students_exclude_fr_rank")
    exitdate: str | None = Field(default=None, alias="students_exitdate")
    father_studentcont_guid: str | None = Field(
        default=None, alias="students_father_studentcont_guid"
    )
    fedethnicity: str | None = Field(default=None, alias="students_fedethnicity")
    fedracedecline: str | None = Field(default=None, alias="students_fedracedecline")
    fee_exemption_status: str | None = Field(
        default=None, alias="students_fee_exemption_status"
    )
    first_name: str | None = Field(default=None, alias="students_first_name")
    fteid: str | None = Field(default=None, alias="students_fteid")
    fulltimeequiv_obsolete: str | None = Field(
        default=None, alias="students_fulltimeequiv_obsolete"
    )
    gender: str | None = Field(default=None, alias="students_gender")
    gpentryyear: str | None = Field(default=None, alias="students_gpentryyear")
    grade_level: str | None = Field(default=None, alias="students_grade_level")
    gradreqsetid: str | None = Field(default=None, alias="students_gradreqsetid")
    graduated_rank: str | None = Field(default=None, alias="students_graduated_rank")
    graduated_schoolid: str | None = Field(
        default=None, alias="students_graduated_schoolid"
    )
    guardian_studentcont_guid: str | None = Field(
        default=None, alias="students_guardian_studentcont_guid"
    )
    home_phone: str | None = Field(default=None, alias="students_home_phone")
    ip_address: str | None = Field(default=None, alias="students_ip_address")
    last_name: str | None = Field(default=None, alias="students_last_name")
    lastfirst: str | None = Field(default=None, alias="students_lastfirst")
    ldapenabled: str | None = Field(default=None, alias="students_ldapenabled")
    log: str | None = Field(default=None, alias="students_log")
    lunch_id: str | None = Field(default=None, alias="students_lunch_id")
    lunchstatus: str | None = Field(default=None, alias="students_lunchstatus")
    mailing_city: str | None = Field(default=None, alias="students_mailing_city")
    mailing_state: str | None = Field(default=None, alias="students_mailing_state")
    mailing_street: str | None = Field(default=None, alias="students_mailing_street")
    mailing_zip: str | None = Field(default=None, alias="students_mailing_zip")
    membershipshare: str | None = Field(default=None, alias="students_membershipshare")
    mother_studentcont_guid: str | None = Field(
        default=None, alias="students_mother_studentcont_guid"
    )
    next_school: str | None = Field(default=None, alias="students_next_school")
    person_id: str | None = Field(default=None, alias="students_person_id")
    phone_id: str | None = Field(default=None, alias="students_phone_id")
    photoflag: str | None = Field(default=None, alias="students_photoflag")
    sched_loadlock: str | None = Field(default=None, alias="students_sched_loadlock")
    sched_lockstudentschedule: str | None = Field(
        default=None, alias="students_sched_lockstudentschedule"
    )
    sched_nextyeargrade: str | None = Field(
        default=None, alias="students_sched_nextyeargrade"
    )
    sched_priority: str | None = Field(default=None, alias="students_sched_priority")
    sched_scheduled: str | None = Field(default=None, alias="students_sched_scheduled")
    sched_yearofgraduation: str | None = Field(
        default=None, alias="students_sched_yearofgraduation"
    )
    schoolentrygradelevel: str | None = Field(
        default=None, alias="students_schoolentrygradelevel"
    )
    schoolid: str | None = Field(default=None, alias="students_schoolid")
    sdatarn: str | None = Field(default=None, alias="students_sdatarn")
    simple_gpa: str | None = Field(default=None, alias="students_simple_gpa")
    simple_pct: str | None = Field(default=None, alias="students_simple_pct")
    state: str | None = Field(default=None, alias="students_state")
    state_enrollflag: str | None = Field(
        default=None, alias="students_state_enrollflag"
    )
    state_excludefromreporting: str | None = Field(
        default=None, alias="students_state_excludefromreporting"
    )
    state_studentnumber: str | None = Field(
        default=None, alias="students_state_studentnumber"
    )
    street: str | None = Field(default=None, alias="students_street")
    student_allowwebaccess: str | None = Field(
        default=None, alias="students_student_allowwebaccess"
    )
    student_number: str | None = Field(default=None, alias="students_student_number")
    studentpers_guid: str | None = Field(
        default=None, alias="students_studentpers_guid"
    )
    studentpict_guid: str | None = Field(
        default=None, alias="students_studentpict_guid"
    )
    studentschlenrl_guid: str | None = Field(
        default=None, alias="students_studentschlenrl_guid"
    )
    summerschoolid: str | None = Field(default=None, alias="students_summerschoolid")
    teachergroupid: str | None = Field(default=None, alias="students_teachergroupid")
    transaction_date: str | None = Field(
        default=None, alias="students_transaction_date"
    )
    tuitionpayer: str | None = Field(default=None, alias="students_tuitionpayer")
    whomodifiedid: str | None = Field(default=None, alias="students_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="students_whomodifiedtype")
    wm_createtime: str | None = Field(default=None, alias="students_wm_createtime")
    wm_tier: str | None = Field(default=None, alias="students_wm_tier")
    zip: str | None = Field(default=None, alias="students_zip")
    districtentrydate: str | None = Field(
        default=None, alias="students_districtentrydate"
    )
    doctor_name: str | None = Field(default=None, alias="students_doctor_name")
    doctor_phone: str | None = Field(default=None, alias="students_doctor_phone")
    middle_name: str | None = Field(default=None, alias="students_middle_name")
    schoolentrydate: str | None = Field(default=None, alias="students_schoolentrydate")
    student_web_id: str | None = Field(default=None, alias="students_student_web_id")
    student_web_password: str | None = Field(
        default=None, alias="students_student_web_password"
    )
    web_id: str | None = Field(default=None, alias="students_web_id")
    web_password: str | None = Field(default=None, alias="students_web_password")
    alert_medical: str | None = Field(default=None, alias="students_alert_medical")
    entrycode: str | None = Field(default=None, alias="students_entrycode")
    exitcode: str | None = Field(default=None, alias="students_exitcode")
    home_room: str | None = Field(default=None, alias="students_home_room")
    emerg_contact_1: str | None = Field(default=None, alias="students_emerg_contact_1")
    emerg_contact_2: str | None = Field(default=None, alias="students_emerg_contact_2")
    emerg_phone_1: str | None = Field(default=None, alias="students_emerg_phone_1")
    emerg_phone_2: str | None = Field(default=None, alias="students_emerg_phone_2")
    geocode: str | None = Field(default=None, alias="students_geocode")
    mailing_geocode: str | None = Field(default=None, alias="students_mailing_geocode")
    transfercomment: str | None = Field(default=None, alias="students_transfercomment")
    exitcomment: str | None = Field(default=None, alias="students_exitcomment")
    father: str | None = Field(default=None, alias="students_father")
    mother: str | None = Field(default=None, alias="students_mother")
    districtofresidence: str | None = Field(
        default=None, alias="students_districtofresidence"
    )
    guardianemail: str | None = Field(default=None, alias="students_guardianemail")


class StudentCoreFields(BaseModel):
    studentsdcid: str | None = Field(
        default=None, alias="studentcorefields_studentsdcid"
    )
    whencreated: str | None = Field(default=None, alias="studentcorefields_whencreated")
    whenmodified: str | None = Field(
        default=None, alias="studentcorefields_whenmodified"
    )
    whomodified: str | None = Field(default=None, alias="studentcorefields_whomodified")
    allergies: str | None = Field(default=None, alias="studentcorefields_allergies")
    graduation_year: str | None = Field(
        default=None, alias="studentcorefields_graduation_year"
    )
    immunizaton_dpt: str | None = Field(
        default=None, alias="studentcorefields_immunizaton_dpt"
    )
    immunizaton_mmr: str | None = Field(
        default=None, alias="studentcorefields_immunizaton_mmr"
    )
    immunizaton_polio: str | None = Field(
        default=None, alias="studentcorefields_immunizaton_polio"
    )
    emerg_1_ptype: str | None = Field(
        default=None, alias="studentcorefields_emerg_1_ptype"
    )
    emerg_1_rel: str | None = Field(default=None, alias="studentcorefields_emerg_1_rel")
    emerg_2_ptype: str | None = Field(
        default=None, alias="studentcorefields_emerg_2_ptype"
    )
    emerg_2_rel: str | None = Field(default=None, alias="studentcorefields_emerg_2_rel")
    emerg_3_phone: str | None = Field(
        default=None, alias="studentcorefields_emerg_3_phone"
    )
    emerg_3_ptype: str | None = Field(
        default=None, alias="studentcorefields_emerg_3_ptype"
    )
    emerg_3_rel: str | None = Field(default=None, alias="studentcorefields_emerg_3_rel")
    emerg_contact_3: str | None = Field(
        default=None, alias="studentcorefields_emerg_contact_3"
    )
    photolastupdated: str | None = Field(
        default=None, alias="studentcorefields_photolastupdated"
    )
    pscore_legal_first_name: str | None = Field(
        default=None, alias="studentcorefields_pscore_legal_first_name"
    )
    pscore_legal_gender: str | None = Field(
        default=None, alias="studentcorefields_pscore_legal_gender"
    )
    pscore_legal_last_name: str | None = Field(
        default=None, alias="studentcorefields_pscore_legal_last_name"
    )
    tracker: str | None = Field(default=None, alias="studentcorefields_tracker")
    guardian_fn: str | None = Field(default=None, alias="studentcorefields_guardian_fn")
    guardian_ln: str | None = Field(default=None, alias="studentcorefields_guardian_ln")
    dentist_name: str | None = Field(
        default=None, alias="studentcorefields_dentist_name"
    )
    dentist_phone: str | None = Field(
        default=None, alias="studentcorefields_dentist_phone"
    )
    medical_considerations: str | None = Field(
        default=None, alias="studentcorefields_medical_considerations"
    )
    pscore_legal_middle_name: str | None = Field(
        default=None, alias="studentcorefields_pscore_legal_middle_name"
    )
    homeless_code: str | None = Field(
        default=None, alias="studentcorefields_homeless_code"
    )
    whocreated: str | None = Field(default=None, alias="studentcorefields_whocreated")
    fatherdayphone: str | None = Field(
        default=None, alias="studentcorefields_fatherdayphone"
    )
    mother_home_phone: str | None = Field(
        default=None, alias="studentcorefields_mother_home_phone"
    )
    motherdayphone: str | None = Field(
        default=None, alias="studentcorefields_motherdayphone"
    )
    father_employer: str | None = Field(
        default=None, alias="studentcorefields_father_employer"
    )
    father_home_phone: str | None = Field(
        default=None, alias="studentcorefields_father_home_phone"
    )
    guardian_mn: str | None = Field(default=None, alias="studentcorefields_guardian_mn")
    mother_employer: str | None = Field(
        default=None, alias="studentcorefields_mother_employer"
    )
    guardiandayphone: str | None = Field(
        default=None, alias="studentcorefields_guardiandayphone"
    )


class StudentContactDetail(BaseModel):
    confidentialcommflag: str | None = Field(
        default=None, alias="studentcontactdetail_confidentialcommflag"
    )
    excludefromstatereportingflg: str | None = Field(
        default=None, alias="studentcontactdetail_excludefromstatereportingflg"
    )
    generalcommflag: str | None = Field(
        default=None, alias="studentcontactdetail_generalcommflag"
    )
    isactive: str | None = Field(default=None, alias="studentcontactdetail_isactive")
    iscustodial: str | None = Field(
        default=None, alias="studentcontactdetail_iscustodial"
    )
    isemergency: str | None = Field(
        default=None, alias="studentcontactdetail_isemergency"
    )
    liveswithflg: str | None = Field(
        default=None, alias="studentcontactdetail_liveswithflg"
    )
    receivesmailflg: str | None = Field(
        default=None, alias="studentcontactdetail_receivesmailflg"
    )
    relationshiptypecodesetid: str | None = Field(
        default=None, alias="studentcontactdetail_relationshiptypecodesetid"
    )
    schoolpickupflg: str | None = Field(
        default=None, alias="studentcontactdetail_schoolpickupflg"
    )
    studentcontactassocid: str | None = Field(
        default=None, alias="studentcontactdetail_studentcontactassocid"
    )
    studentcontactdetailid: str | None = Field(
        default=None, alias="studentcontactdetail_studentcontactdetailid"
    )
    whencreated: str | None = Field(
        default=None, alias="studentcontactdetail_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="studentcontactdetail_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, alias="studentcontactdetail_whocreated"
    )
    whomodified: str | None = Field(
        default=None, alias="studentcontactdetail_whomodified"
    )
    relationshipnote: str | None = Field(
        default=None, alias="studentcontactdetail_relationshipnote"
    )
    enddate: str | None = Field(default=None, alias="studentcontactdetail_enddate")
    startdate: str | None = Field(default=None, alias="studentcontactdetail_startdate")


class BellSchedule(BaseModel):
    id: str | None = Field(default=None, alias="bell_schedule_id")
    dcid: str | None = Field(default=None, alias="bell_schedule_dcid")
    attendance_conversion_id: str | None = Field(
        default=None, alias="bell_schedule_attendance_conversion_id"
    )
    name: str | None = Field(default=None, alias="bell_schedule_name")
    schoolid: str | None = Field(default=None, alias="bell_schedule_schoolid")
    year_id: str | None = Field(default=None, alias="bell_schedule_year_id")


class PhoneNumber(BaseModel):
    issms: str | None = Field(default=None, alias="phonenumber_issms")
    phonenumber: str | None = Field(default=None, alias="phonenumber_phonenumber")
    phonenumberid: str | None = Field(default=None, alias="phonenumber_phonenumberid")
    whencreated: str | None = Field(default=None, alias="phonenumber_whencreated")
    whenmodified: str | None = Field(default=None, alias="phonenumber_whenmodified")
    whocreated: str | None = Field(default=None, alias="phonenumber_whocreated")
    whomodified: str | None = Field(default=None, alias="phonenumber_whomodified")
    phonenumberext: str | None = Field(default=None, alias="phonenumber_phonenumberext")


class Sections(BaseModel):
    id: str | None = Field(default=None, alias="sections_id")
    dcid: str | None = Field(default=None, alias="sections_dcid")
    att_mode_code: str | None = Field(default=None, alias="sections_att_mode_code")
    attendance_type_code: str | None = Field(
        default=None, alias="sections_attendance_type_code"
    )
    bitmap: str | None = Field(default=None, alias="sections_bitmap")
    buildid: str | None = Field(default=None, alias="sections_buildid")
    campusid: str | None = Field(default=None, alias="sections_campusid")
    course_number: str | None = Field(default=None, alias="sections_course_number")
    distuniqueid: str | None = Field(default=None, alias="sections_distuniqueid")
    exclude_ada: str | None = Field(default=None, alias="sections_exclude_ada")
    exclude_state_rpt_yn: str | None = Field(
        default=None, alias="sections_exclude_state_rpt_yn"
    )
    excludefromclassrank: str | None = Field(
        default=None, alias="sections_excludefromclassrank"
    )
    excludefromgpa: str | None = Field(default=None, alias="sections_excludefromgpa")
    excludefromhonorroll: str | None = Field(
        default=None, alias="sections_excludefromhonorroll"
    )
    excludefromstoredgrades: str | None = Field(
        default=None, alias="sections_excludefromstoredgrades"
    )
    expression: str | None = Field(default=None, alias="sections_expression")
    external_expression: str | None = Field(
        default=None, alias="sections_external_expression"
    )
    grade_level: str | None = Field(default=None, alias="sections_grade_level")
    gradebooktype: str | None = Field(default=None, alias="sections_gradebooktype")
    gradescaleid: str | None = Field(default=None, alias="sections_gradescaleid")
    ip_address: str | None = Field(default=None, alias="sections_ip_address")
    maxcut: str | None = Field(default=None, alias="sections_maxcut")
    maxenrollment: str | None = Field(default=None, alias="sections_maxenrollment")
    no_of_students: str | None = Field(default=None, alias="sections_no_of_students")
    noofterms: str | None = Field(default=None, alias="sections_noofterms")
    parent_section_id: str | None = Field(
        default=None, alias="sections_parent_section_id"
    )
    pgversion: str | None = Field(default=None, alias="sections_pgversion")
    programid: str | None = Field(default=None, alias="sections_programid")
    rostermodser: str | None = Field(default=None, alias="sections_rostermodser")
    schedulesectionid: str | None = Field(
        default=None, alias="sections_schedulesectionid"
    )
    schoolid: str | None = Field(default=None, alias="sections_schoolid")
    section_number: str | None = Field(default=None, alias="sections_section_number")
    sectioninfo_guid: str | None = Field(
        default=None, alias="sections_sectioninfo_guid"
    )
    sortorder: str | None = Field(default=None, alias="sections_sortorder")
    teacher: str | None = Field(default=None, alias="sections_teacher")
    termid: str | None = Field(default=None, alias="sections_termid")
    trackteacheratt: str | None = Field(default=None, alias="sections_trackteacheratt")
    transaction_date: str | None = Field(
        default=None, alias="sections_transaction_date"
    )
    wheretaught: str | None = Field(default=None, alias="sections_wheretaught")
    wheretaughtdistrict: str | None = Field(
        default=None, alias="sections_wheretaughtdistrict"
    )
    whomodifiedid: str | None = Field(default=None, alias="sections_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="sections_whomodifiedtype")
    dependent_secs: str | None = Field(default=None, alias="sections_dependent_secs")
    room: str | None = Field(default=None, alias="sections_room")


class CalendarDay(BaseModel):
    id: str | None = Field(default=None, alias="calendar_day_id")
    dcid: str | None = Field(default=None, alias="calendar_day_dcid")
    a: str | None = Field(default=None, alias="calendar_day_a")
    b: str | None = Field(default=None, alias="calendar_day_b")
    bell_schedule_id: str | None = Field(
        default=None, alias="calendar_day_bell_schedule_id"
    )
    c: str | None = Field(default=None, alias="calendar_day_c")
    cycle_day_id: str | None = Field(default=None, alias="calendar_day_cycle_day_id")
    d: str | None = Field(default=None, alias="calendar_day_d")
    date: str | None = Field(default=None, alias="calendar_day_date")
    e: str | None = Field(default=None, alias="calendar_day_e")
    f: str | None = Field(default=None, alias="calendar_day_f")
    insession: str | None = Field(default=None, alias="calendar_day_insession")
    membershipvalue: str | None = Field(
        default=None, alias="calendar_day_membershipvalue"
    )
    scheduleid: str | None = Field(default=None, alias="calendar_day_scheduleid")
    schoolid: str | None = Field(default=None, alias="calendar_day_schoolid")
    week_num: str | None = Field(default=None, alias="calendar_day_week_num")
    type: str | None = Field(default=None, alias="calendar_day_type")
    note: str | None = Field(default=None, alias="calendar_day_note")


class CodeSet(BaseModel):
    code: str | None = Field(default=None, alias="codeset_code")
    codeorigin: str | None = Field(default=None, alias="codeset_codeorigin")
    codesetid: str | None = Field(default=None, alias="codeset_codesetid")
    codetype: str | None = Field(default=None, alias="codeset_codetype")
    description: str | None = Field(default=None, alias="codeset_description")
    excludefromstatereporting: str | None = Field(
        default=None, alias="codeset_excludefromstatereporting"
    )
    isdeletable: str | None = Field(default=None, alias="codeset_isdeletable")
    ismodifiable: str | None = Field(default=None, alias="codeset_ismodifiable")
    isvisible: str | None = Field(default=None, alias="codeset_isvisible")
    uidisplayorder: str | None = Field(default=None, alias="codeset_uidisplayorder")
    whencreated: str | None = Field(default=None, alias="codeset_whencreated")
    whenmodified: str | None = Field(default=None, alias="codeset_whenmodified")
    whocreated: str | None = Field(default=None, alias="codeset_whocreated")
    whomodified: str | None = Field(default=None, alias="codeset_whomodified")
    changevalidation: str | None = Field(default=None, alias="codeset_changevalidation")
    displayvalue: str | None = Field(default=None, alias="codeset_displayvalue")
    parentcodesetid: str | None = Field(default=None, alias="codeset_parentcodesetid")
    alternatecode2: str | None = Field(default=None, alias="codeset_alternatecode2")
    reportedvalue: str | None = Field(default=None, alias="codeset_reportedvalue")
    alternatecode1: str | None = Field(default=None, alias="codeset_alternatecode1")


class Courses(BaseModel):
    id: str | None = Field(default=None, alias="courses_id")
    dcid: str | None = Field(default=None, alias="courses_dcid")
    add_to_gpa: str | None = Field(default=None, alias="courses_add_to_gpa")
    course_name: str | None = Field(default=None, alias="courses_course_name")
    course_number: str | None = Field(default=None, alias="courses_course_number")
    credit_hours: str | None = Field(default=None, alias="courses_credit_hours")
    credittype: str | None = Field(default=None, alias="courses_credittype")
    crhrweight: str | None = Field(default=None, alias="courses_crhrweight")
    exclude_ada: str | None = Field(default=None, alias="courses_exclude_ada")
    excludefromclassrank: str | None = Field(
        default=None, alias="courses_excludefromclassrank"
    )
    excludefromgpa: str | None = Field(default=None, alias="courses_excludefromgpa")
    excludefromhonorroll: str | None = Field(
        default=None, alias="courses_excludefromhonorroll"
    )
    excludefromstoredgrades: str | None = Field(
        default=None, alias="courses_excludefromstoredgrades"
    )
    gpa_addedvalue: str | None = Field(default=None, alias="courses_gpa_addedvalue")
    gradescaleid: str | None = Field(default=None, alias="courses_gradescaleid")
    ip_address: str | None = Field(default=None, alias="courses_ip_address")
    iscareertech: str | None = Field(default=None, alias="courses_iscareertech")
    isfitnesscourse: str | None = Field(default=None, alias="courses_isfitnesscourse")
    ispewaiver: str | None = Field(default=None, alias="courses_ispewaiver")
    maxclasssize: str | None = Field(default=None, alias="courses_maxclasssize")
    maxcredit: str | None = Field(default=None, alias="courses_maxcredit")
    programid: str | None = Field(default=None, alias="courses_programid")
    regavailable: str | None = Field(default=None, alias="courses_regavailable")
    sched_balanceterms: str | None = Field(
        default=None, alias="courses_sched_balanceterms"
    )
    sched_blockstart: str | None = Field(default=None, alias="courses_sched_blockstart")
    sched_closesectionaftermax: str | None = Field(
        default=None, alias="courses_sched_closesectionaftermax"
    )
    sched_concurrentflag: str | None = Field(
        default=None, alias="courses_sched_concurrentflag"
    )
    sched_consecutiveperiods: str | None = Field(
        default=None, alias="courses_sched_consecutiveperiods"
    )
    sched_consecutiveterms: str | None = Field(
        default=None, alias="courses_sched_consecutiveterms"
    )
    sched_coursepackage: str | None = Field(
        default=None, alias="courses_sched_coursepackage"
    )
    sched_department: str | None = Field(default=None, alias="courses_sched_department")
    sched_do_not_print: str | None = Field(
        default=None, alias="courses_sched_do_not_print"
    )
    sched_frequency: str | None = Field(default=None, alias="courses_sched_frequency")
    sched_labflag: str | None = Field(default=None, alias="courses_sched_labflag")
    sched_labfrequency: str | None = Field(
        default=None, alias="courses_sched_labfrequency"
    )
    sched_labperiodspermeeting: str | None = Field(
        default=None, alias="courses_sched_labperiodspermeeting"
    )
    sched_lengthinnumberofterms: str | None = Field(
        default=None, alias="courses_sched_lengthinnumberofterms"
    )
    sched_loadpriority: str | None = Field(
        default=None, alias="courses_sched_loadpriority"
    )
    sched_lunchcourse: str | None = Field(
        default=None, alias="courses_sched_lunchcourse"
    )
    sched_maximumdayspercycle: str | None = Field(
        default=None, alias="courses_sched_maximumdayspercycle"
    )
    sched_maximumenrollment: str | None = Field(
        default=None, alias="courses_sched_maximumenrollment"
    )
    sched_maximumperiodsperday: str | None = Field(
        default=None, alias="courses_sched_maximumperiodsperday"
    )
    sched_minimumdayspercycle: str | None = Field(
        default=None, alias="courses_sched_minimumdayspercycle"
    )
    sched_minimumperiodsperday: str | None = Field(
        default=None, alias="courses_sched_minimumperiodsperday"
    )
    sched_multiplerooms: str | None = Field(
        default=None, alias="courses_sched_multiplerooms"
    )
    sched_periodspercycle: str | None = Field(
        default=None, alias="courses_sched_periodspercycle"
    )
    sched_periodspermeeting: str | None = Field(
        default=None, alias="courses_sched_periodspermeeting"
    )
    sched_repeatsallowed: str | None = Field(
        default=None, alias="courses_sched_repeatsallowed"
    )
    sched_scheduled: str | None = Field(default=None, alias="courses_sched_scheduled")
    sched_sectionsoffered: str | None = Field(
        default=None, alias="courses_sched_sectionsoffered"
    )
    sched_substitutionallowed: str | None = Field(
        default=None, alias="courses_sched_substitutionallowed"
    )
    sched_teachercount: str | None = Field(
        default=None, alias="courses_sched_teachercount"
    )
    sched_usepreestablishedteams: str | None = Field(
        default=None, alias="courses_sched_usepreestablishedteams"
    )
    sched_usesectiontypes: str | None = Field(
        default=None, alias="courses_sched_usesectiontypes"
    )
    sched_year: str | None = Field(default=None, alias="courses_sched_year")
    schoolgroup: str | None = Field(default=None, alias="courses_schoolgroup")
    schoolid: str | None = Field(default=None, alias="courses_schoolid")
    sectionstooffer: str | None = Field(default=None, alias="courses_sectionstooffer")
    status: str | None = Field(default=None, alias="courses_status")
    targetclasssize: str | None = Field(default=None, alias="courses_targetclasssize")
    transaction_date: str | None = Field(default=None, alias="courses_transaction_date")
    vocational: str | None = Field(default=None, alias="courses_vocational")
    whomodifiedid: str | None = Field(default=None, alias="courses_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="courses_whomodifiedtype")


class CycleDay(BaseModel):
    id: str | None = Field(default=None, alias="cycle_day_id")
    dcid: str | None = Field(default=None, alias="cycle_day_dcid")
    abbreviation: str | None = Field(default=None, alias="cycle_day_abbreviation")
    day_name: str | None = Field(default=None, alias="cycle_day_day_name")
    day_number: str | None = Field(default=None, alias="cycle_day_day_number")
    letter: str | None = Field(default=None, alias="cycle_day_letter")
    schoolid: str | None = Field(default=None, alias="cycle_day_schoolid")
    sortorder: str | None = Field(default=None, alias="cycle_day_sortorder")
    year_id: str | None = Field(default=None, alias="cycle_day_year_id")


class FTE(BaseModel):
    id: str | None = Field(default=None, alias="fte_id")
    dcid: str | None = Field(default=None, alias="fte_dcid")
    dflt_att_mode_code: str | None = Field(default=None, alias="fte_dflt_att_mode_code")
    dflt_conversion_mode_code: str | None = Field(
        default=None, alias="fte_dflt_conversion_mode_code"
    )
    fte_value: str | None = Field(default=None, alias="fte_fte_value")
    name: str | None = Field(default=None, alias="fte_name")
    schoolid: str | None = Field(default=None, alias="fte_schoolid")
    yearid: str | None = Field(default=None, alias="fte_yearid")


class OriginalContactMap(BaseModel):
    originalcontactmapid: str | None = Field(
        default=None, alias="originalcontactmap_originalcontactmapid"
    )
    originalcontacttype: str | None = Field(
        default=None, alias="originalcontactmap_originalcontacttype"
    )
    studentcontactassocid: str | None = Field(
        default=None, alias="originalcontactmap_studentcontactassocid"
    )
    whencreated: str | None = Field(
        default=None, alias="originalcontactmap_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="originalcontactmap_whenmodified"
    )
    whocreated: str | None = Field(default=None, alias="originalcontactmap_whocreated")
    whomodified: str | None = Field(
        default=None, alias="originalcontactmap_whomodified"
    )


class Person(BaseModel):
    id: str | None = Field(default=None, alias="person_id")
    dcid: str | None = Field(default=None, alias="person_dcid")
    excludefromstatereporting: str | None = Field(
        default=None, alias="person_excludefromstatereporting"
    )
    firstname: str | None = Field(default=None, alias="person_firstname")
    gendercodesetid: str | None = Field(default=None, alias="person_gendercodesetid")
    isactive: str | None = Field(default=None, alias="person_isactive")
    lastname: str | None = Field(default=None, alias="person_lastname")
    whencreated: str | None = Field(default=None, alias="person_whencreated")
    whenmodified: str | None = Field(default=None, alias="person_whenmodified")
    whocreated: str | None = Field(default=None, alias="person_whocreated")
    whomodified: str | None = Field(default=None, alias="person_whomodified")
    middlename: str | None = Field(default=None, alias="person_middlename")
    prefixcodesetid: str | None = Field(default=None, alias="person_prefixcodesetid")
    employer: str | None = Field(default=None, alias="person_employer")
    suffixcodesetid: str | None = Field(default=None, alias="person_suffixcodesetid")


class PersonAddress(BaseModel):
    city: str | None = Field(default=None, alias="personaddress_city")
    countrycodesetid: str | None = Field(
        default=None, alias="personaddress_countrycodesetid"
    )
    personaddressid: str | None = Field(
        default=None, alias="personaddress_personaddressid"
    )
    postalcode: str | None = Field(default=None, alias="personaddress_postalcode")
    statescodesetid: str | None = Field(
        default=None, alias="personaddress_statescodesetid"
    )
    street: str | None = Field(default=None, alias="personaddress_street")
    whencreated: str | None = Field(default=None, alias="personaddress_whencreated")
    whenmodified: str | None = Field(default=None, alias="personaddress_whenmodified")
    whocreated: str | None = Field(default=None, alias="personaddress_whocreated")
    whomodified: str | None = Field(default=None, alias="personaddress_whomodified")
    geocodelatitude: str | None = Field(
        default=None, alias="personaddress_geocodelatitude"
    )
    geocodelongitude: str | None = Field(
        default=None, alias="personaddress_geocodelongitude"
    )
    linetwo: str | None = Field(default=None, alias="personaddress_linetwo")
    unit: str | None = Field(default=None, alias="personaddress_unit")
    isverified: str | None = Field(default=None, alias="personaddress_isverified")


class PersonAddressAssoc(BaseModel):
    addresspriorityorder: str | None = Field(
        default=None, alias="personaddressassoc_addresspriorityorder"
    )
    addresstypecodesetid: str | None = Field(
        default=None, alias="personaddressassoc_addresstypecodesetid"
    )
    personaddressassocid: str | None = Field(
        default=None, alias="personaddressassoc_personaddressassocid"
    )
    personaddressid: str | None = Field(
        default=None, alias="personaddressassoc_personaddressid"
    )
    personid: str | None = Field(default=None, alias="personaddressassoc_personid")
    whencreated: str | None = Field(
        default=None, alias="personaddressassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="personaddressassoc_whenmodified"
    )
    whocreated: str | None = Field(default=None, alias="personaddressassoc_whocreated")
    whomodified: str | None = Field(
        default=None, alias="personaddressassoc_whomodified"
    )
    startdate: str | None = Field(default=None, alias="personaddressassoc_startdate")
    enddate: str | None = Field(default=None, alias="personaddressassoc_enddate")


class PersonEmailAddressAssoc(BaseModel):
    emailaddressid: str | None = Field(
        default=None, alias="personemailaddressassoc_emailaddressid"
    )
    emailaddresspriorityorder: str | None = Field(
        default=None, alias="personemailaddressassoc_emailaddresspriorityorder"
    )
    emailtypecodesetid: str | None = Field(
        default=None, alias="personemailaddressassoc_emailtypecodesetid"
    )
    isprimaryemailaddress: str | None = Field(
        default=None, alias="personemailaddressassoc_isprimaryemailaddress"
    )
    personemailaddressassocid: str | None = Field(
        default=None, alias="personemailaddressassoc_personemailaddressassocid"
    )
    personid: str | None = Field(default=None, alias="personemailaddressassoc_personid")
    whencreated: str | None = Field(
        default=None, alias="personemailaddressassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="personemailaddressassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, alias="personemailaddressassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, alias="personemailaddressassoc_whomodified"
    )


class Reenrollments(BaseModel):
    id: str | None = Field(default=None, alias="reenrollments_id")
    dcid: str | None = Field(default=None, alias="reenrollments_dcid")
    enrollmentcode: str | None = Field(
        default=None, alias="reenrollments_enrollmentcode"
    )
    entrydate: str | None = Field(default=None, alias="reenrollments_entrydate")
    exitdate: str | None = Field(default=None, alias="reenrollments_exitdate")
    fteid: str | None = Field(default=None, alias="reenrollments_fteid")
    fulltimeequiv_obsolete: str | None = Field(
        default=None, alias="reenrollments_fulltimeequiv_obsolete"
    )
    grade_level: str | None = Field(default=None, alias="reenrollments_grade_level")
    lunchstatus: str | None = Field(default=None, alias="reenrollments_lunchstatus")
    membershipshare: str | None = Field(
        default=None, alias="reenrollments_membershipshare"
    )
    schoolid: str | None = Field(default=None, alias="reenrollments_schoolid")
    studentid: str | None = Field(default=None, alias="reenrollments_studentid")
    studentschlenrl_guid: str | None = Field(
        default=None, alias="reenrollments_studentschlenrl_guid"
    )
    tuitionpayer: str | None = Field(default=None, alias="reenrollments_tuitionpayer")
    type: str | None = Field(default=None, alias="reenrollments_type")
    exitcomment: str | None = Field(default=None, alias="reenrollments_exitcomment")
    districtofresidence: str | None = Field(
        default=None, alias="reenrollments_districtofresidence"
    )
    entrycode: str | None = Field(default=None, alias="reenrollments_entrycode")
    exitcode: str | None = Field(default=None, alias="reenrollments_exitcode")
    entrycomment: str | None = Field(default=None, alias="reenrollments_entrycomment")


class SNJCrsX(BaseModel):
    coursesdcid: str | None = Field(default=None, alias="s_nj_crs_x_coursesdcid")
    exclude_course_submission_tf: str | None = Field(
        default=None, alias="s_nj_crs_x_exclude_course_submission_tf"
    )
    sla_include_tf: str | None = Field(default=None, alias="s_nj_crs_x_sla_include_tf")
    whencreated: str | None = Field(default=None, alias="s_nj_crs_x_whencreated")
    whenmodified: str | None = Field(default=None, alias="s_nj_crs_x_whenmodified")
    whocreated: str | None = Field(default=None, alias="s_nj_crs_x_whocreated")
    whomodified: str | None = Field(default=None, alias="s_nj_crs_x_whomodified")


class SNJRenX(BaseModel):
    city: str | None = Field(default=None, alias="s_nj_ren_x_city")
    countycodeattending: str | None = Field(
        default=None, alias="s_nj_ren_x_countycodeattending"
    )
    countycodereceiving: str | None = Field(
        default=None, alias="s_nj_ren_x_countycodereceiving"
    )
    districtcodeattending: str | None = Field(
        default=None, alias="s_nj_ren_x_districtcodeattending"
    )
    districtcodereceiving: str | None = Field(
        default=None, alias="s_nj_ren_x_districtcodereceiving"
    )
    districtentrydate: str | None = Field(
        default=None, alias="s_nj_ren_x_districtentrydate"
    )
    homeless_code: str | None = Field(default=None, alias="s_nj_ren_x_homeless_code")
    lep_completion_date_refused: str | None = Field(
        default=None, alias="s_nj_ren_x_lep_completion_date_refused"
    )
    lep_tf: str | None = Field(default=None, alias="s_nj_ren_x_lep_tf")
    liep_languageofinstruction: str | None = Field(
        default=None, alias="s_nj_ren_x_liep_languageofinstruction"
    )
    pid_504_tf: str | None = Field(default=None, alias="s_nj_ren_x_pid_504_tf")
    reenrollmentsdcid: str | None = Field(
        default=None, alias="s_nj_ren_x_reenrollmentsdcid"
    )
    residentmunicipalcode: str | None = Field(
        default=None, alias="s_nj_ren_x_residentmunicipalcode"
    )
    retained_tf: str | None = Field(default=None, alias="s_nj_ren_x_retained_tf")
    schoolcodeattending: str | None = Field(
        default=None, alias="s_nj_ren_x_schoolcodeattending"
    )
    schoolcodereceiving: str | None = Field(
        default=None, alias="s_nj_ren_x_schoolcodereceiving"
    )
    schoolentrydate: str | None = Field(
        default=None, alias="s_nj_ren_x_schoolentrydate"
    )
    sid_excludeenrollment: str | None = Field(
        default=None, alias="s_nj_ren_x_sid_excludeenrollment"
    )
    sld_basic_reading_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_basic_reading_yn"
    )
    sld_listen_comp_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_listen_comp_yn"
    )
    sld_math_cal_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_math_cal_yn"
    )
    sld_math_prob_solve_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_math_prob_solve_yn"
    )
    sld_oral_expresn_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_oral_expresn_yn"
    )
    sld_read_fluency_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_read_fluency_yn"
    )
    sld_reading_comp_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_reading_comp_yn"
    )
    sld_writn_exprsn_yn: str | None = Field(
        default=None, alias="s_nj_ren_x_sld_writn_exprsn_yn"
    )
    specialed_classification: str | None = Field(
        default=None, alias="s_nj_ren_x_specialed_classification"
    )
    titleiindicator: str | None = Field(
        default=None, alias="s_nj_ren_x_titleiindicator"
    )
    whencreated: str | None = Field(default=None, alias="s_nj_ren_x_whencreated")
    whenmodified: str | None = Field(default=None, alias="s_nj_ren_x_whenmodified")
    whocreated: str | None = Field(default=None, alias="s_nj_ren_x_whocreated")
    whomodified: str | None = Field(default=None, alias="s_nj_ren_x_whomodified")


class SNJStuX(BaseModel):
    annual_iep_review_meeting_date: str | None = Field(
        default=None, alias="s_nj_stu_x_annual_iep_review_meeting_date"
    )
    birthplace_refusal: str | None = Field(
        default=None, alias="s_nj_stu_x_birthplace_refusal"
    )
    cityofbirth: str | None = Field(default=None, alias="s_nj_stu_x_cityofbirth")
    counseling_services_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_counseling_services_yn"
    )
    countryofbirth: str | None = Field(default=None, alias="s_nj_stu_x_countryofbirth")
    countycodeattending: str | None = Field(
        default=None, alias="s_nj_stu_x_countycodeattending"
    )
    countycodereceiving: str | None = Field(
        default=None, alias="s_nj_stu_x_countycodereceiving"
    )
    districtcodeattending: str | None = Field(
        default=None, alias="s_nj_stu_x_districtcodeattending"
    )
    districtcodereceiving: str | None = Field(
        default=None, alias="s_nj_stu_x_districtcodereceiving"
    )
    early_intervention_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_early_intervention_yn"
    )
    eligibility_determ_date: str | None = Field(
        default=None, alias="s_nj_stu_x_eligibility_determ_date"
    )
    immigrantstatus_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_immigrantstatus_yn"
    )
    includeinassareport_tf: str | None = Field(
        default=None, alias="s_nj_stu_x_includeinassareport_tf"
    )
    includeinctereport_tf: str | None = Field(
        default=None, alias="s_nj_stu_x_includeinctereport_tf"
    )
    includeinnjsmart_tf: str | None = Field(
        default=None, alias="s_nj_stu_x_includeinnjsmart_tf"
    )
    includeinstucourse_tf: str | None = Field(
        default=None, alias="s_nj_stu_x_includeinstucourse_tf"
    )
    initial_iep_meeting_date: str | None = Field(
        default=None, alias="s_nj_stu_x_initial_iep_meeting_date"
    )
    initial_process_delay_reason: str | None = Field(
        default=None, alias="s_nj_stu_x_initial_process_delay_reason"
    )
    lep_completion_date_refused: str | None = Field(
        default=None, alias="s_nj_stu_x_lep_completion_date_refused"
    )
    lep_tf: str | None = Field(default=None, alias="s_nj_stu_x_lep_tf")
    liep_classification: str | None = Field(
        default=None, alias="s_nj_stu_x_liep_classification"
    )
    liep_languageofinstruction: str | None = Field(
        default=None, alias="s_nj_stu_x_liep_languageofinstruction"
    )
    lunchstatusoverride: str | None = Field(
        default=None, alias="s_nj_stu_x_lunchstatusoverride"
    )
    migrant_tf: str | None = Field(default=None, alias="s_nj_stu_x_migrant_tf")
    occupational_therapy_serv_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_occupational_therapy_serv_yn"
    )
    other_related_services_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_other_related_services_yn"
    )
    parent_consent_intial_iep_date: str | None = Field(
        default=None, alias="s_nj_stu_x_parent_consent_intial_iep_date"
    )
    parent_consent_obtain_code: str | None = Field(
        default=None, alias="s_nj_stu_x_parent_consent_obtain_code"
    )
    parental_consent_eval_date: str | None = Field(
        default=None, alias="s_nj_stu_x_parental_consent_eval_date"
    )
    physical_therapy_services_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_physical_therapy_services_yn"
    )
    pid_504_tf: str | None = Field(default=None, alias="s_nj_stu_x_pid_504_tf")
    referral_date: str | None = Field(default=None, alias="s_nj_stu_x_referral_date")
    residentmunicipalcode: str | None = Field(
        default=None, alias="s_nj_stu_x_residentmunicipalcode"
    )
    schoolcodeattending: str | None = Field(
        default=None, alias="s_nj_stu_x_schoolcodeattending"
    )
    schoolcodereceiving: str | None = Field(
        default=None, alias="s_nj_stu_x_schoolcodereceiving"
    )
    sid_excludeenrollment: str | None = Field(
        default=None, alias="s_nj_stu_x_sid_excludeenrollment"
    )
    sld_basic_reading_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_basic_reading_yn"
    )
    sld_listen_comp_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_listen_comp_yn"
    )
    sld_math_cal_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_math_cal_yn"
    )
    sld_math_prob_solve_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_math_prob_solve_yn"
    )
    sld_oral_expresn_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_oral_expresn_yn"
    )
    sld_read_fluency_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_read_fluency_yn"
    )
    sld_reading_comp_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_reading_comp_yn"
    )
    sld_writn_exprsn_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_sld_writn_exprsn_yn"
    )
    special_education_placement: str | None = Field(
        default=None, alias="s_nj_stu_x_special_education_placement"
    )
    specialed_classification: str | None = Field(
        default=None, alias="s_nj_stu_x_specialed_classification"
    )
    speech_lang_theapy_services_yn: str | None = Field(
        default=None, alias="s_nj_stu_x_speech_lang_theapy_services_yn"
    )
    state_lep_status: str | None = Field(
        default=None, alias="s_nj_stu_x_state_lep_status"
    )
    stateofbirth: str | None = Field(default=None, alias="s_nj_stu_x_stateofbirth")
    studentsdcid: str | None = Field(default=None, alias="s_nj_stu_x_studentsdcid")
    titleiindicator: str | None = Field(
        default=None, alias="s_nj_stu_x_titleiindicator"
    )
    tuition_code: str | None = Field(default=None, alias="s_nj_stu_x_tuition_code")
    whencreated: str | None = Field(default=None, alias="s_nj_stu_x_whencreated")
    whenmodified: str | None = Field(default=None, alias="s_nj_stu_x_whenmodified")
    whocreated: str | None = Field(default=None, alias="s_nj_stu_x_whocreated")
    whomodified: str | None = Field(default=None, alias="s_nj_stu_x_whomodified")


class SchoolStaff(BaseModel):
    id: str | None = Field(default=None, alias="schoolstaff_id")
    dcid: str | None = Field(default=None, alias="schoolstaff_dcid")
    balance1: str | None = Field(default=None, alias="schoolstaff_balance1")
    balance2: str | None = Field(default=None, alias="schoolstaff_balance2")
    balance3: str | None = Field(default=None, alias="schoolstaff_balance3")
    balance4: str | None = Field(default=None, alias="schoolstaff_balance4")
    ip_address: str | None = Field(default=None, alias="schoolstaff_ip_address")
    noofcurclasses: str | None = Field(default=None, alias="schoolstaff_noofcurclasses")
    sched_isteacherfree: str | None = Field(
        default=None, alias="schoolstaff_sched_isteacherfree"
    )
    sched_lunch: str | None = Field(default=None, alias="schoolstaff_sched_lunch")
    sched_maximumconsecutive: str | None = Field(
        default=None, alias="schoolstaff_sched_maximumconsecutive"
    )
    sched_maximumcourses: str | None = Field(
        default=None, alias="schoolstaff_sched_maximumcourses"
    )
    sched_maximumduty: str | None = Field(
        default=None, alias="schoolstaff_sched_maximumduty"
    )
    sched_maximumfree: str | None = Field(
        default=None, alias="schoolstaff_sched_maximumfree"
    )
    sched_maxpers: str | None = Field(default=None, alias="schoolstaff_sched_maxpers")
    sched_maxpreps: str | None = Field(default=None, alias="schoolstaff_sched_maxpreps")
    sched_scheduled: str | None = Field(
        default=None, alias="schoolstaff_sched_scheduled"
    )
    sched_substitute: str | None = Field(
        default=None, alias="schoolstaff_sched_substitute"
    )
    sched_teachermoreoneschool: str | None = Field(
        default=None, alias="schoolstaff_sched_teachermoreoneschool"
    )
    sched_totalcourses: str | None = Field(
        default=None, alias="schoolstaff_sched_totalcourses"
    )
    sched_usebuilding: str | None = Field(
        default=None, alias="schoolstaff_sched_usebuilding"
    )
    sched_usehouse: str | None = Field(default=None, alias="schoolstaff_sched_usehouse")
    schoolid: str | None = Field(default=None, alias="schoolstaff_schoolid")
    staffstatus: str | None = Field(default=None, alias="schoolstaff_staffstatus")
    status: str | None = Field(default=None, alias="schoolstaff_status")
    transaction_date: str | None = Field(
        default=None, alias="schoolstaff_transaction_date"
    )
    users_dcid: str | None = Field(default=None, alias="schoolstaff_users_dcid")
    whomodifiedid: str | None = Field(default=None, alias="schoolstaff_whomodifiedid")
    whomodifiedtype: str | None = Field(
        default=None, alias="schoolstaff_whomodifiedtype"
    )
    log: str | None = Field(default=None, alias="schoolstaff_log")


class SPEnrollments(BaseModel):
    id: str | None = Field(default=None, alias="spenrollments_id")
    dcid: str | None = Field(default=None, alias="spenrollments_dcid")
    code1: str | None = Field(default=None, alias="spenrollments_code1")
    code2: str | None = Field(default=None, alias="spenrollments_code2")
    enter_date: str | None = Field(default=None, alias="spenrollments_enter_date")
    exit_date: str | None = Field(default=None, alias="spenrollments_exit_date")
    exitcode: str | None = Field(default=None, alias="spenrollments_exitcode")
    gradelevel: str | None = Field(default=None, alias="spenrollments_gradelevel")
    programid: str | None = Field(default=None, alias="spenrollments_programid")
    psguid: str | None = Field(default=None, alias="spenrollments_psguid")
    schoolid: str | None = Field(default=None, alias="spenrollments_schoolid")
    sp_comment: str | None = Field(default=None, alias="spenrollments_sp_comment")
    studentid: str | None = Field(default=None, alias="spenrollments_studentid")


class CC(BaseModel):
    id: str | None = Field(default=None, alias="cc_id")
    dcid: str | None = Field(default=None, alias="cc_dcid")
    attendance_type_code: str | None = Field(
        default=None, alias="cc_attendance_type_code"
    )
    course_number: str | None = Field(default=None, alias="cc_course_number")
    currentabsences: str | None = Field(default=None, alias="cc_currentabsences")
    currenttardies: str | None = Field(default=None, alias="cc_currenttardies")
    dateenrolled: str | None = Field(default=None, alias="cc_dateenrolled")
    dateleft: str | None = Field(default=None, alias="cc_dateleft")
    expression: str | None = Field(default=None, alias="cc_expression")
    lastattmod: str | None = Field(default=None, alias="cc_lastattmod")
    log: str | None = Field(default=None, alias="cc_log")
    origsectionid: str | None = Field(default=None, alias="cc_origsectionid")
    schoolid: str | None = Field(default=None, alias="cc_schoolid")
    section_number: str | None = Field(default=None, alias="cc_section_number")
    sectionid: str | None = Field(default=None, alias="cc_sectionid")
    studentid: str | None = Field(default=None, alias="cc_studentid")
    studyear: str | None = Field(default=None, alias="cc_studyear")
    teacherid: str | None = Field(default=None, alias="cc_teacherid")
    termid: str | None = Field(default=None, alias="cc_termid")
    transaction_date: str | None = Field(default=None, alias="cc_transaction_date")
    unused2: str | None = Field(default=None, alias="cc_unused2")
    unused3: str | None = Field(default=None, alias="cc_unused3")
    whomodifiedid: str | None = Field(default=None, alias="cc_whomodifiedid")
    whomodifiedtype: str | None = Field(default=None, alias="cc_whomodifiedtype")
    ip_address: str | None = Field(default=None, alias="cc_ip_address")


class EmailAddress(BaseModel):
    emailaddress: str | None = Field(default=None, alias="emailaddress_emailaddress")
    emailaddressid: str | None = Field(
        default=None, alias="emailaddress_emailaddressid"
    )
    whencreated: str | None = Field(default=None, alias="emailaddress_whencreated")
    whenmodified: str | None = Field(default=None, alias="emailaddress_whenmodified")
    whocreated: str | None = Field(default=None, alias="emailaddress_whocreated")
    whomodified: str | None = Field(default=None, alias="emailaddress_whomodified")


class PersonPhoneNumberAssoc(BaseModel):
    ispreferred: str | None = Field(
        default=None, alias="personphonenumberassoc_ispreferred"
    )
    personid: str | None = Field(default=None, alias="personphonenumberassoc_personid")
    personphonenumberassocid: str | None = Field(
        default=None, alias="personphonenumberassoc_personphonenumberassocid"
    )
    phonenumberasentered: str | None = Field(
        default=None, alias="personphonenumberassoc_phonenumberasentered"
    )
    phonenumberid: str | None = Field(
        default=None, alias="personphonenumberassoc_phonenumberid"
    )
    phonenumberpriorityorder: str | None = Field(
        default=None, alias="personphonenumberassoc_phonenumberpriorityorder"
    )
    phonetypecodesetid: str | None = Field(
        default=None, alias="personphonenumberassoc_phonetypecodesetid"
    )
    whencreated: str | None = Field(
        default=None, alias="personphonenumberassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="personphonenumberassoc_whenmodified"
    )
    whocreated: str | None = Field(
        default=None, alias="personphonenumberassoc_whocreated"
    )
    whomodified: str | None = Field(
        default=None, alias="personphonenumberassoc_whomodified"
    )


class StudentContactAssoc(BaseModel):
    contactpriorityorder: str | None = Field(
        default=None, alias="studentcontactassoc_contactpriorityorder"
    )
    currreltypecodesetid: str | None = Field(
        default=None, alias="studentcontactassoc_currreltypecodesetid"
    )
    personid: str | None = Field(default=None, alias="studentcontactassoc_personid")
    studentcontactassocid: str | None = Field(
        default=None, alias="studentcontactassoc_studentcontactassocid"
    )
    studentdcid: str | None = Field(
        default=None, alias="studentcontactassoc_studentdcid"
    )
    whencreated: str | None = Field(
        default=None, alias="studentcontactassoc_whencreated"
    )
    whenmodified: str | None = Field(
        default=None, alias="studentcontactassoc_whenmodified"
    )
    whocreated: str | None = Field(default=None, alias="studentcontactassoc_whocreated")
    whomodified: str | None = Field(
        default=None, alias="studentcontactassoc_whomodified"
    )
