import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db import schema, tables
from teamster.core.powerschool.ops.db import extract, get_counts


@config_mapping()
def construct_sync_multi_config(config):
    constructed_config = {}

    for tbl in config.items():
        table_name, config_val = tbl
        constructed_config[table_name] = {"config": config_val}

    return constructed_config


@config_mapping(config_schema=schema.PS_DB_CONFIG)
def construct_sync_table_config(config):
    [(sql_key, sql_value)] = config["sql"].items()
    if sql_key == "text":
        sql = text(sql_value)
    elif sql_key == "file":
        sql_file = pathlib.Path(sql_value).absolute()
        with sql_file.open(mode="r") as f:
            sql = text(f.read())
    elif sql_key == "schema":
        sql_where = sql_value.get("where")
        if sql_where is not None:
            constructed_sql_where = (
                f"{sql_where['column']} >= "
                f"TO_TIMESTAMP_TZ('{{{sql_where['value']}}}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')"
            )
        else:
            constructed_sql_where = ""

        sql = (
            select(*[literal_column(col) for col in sql_value["select"]])
            .select_from(table(**sql_value["table"]))
            .where(text(constructed_sql_where))
        )

    return {
        "extract": {
            "config": {
                "sql": sql,
                "partition_size": config["partition_size"],
            }
        }
    }


@graph(config=construct_sync_table_config)
def sync_table(has_count):
    extract(has_count)


# @graph
# def test_sync_table():
#     sync_table_inst = sync_table.alias("test_sync_table")
#     sync_table_inst()


@graph(config=construct_sync_multi_config)
def sync():
    valid_tables = get_counts()

    for tbl in tables.STANDARD_TABLES:
        sync_table_inst = sync_table.alias(tbl)
        sync_table_inst(getattr(valid_tables, tbl))


# @graph
# def sync():
#     valid_tables = get_counts()

# assignmentsection = sync_table.alias("assignmentsection")
# assignmentsection(valid_tables.assignmentsection)

# attendance_code = sync_table.alias("attendance_code")
# attendance_code(valid_tables.attendance_code)

# attendance_conversion_items = sync_table.alias("attendance_conversion_items")
# attendance_conversion_items(valid_tables.attendance_conversion_items)

# bell_schedule = sync_table.alias("bell_schedule")
# bell_schedule(valid_tables.bell_schedule)

# calendar_day = sync_table.alias("calendar_day")
# calendar_day(valid_tables.calendar_day)

# codeset = sync_table.alias("codeset")
# codeset(valid_tables.codeset)

# courses = sync_table.alias("courses")
# courses(valid_tables.courses)

# cycle_day = sync_table.alias("cycle_day")
# cycle_day(valid_tables.cycle_day)

# districtteachercategory = sync_table.alias("districtteachercategory")
# districtteachercategory(valid_tables.districtteachercategory)

# emailaddress = sync_table.alias("emailaddress")
# emailaddress(valid_tables.emailaddress)

# fte = sync_table.alias("fte")
# fte(valid_tables.fte)

# gen = sync_table.alias("gen")
# gen(valid_tables.gen)

# gradecalcformulaweight = sync_table.alias("gradecalcformulaweight")
# gradecalcformulaweight(valid_tables.gradecalcformulaweight)

# gradecalcschoolassoc = sync_table.alias("gradecalcschoolassoc")
# gradecalcschoolassoc(valid_tables.gradecalcschoolassoc)

# gradecalculationtype = sync_table.alias("gradecalculationtype")
# gradecalculationtype(valid_tables.gradecalculationtype)

# gradeformulaset = sync_table.alias("gradeformulaset")
# gradeformulaset(valid_tables.gradeformulaset)

# gradescaleitem = sync_table.alias("gradescaleitem")
# gradescaleitem(valid_tables.gradescaleitem)

# gradeschoolconfig = sync_table.alias("gradeschoolconfig")
# gradeschoolconfig(valid_tables.gradeschoolconfig)

# gradeschoolformulaassoc = sync_table.alias("gradeschoolformulaassoc")
# gradeschoolformulaassoc(valid_tables.gradeschoolformulaassoc)

# gradesectionconfig = sync_table.alias("gradesectionconfig")
# gradesectionconfig(valid_tables.gradesectionconfig)

# originalcontactmap = sync_table.alias("originalcontactmap")
# originalcontactmap(valid_tables.originalcontactmap)

# period = sync_table.alias("period")
# period(valid_tables.period)

# person = sync_table.alias("person")
# person(valid_tables.person)

# personaddress = sync_table.alias("personaddress")
# personaddress(valid_tables.personaddress)

# personaddressassoc = sync_table.alias("personaddressassoc")
# personaddressassoc(valid_tables.personaddressassoc)

# personemailaddressassoc = sync_table.alias("personemailaddressassoc")
# personemailaddressassoc(valid_tables.personemailaddressassoc)

# personphonenumberassoc = sync_table.alias("personphonenumberassoc")
# personphonenumberassoc(valid_tables.personphonenumberassoc)

# phonenumber = sync_table.alias("phonenumber")
# phonenumber(valid_tables.phonenumber)

# prefs = sync_table.alias("prefs")
# prefs(valid_tables.prefs)

# reenrollments = sync_table.alias("reenrollments")
# reenrollments(valid_tables.reenrollments)

# roledef = sync_table.alias("roledef")
# roledef(valid_tables.roledef)

# schools = sync_table.alias("schools")
# schools(valid_tables.schools)

# schoolstaff = sync_table.alias("schoolstaff")
# schoolstaff(valid_tables.schoolstaff)

# sections = sync_table.alias("sections")
# sections(valid_tables.sections)

# sectionteacher = sync_table.alias("sectionteacher")
# sectionteacher(valid_tables.sectionteacher)

# spenrollments = sync_table.alias("spenrollments")
# spenrollments(valid_tables.spenrollments)

# students = sync_table.alias("students")
# students(valid_tables.students)

# studentcontactassoc = sync_table.alias("studentcontactassoc")
# studentcontactassoc(valid_tables.studentcontactassoc)

# studentcontactdetail = sync_table.alias("studentcontactdetail")
# studentcontactdetail(valid_tables.studentcontactdetail)

# studentcorefields = sync_table.alias("studentcorefields")
# studentcorefields(valid_tables.studentcorefields)

# studentrace = sync_table.alias("studentrace")
# studentrace(valid_tables.studentrace)

# teachercategory = sync_table.alias("teachercategory")
# teachercategory(valid_tables.teachercategory)

# termbins = sync_table.alias("termbins")
# termbins(valid_tables.termbins)

# terms = sync_table.alias("terms")
# terms(valid_tables.terms)

# test = sync_table.alias("test")
# test(valid_tables.test)

# testscore = sync_table.alias("testscore")
# testscore(valid_tables.testscore)

# users = sync_table.alias("users")
# users(valid_tables.users)

# assignmentcategoryassoc = sync_table.alias("assignmentcategoryassoc")
# assignmentcategoryassoc(valid_tables.assignmentcategoryassoc)

# cc = sync_table.alias("cc")
# cc(valid_tables.cc)

# log = sync_table.alias("log")
# log(valid_tables.log)

# storedgrades = sync_table.alias("storedgrades")
# storedgrades(valid_tables.storedgrades)

# pgfinalgrades = sync_table.alias("pgfinalgrades")
# pgfinalgrades(valid_tables.pgfinalgrades)

# attendance = sync_table.alias("attendance")
# attendance(valid_tables.attendance)

# assignmentscore = sync_table.alias("assignmentscore")
# assignmentscore(valid_tables.assignmentscore)
