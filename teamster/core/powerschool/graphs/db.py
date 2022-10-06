import pathlib

from dagster import config_mapping, graph
from sqlalchemy import literal_column, select, table, text

from teamster.core.powerschool.config.db.schema import PS_DB_CONFIG
from teamster.core.powerschool.ops.db import extract


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
def test_sync():
    test = sync_table.alias("test")
    test()


@graph
def sync():
    tables = [
        "assignmentsection",
        "attendance_code",
        "attendance_conversion_items",
        "bell_schedule",
        "calendar_day",
        "codeset",
        "courses",
        "cycle_day",
        "districtteachercategory",
        "emailaddress",
        "fte",
        "gen",
        "gradecalcformulaweight",
        "gradecalcschoolassoc",
        "gradecalculationtype",
        "gradeformulaset",
        "gradescaleitem",
        "gradeschoolconfig",
        "gradeschoolformulaassoc",
        "gradesectionconfig",
        "originalcontactmap",
        "period",
        "person",
        "personaddress",
        "personaddressassoc",
        "personemailaddressassoc",
        "personphonenumberassoc",
        "phonenumber",
        "prefs",
        "reenrollments",
        "roledef",
        "schools",
        "schoolstaff",
        "sections",
        "sectionteacher",
        "spenrollments",
        "students",
        "studentcontactassoc",
        "studentcontactdetail",
        "studentcorefields",
        "studentrace",
        "teachercategory",
        "termbins",
        "terms",
        "test",
        "testscore",
        "users",
        "assignmentcategoryassoc",
        "cc",
        "log",
        "storedgrades",
        "pgfinalgrades",
        "attendance",
        "assignmentscore",
    ]

    for tbl in tables:
        graph_instance = sync_table.alias(tbl)
        graph_instance()
