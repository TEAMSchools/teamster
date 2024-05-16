import json

import py_avro_schema

from teamster.smartrecruiters.schema import Applicant, Application, OfferedHired

ASSET_SCHEMA = {
    "applicants": json.loads(
        py_avro_schema.generate(py_type=Applicant, namespace="applicant")
    ),
    "applications": json.loads(
        py_avro_schema.generate(py_type=Application, namespace="application")
    ),
    "offered_hired": json.loads(
        py_avro_schema.generate(py_type=OfferedHired, namespace="offered_hired")
    ),
}
