import json

import py_avro_schema

from teamster.libraries.nsc.schema import StudentTracker

options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STUDENT_TRACKER_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentTracker, options=options)
)
