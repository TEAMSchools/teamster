import re

from dagster import Any, Bool, In, Int, List, Out, Output, op

from teamster.core.utils.functions import get_last_schedule_run
from teamster.core.utils.variables import TODAY

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


@op(out={tbl: Out(Bool) for tbl in tables})
def get_counts(context):
    for tbl in tables:
        if tbl in [
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
        ]:
            yield Output(value=True, output_name=tbl)


@op(
    config_schema={"sql": Any, "partition_size": Int},
    ins={"has_count": In(dagster_type=Bool)},
    out={"data": Out(dagster_type=List[Any], is_required=False)},
    required_resource_keys={"db", "ssh", "file_manager"},
    tags={"dagster/priority": 1},
)
def extract(context, has_count):
    sql = context.op_config["sql"]
    file_manager_key = context.solid_handle.path[0]

    # organize partitions under table folder
    re_match = re.match(r"([\w_]+)_(R\d+)", file_manager_key)
    if re_match:
        table_name, resync_partition = re_match.groups()
        file_manager_key = f"{table_name}/{resync_partition}"

    # format where clause
    last_run = get_last_schedule_run(context) or TODAY
    sql.whereclause.text = sql.whereclause.text.format(
        today=TODAY.isoformat(timespec="microseconds"),
        last_run=last_run.isoformat(timespec="microseconds"),
    )

    if context.resources.ssh.tunnel:
        context.log.info("Starting SSH tunnel")
        ssh_tunnel = context.resources.ssh.get_tunnel()
        ssh_tunnel.start()
    else:
        ssh_tunnel = None

    data = context.resources.db.execute_query(
        query=sql, partition_size=context.op_config["partition_size"], output_fmt="file"
    )

    if ssh_tunnel is not None:
        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()

    if data:
        file_handles = []
        for i, fp in enumerate(data):
            if sql.whereclause.text == "":
                file_stem = f"{file_manager_key}_R{i}"
            else:
                file_stem = fp.stem

            with fp.open(mode="rb") as f:
                file_handle = context.resources.file_manager.write(
                    file_obj=f,
                    key=f"{file_manager_key}/{file_stem}",
                    ext=fp.suffix[1:],
                )

            context.log.info(f"Saved to {file_handle.path_desc}")
            file_handles.append(file_handle)

        yield Output(value=file_handles, output_name="data")
