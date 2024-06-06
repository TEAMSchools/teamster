import json

import py_avro_schema

from teamster.smartrecruiters.schema import Applicant, Application

APPLICANTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Applicant, namespace="applicant")
)

APPLICATIONS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Application, namespace="application")
)
