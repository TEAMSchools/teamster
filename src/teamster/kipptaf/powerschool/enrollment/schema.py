import json

import py_avro_schema

from teamster.powerschool.enrollment.schema import SubmissionRecord

SUBMISSION_RECORD_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SubmissionRecord, namespace="submission_record")
)
