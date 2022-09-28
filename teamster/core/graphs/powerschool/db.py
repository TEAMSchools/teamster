import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import PS_DB_CONFIG
from teamster.core.ops.powerschool.db import extract


@config_mapping(config_schema=PS_DB_CONFIG)
def construct_graph_config(config):
    [(sql_key, sql_value)] = config["sql"].items()
    if sql_key == "text":
        sql = text(sql_value)
    elif sql_key == "file":
        sql_file = pathlib.Path(sql_value).absolute()
        with sql_file.open(mode="r") as f:
            sql = text(f.read())
    elif sql_key == "schema":
        sql = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(sql_value.get("where", "")))
        )

    return {
        "extract": {
            "config": {
                "sql": sql,
                "partition_size": config["partition_size"],
            }
        }
    }


@graph(config=construct_graph_config)
def sync_table():
    extract()


@graph
def test_sync_all():
    test = sync_table.alias("test")
    test()


@graph
def resync():
    assignmentsection = sync_table.alias("assignmentsection")
    assignmentsection()

    attendance_code = sync_table.alias("attendance_code")
    attendance_code()

    attendance_conversion_items = sync_table.alias("attendance_conversion_items")
    attendance_conversion_items()

    bell_schedule = sync_table.alias("bell_schedule")
    bell_schedule()

    calendar_day = sync_table.alias("calendar_day")
    calendar_day()

    codeset = sync_table.alias("codeset")
    codeset()

    courses = sync_table.alias("courses")
    courses()

    cycle_day = sync_table.alias("cycle_day")
    cycle_day()

    districtteachercategory = sync_table.alias("districtteachercategory")
    districtteachercategory()

    emailaddress = sync_table.alias("emailaddress")
    emailaddress()

    fte = sync_table.alias("fte")
    fte()

    gen = sync_table.alias("gen")
    gen()

    gradecalcformulaweight = sync_table.alias("gradecalcformulaweight")
    gradecalcformulaweight()

    gradecalcschoolassoc = sync_table.alias("gradecalcschoolassoc")
    gradecalcschoolassoc()

    gradecalculationtype = sync_table.alias("gradecalculationtype")
    gradecalculationtype()

    gradeformulaset = sync_table.alias("gradeformulaset")
    gradeformulaset()

    gradescaleitem = sync_table.alias("gradescaleitem")
    gradescaleitem()

    gradeschoolconfig = sync_table.alias("gradeschoolconfig")
    gradeschoolconfig()

    gradeschoolformulaassoc = sync_table.alias("gradeschoolformulaassoc")
    gradeschoolformulaassoc()

    gradesectionconfig = sync_table.alias("gradesectionconfig")
    gradesectionconfig()

    originalcontactmap = sync_table.alias("originalcontactmap")
    originalcontactmap()

    period = sync_table.alias("period")
    period()

    person = sync_table.alias("person")
    person()

    personaddress = sync_table.alias("personaddress")
    personaddress()

    personaddressassoc = sync_table.alias("personaddressassoc")
    personaddressassoc()

    personemailaddressassoc = sync_table.alias("personemailaddressassoc")
    personemailaddressassoc()

    personphonenumberassoc = sync_table.alias("personphonenumberassoc")
    personphonenumberassoc()

    phonenumber = sync_table.alias("phonenumber")
    phonenumber()

    prefs = sync_table.alias("prefs")
    prefs()

    reenrollments = sync_table.alias("reenrollments")
    reenrollments()

    roledef = sync_table.alias("roledef")
    roledef()

    schools = sync_table.alias("schools")
    schools()

    schoolstaff = sync_table.alias("schoolstaff")
    schoolstaff()

    sections = sync_table.alias("sections")
    sections()

    sectionteacher = sync_table.alias("sectionteacher")
    sectionteacher()

    spenrollments = sync_table.alias("spenrollments")
    spenrollments()

    students = sync_table.alias("students")
    students()

    studentcontactassoc = sync_table.alias("studentcontactassoc")
    studentcontactassoc()

    studentcontactdetail = sync_table.alias("studentcontactdetail")
    studentcontactdetail()

    studentcorefields = sync_table.alias("studentcorefields")
    studentcorefields()

    studentrace = sync_table.alias("studentrace")
    studentrace()

    teachercategory = sync_table.alias("teachercategory")
    teachercategory()

    termbins = sync_table.alias("termbins")
    termbins()

    terms = sync_table.alias("terms")
    terms()

    test = sync_table.alias("test")
    test()

    testscore = sync_table.alias("testscore")
    testscore()

    users = sync_table.alias("users")
    users()

    # 100,000
    assignmentcategoryassoc_R01 = sync_table.alias("assignmentcategoryassoc_R01")
    assignmentcategoryassoc_R01()
    assignmentcategoryassoc_R02 = sync_table.alias("assignmentcategoryassoc_R02")
    assignmentcategoryassoc_R02()
    assignmentcategoryassoc_R03 = sync_table.alias("assignmentcategoryassoc_R03")
    assignmentcategoryassoc_R03()
    assignmentcategoryassoc_R04 = sync_table.alias("assignmentcategoryassoc_R04")
    assignmentcategoryassoc_R04()
    assignmentcategoryassoc_R05 = sync_table.alias("assignmentcategoryassoc_R05")
    assignmentcategoryassoc_R05()

    cc_R01 = sync_table.alias("cc_R01")
    cc_R01()
    cc_R02 = sync_table.alias("cc_R02")
    cc_R02()
    cc_R03 = sync_table.alias("cc_R03")
    cc_R03()
    cc_R04 = sync_table.alias("cc_R04")
    cc_R04()
    cc_R05 = sync_table.alias("cc_R05")
    cc_R05()
    cc_R06 = sync_table.alias("cc_R06")
    cc_R06()

    log_R01 = sync_table.alias("log_R01")
    log_R01()
    log_R02 = sync_table.alias("log_R02")
    log_R02()
    log_R03 = sync_table.alias("log_R03")
    log_R03()
    log_R04 = sync_table.alias("log_R04")
    log_R04()

    storedgrades_R01 = sync_table.alias("storedgrades_R01")
    storedgrades_R01()
    storedgrades_R02 = sync_table.alias("storedgrades_R02")
    storedgrades_R02()
    storedgrades_R03 = sync_table.alias("storedgrades_R03")
    storedgrades_R03()
    storedgrades_R04 = sync_table.alias("storedgrades_R04")
    storedgrades_R04()
    storedgrades_R05 = sync_table.alias("storedgrades_R05")
    storedgrades_R05()
    storedgrades_R06 = sync_table.alias("storedgrades_R06")
    storedgrades_R06()
    storedgrades_R07 = sync_table.alias("storedgrades_R07")
    storedgrades_R07()
    storedgrades_R08 = sync_table.alias("storedgrades_R08")
    storedgrades_R08()
    storedgrades_R09 = sync_table.alias("storedgrades_R09")
    storedgrades_R09()
    storedgrades_R10 = sync_table.alias("storedgrades_R10")
    storedgrades_R10()

    # 1,000,000
    pgfinalgrades_R01 = sync_table.alias("pgfinalgrades_R01")
    pgfinalgrades_R01()
    pgfinalgrades_R02 = sync_table.alias("pgfinalgrades_R02")
    pgfinalgrades_R02()
    pgfinalgrades_R03 = sync_table.alias("pgfinalgrades_R03")
    pgfinalgrades_R03()

    attendance_R01 = sync_table.alias("attendance_R01")
    attendance_R01()
    attendance_R02 = sync_table.alias("attendance_R02")
    attendance_R02()
    attendance_R03 = sync_table.alias("attendance_R03")
    attendance_R03()
    attendance_R04 = sync_table.alias("attendance_R04")
    attendance_R04()
    attendance_R05 = sync_table.alias("attendance_R05")
    attendance_R05()

    assignmentscore_R01 = sync_table.alias("assignmentscore_R01")
    assignmentscore_R01()
    assignmentscore_R02 = sync_table.alias("assignmentscore_R02")
    assignmentscore_R02()
    assignmentscore_R03 = sync_table.alias("assignmentscore_R03")
    assignmentscore_R03()
    assignmentscore_R04 = sync_table.alias("assignmentscore_R04")
    assignmentscore_R04()
    assignmentscore_R05 = sync_table.alias("assignmentscore_R05")
    assignmentscore_R05()
    assignmentscore_R06 = sync_table.alias("assignmentscore_R06")
    assignmentscore_R06()
    assignmentscore_R07 = sync_table.alias("assignmentscore_R07")
    assignmentscore_R07()
    assignmentscore_R08 = sync_table.alias("assignmentscore_R08")
    assignmentscore_R08()
    assignmentscore_R09 = sync_table.alias("assignmentscore_R09")
    assignmentscore_R09()
    assignmentscore_R10 = sync_table.alias("assignmentscore_R10")
    assignmentscore_R10()
    assignmentscore_R11 = sync_table.alias("assignmentscore_R11")
    assignmentscore_R11()


@graph
def sync_extensions():
    s_nj_crs_x = sync_table.alias("s_nj_crs_x")
    s_nj_crs_x()

    s_nj_ren_x = sync_table.alias("s_nj_ren_x")
    s_nj_ren_x()

    s_nj_stu_x = sync_table.alias("s_nj_stu_x")
    s_nj_stu_x()

    s_nj_usr_x = sync_table.alias("s_nj_usr_x")
    s_nj_usr_x()

    u_clg_et_stu = sync_table.alias("u_clg_et_stu")
    u_clg_et_stu()

    u_clg_et_stu_alt = sync_table.alias("u_clg_et_stu_alt")
    u_clg_et_stu_alt()

    u_def_ext_students = sync_table.alias("u_def_ext_students")
    u_def_ext_students()

    u_studentsuserfields = sync_table.alias("u_studentsuserfields")
    u_studentsuserfields()
