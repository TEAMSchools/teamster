import json

import py_avro_schema

from teamster.libraries.deanslist.schema import (
    Behavior,
    CommLog,
    DFFStats,
    Followup,
    Homework,
    Incident,
    ListModel,
    ReconcileAttendance,
    ReconcileSuspensions,
    Roster,
    RosterAssignment,
    Student,
    Term,
    User,
)


class behavior_record(Behavior):
    """helper class for backwards compatibility"""


class followups_record(Followup):
    """helper class for backwards compatibility"""


class homework_record(Homework):
    """helper class for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

BEHAVIOR_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=behavior_record, options=pas_options)
)

INCIDENTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Incident, options=pas_options)
)

ASSET_SCHEMA = {
    "comm-log": json.loads(py_avro_schema.generate(py_type=CommLog)),
    "lists": json.loads(py_avro_schema.generate(py_type=ListModel)),
    "roster-assignments": json.loads(py_avro_schema.generate(py_type=RosterAssignment)),
    "rosters": json.loads(py_avro_schema.generate(py_type=Roster)),
    "students": json.loads(py_avro_schema.generate(py_type=Student)),
    "terms": json.loads(py_avro_schema.generate(py_type=Term)),
    "users": json.loads(py_avro_schema.generate(py_type=User)),
    "reconcile_attendance": json.loads(
        py_avro_schema.generate(py_type=ReconcileAttendance)
    ),
    "reconcile_suspensions": json.loads(
        py_avro_schema.generate(py_type=ReconcileSuspensions)
    ),
    "followups": json.loads(
        py_avro_schema.generate(py_type=followups_record, options=pas_options)
    ),
    "homework": json.loads(
        py_avro_schema.generate(py_type=homework_record, options=pas_options)
    ),
    "incidents": INCIDENTS_SCHEMA,
    "dff/stats": json.loads(
        py_avro_schema.generate(py_type=DFFStats, options=pas_options)
    ),
}
