# trunk-ignore-all(pyright/reportIncompatibleVariableOverride)
import json

import py_avro_schema

from teamster.libraries.deanslist.schema import (
    Action,
    Behavior,
    CommLog,
    CustomField,
    Date,
    Followup,
    Homework,
    Incident,
    ListModel,
    Penalty,
    ReconcileAttendance,
    ReconcileSuspensions,
    Roster,
    RosterAssignment,
    Student,
    Term,
    User,
)


class CloseTS_record(Date):
    """helper class for backwards compatibility"""


class CreateTS_record(Date):
    """helper class for backwards compatibility"""


class DL_LASTUPDATE_record(Date):
    """helper class for backwards compatibility"""


class HearingDate_record(Date):
    """helper class for backwards compatibility"""


class IssueTS_record(Date):
    """helper class for backwards compatibility"""


class ReturnDate_record(Date):
    """helper class for backwards compatibility"""


class ReviewTS_record(Date):
    """helper class for backwards compatibility"""


class UpdateTS_record(Date):
    """helper class for backwards compatibility"""


class action_record(Action):
    """helper class for backwards compatibility"""


class custom_field_record(CustomField):
    """helper class for backwards compatibility"""


class penalty_record(Penalty):
    """helper class for backwards compatibility"""


class behavior_record(Behavior):
    """helper class for backwards compatibility"""


class followups_record(Followup):
    """helper class for backwards compatibility"""


class homework_record(Homework):
    """helper class for backwards compatibility"""


class incidents_record(Incident):
    """helper class for backwards compatibility"""

    CloseTS: CloseTS_record | None = None
    CreateTS: CreateTS_record | None = None
    DL_LASTUPDATE: DL_LASTUPDATE_record | None = None
    HearingDate: HearingDate_record | None = None
    IssueTS: IssueTS_record | None = None
    ReturnDate: ReturnDate_record | None = None
    ReviewTS: ReviewTS_record | None = None
    UpdateTS: UpdateTS_record | None = None

    Actions: list[action_record | None] | None = None
    Penalties: list[penalty_record | None] | None = None
    Custom_Fields: list[custom_field_record | None] | None = None


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

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
    "behavior": json.loads(
        py_avro_schema.generate(py_type=behavior_record, options=pas_options)
    ),
    "followups": json.loads(
        py_avro_schema.generate(py_type=followups_record, options=pas_options)
    ),
    "homework": json.loads(
        py_avro_schema.generate(py_type=homework_record, options=pas_options)
    ),
    "incidents": json.loads(
        py_avro_schema.generate(py_type=incidents_record, options=pas_options)
    ),
}
