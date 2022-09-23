import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.config.powerschool.db.schema import PS_DB_CONFIG
from teamster.core.ops.powerschool.db import extract


@config_mapping(config_schema=PS_DB_CONFIG)
def construct_graph_config(config):
    query_config = config["query"]
    destination_config = config["destination"]

    [(sql_key, sql_value)] = query_config["sql"].items()
    if sql_key == "text":
        query = text(sql_value)
    elif sql_key == "file":
        query_file = pathlib.Path(sql_value).absolute()
        with query_file.open(mode="r") as f:
            query = text(f.read())
    elif sql_key == "schema":
        query = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(sql_value.get("where", "")))
        )

    return {
        "extract": {
            "config": {
                "query": query,
                "output_fmt": query_config["output_fmt"],
                "partition_size": query_config["partition_size"],
                "destination_type": destination_config["type"],
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
def sync_all():
    assignmentcategoryassoc = sync_table.alias("assignmentcategoryassoc")
    assignmentcategoryassoc()

    assignmentsection = sync_table.alias("assignmentsection")
    assignmentsection()

    attendance = sync_table.alias("attendance")
    attendance()

    attendance_code = sync_table.alias("attendance_code")
    attendance_code()

    attendance_conversion_items = sync_table.alias("attendance_conversion_items")
    attendance_conversion_items()

    bell_schedule = sync_table.alias("bell_schedule")
    bell_schedule()

    calendar_day = sync_table.alias("calendar_day")
    calendar_day()

    cc = sync_table.alias("cc")
    cc()

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

    log = sync_table.alias("log")
    log()

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

    pgfinalgrades = sync_table.alias("pgfinalgrades")
    pgfinalgrades()

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

    storedgrades = sync_table.alias("storedgrades")
    storedgrades()

    studentcontactassoc = sync_table.alias("studentcontactassoc")
    studentcontactassoc()

    studentcontactdetail = sync_table.alias("studentcontactdetail")
    studentcontactdetail()

    studentcorefields = sync_table.alias("studentcorefields")
    studentcorefields()

    studentrace = sync_table.alias("studentrace")
    studentrace()

    students = sync_table.alias("students")
    students()

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

    assignmentscore_S01 = sync_table.alias("assignmentscore_S01")
    assignmentscore_S01()
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

    # # extensions
    # s_nj_crs_x = sync_table.alias("s_nj_crs_x")
    # s_nj_crs_x()

    # s_nj_ren_x = sync_table.alias("s_nj_ren_x")
    # s_nj_ren_x()

    # s_nj_stu_x = sync_table.alias("s_nj_stu_x")
    # s_nj_stu_x()

    # s_nj_usr_x = sync_table.alias("s_nj_usr_x")
    # s_nj_usr_x()

    # u_clg_et_stu = sync_table.alias("u_clg_et_stu")
    # u_clg_et_stu()

    # u_clg_et_stu_alt = sync_table.alias("u_clg_et_stu_alt")
    # u_clg_et_stu_alt()

    # u_def_ext_students = sync_table.alias("u_def_ext_students")
    # u_def_ext_students()

    # u_studentsuserfields = sync_table.alias("u_studentsuserfields")
    # u_studentsuserfields()
