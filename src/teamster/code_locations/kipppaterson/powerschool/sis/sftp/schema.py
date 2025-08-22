import json

import py_avro_schema

from teamster.libraries.powerschool.sis.sftp.schema import (  # SPEnrollments,
    CC,
    FTE,
    Attendance,
    AttendanceCode,
    AttendanceConversionItems,
    BellSchedule,
    CalendarDay,
    CodeSet,
    Courses,
    CycleDay,
    EmailAddress,
    Gen,
    OriginalContactMap,
    Person,
    PersonAddress,
    PersonAddressAssoc,
    PersonEmailAddressAssoc,
    PersonPhoneNumberAssoc,
    PhoneNumber,
    Reenrollments,
    Schools,
    SchoolStaff,
    Sections,
    SNJCrsX,
    SNJRenX,
    SNJStuX,
    StudentContactAssoc,
    StudentContactDetail,
    StudentCoreFields,
    Students,
    TermBins,
    Terms,
    Users,
)

options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

ATTENDANCE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Attendance, options=options)
)

ATTENDANCE_CODE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=AttendanceCode, options=options)
)

ATTENDANCE_CONVERSION_ITEMS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=AttendanceConversionItems, options=options)
)

BELL_SCHEDULE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=BellSchedule, options=options)
)

CALENDAR_DAY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=CalendarDay, options=options)
)

CC_SCHEMA = json.loads(py_avro_schema.generate(py_type=CC, options=options))

CODESET_SCHEMA = json.loads(py_avro_schema.generate(py_type=CodeSet, options=options))

COURSES_SCHEMA = json.loads(py_avro_schema.generate(py_type=Courses, options=options))

CYCLE_DAY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=CycleDay, options=options)
)

EMAILADDRESS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=EmailAddress, options=options)
)

FTE_SCHEMA = json.loads(py_avro_schema.generate(py_type=FTE, options=options))

GEN_SCHEMA = json.loads(py_avro_schema.generate(py_type=Gen, options=options))

ORIGINALCONTACTMAP_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=OriginalContactMap, options=options)
)

PERSON_SCHEMA = json.loads(py_avro_schema.generate(py_type=Person, options=options))

PERSONADDRESS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PersonAddress, options=options)
)

PERSONADDRESSASSOC_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PersonAddressAssoc, options=options)
)

PERSONEMAILADDRESSASSOC_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PersonEmailAddressAssoc, options=options)
)

PERSONPHONENUMBERASSOC_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PersonPhoneNumberAssoc, options=options)
)

PHONENUMBER_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PhoneNumber, options=options)
)

REENROLLMENTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Reenrollments, options=options)
)

S_NJ_CRS_X_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SNJCrsX, options=options)
)

S_NJ_REN_X_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SNJRenX, options=options)
)

S_NJ_STU_X_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SNJStuX, options=options)
)

SCHOOLS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Schools, options=options))

SCHOOLSTAFF_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SchoolStaff, options=options)
)

SECTIONS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Sections, options=options))

# SPENROLLMENTS_SCHEMA = json.loads(
#     py_avro_schema.generate(py_type=SPEnrollments, options=options)
# )

STUDENTCONTACTASSOC_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentContactAssoc, options=options)
)

STUDENTCONTACTDETAIL_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentContactDetail, options=options)
)

STUDENTCOREFIELDS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentCoreFields, options=options)
)

STUDENTS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Students, options=options))

TERMBINS_SCHEMA = json.loads(py_avro_schema.generate(py_type=TermBins, options=options))

TERMS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Terms, options=options))

USERS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Users, options=options))

SCHEMAS = {
    "attendance": ATTENDANCE_SCHEMA,
    "attendance_code": ATTENDANCE_CODE_SCHEMA,
    "attendance_conversion_items": ATTENDANCE_CONVERSION_ITEMS_SCHEMA,
    "bell_schedule": BELL_SCHEDULE_SCHEMA,
    "calendar_day": CALENDAR_DAY_SCHEMA,
    "cc": CC_SCHEMA,
    "codeset": CODESET_SCHEMA,
    "courses": COURSES_SCHEMA,
    "cycle_day": CYCLE_DAY_SCHEMA,
    "emailaddress": EMAILADDRESS_SCHEMA,
    "fte": FTE_SCHEMA,
    "gen": GEN_SCHEMA,
    "originalcontactmap": ORIGINALCONTACTMAP_SCHEMA,
    "person": PERSON_SCHEMA,
    "personaddress": PERSONADDRESS_SCHEMA,
    "personaddressassoc": PERSONADDRESSASSOC_SCHEMA,
    "personemailaddressassoc": PERSONEMAILADDRESSASSOC_SCHEMA,
    "personphonenumberassoc": PERSONPHONENUMBERASSOC_SCHEMA,
    "phonenumber": PHONENUMBER_SCHEMA,
    "reenrollments": REENROLLMENTS_SCHEMA,
    "s_nj_crs_x": S_NJ_CRS_X_SCHEMA,
    "s_nj_ren_x": S_NJ_REN_X_SCHEMA,
    "s_nj_stu_x": S_NJ_STU_X_SCHEMA,
    "schools": SCHOOLS_SCHEMA,
    "schoolstaff": SCHOOLSTAFF_SCHEMA,
    "sections": SECTIONS_SCHEMA,
    # "spenrollments": SPENROLLMENTS_SCHEMA,
    "studentcontactassoc": STUDENTCONTACTASSOC_SCHEMA,
    "studentcontactdetail": STUDENTCONTACTDETAIL_SCHEMA,
    "studentcorefields": STUDENTCOREFIELDS_SCHEMA,
    "students": STUDENTS_SCHEMA,
    "termbins": TERMBINS_SCHEMA,
    "terms": TERMS_SCHEMA,
    "users": USERS_SCHEMA,
}
