import json

import py_avro_schema

from teamster.libraries.deanslist.schema import (
    ReconcileAttendance,
    ReconcileSuspensions,
)

RECONCILE_ATTENDANCE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=ReconcileAttendance)
)

RECONCILE_SUSPENSIONS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=ReconcileSuspensions)
)
